"""Regressions for photo meals, explicit corrections and saved portion weights."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.meal_review import normalize_meal_proposal, user_food_claims
from core.food_reference import apply_food_references, foods_from_visual_description
from core.food_portions import estimate_visual_portions
from core.vision import (
    analyze_food_photo, analyze_image, confirm_vision_action, handle_vision_callback, modify_pending_meal,
    render_meal_preview,
)


@pytest.fixture(autouse=True)
def local_reference_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Legacy meal regressions must never depend on a developer's API keys."""
    monkeypatch.setattr("core.config.NUTRITION_CLOUD_ENABLED", False)


def food(name: str = "Pui", grams: float = 100, **kwargs: object) -> dict:
    return {"name": name, "grams": grams, "calories": 150, "protein": 20, "carbs": 4, "fat": 6, **kwargs}


@pytest.mark.asyncio
async def test_direct_local_food_vision_uses_image_and_user_weights() -> None:
    response = {"message": {"content": "Chicken, fried eggs and toast."}}
    with patch("core.vision.OLLAMA_FOOD_VISION_MODEL", "qwen3-vl:2b-instruct"), patch("core.vision._ollama_client.chat", new=AsyncMock(return_value=response)) as chat:
        result = await analyze_food_photo(b"photo", "am mancat 180 g pui")
    assert result["extracted_data"]["items"][0]["grams"] == 180
    assert result["extracted_data"]["items"][0]["grams_source"] == "user_weight"
    assert chat.call_args.kwargs["messages"][0]["images"]
    assert chat.call_args.kwargs["model"] == "qwen3-vl:2b-instruct"
    assert chat.call_args.kwargs["options"]["num_predict"] == 150


@pytest.mark.asyncio
async def test_direct_food_route_avoids_lossy_second_model() -> None:
    expected = {"type": "food", "extracted_data": {"items": [food()]}}
    with patch("core.vision.extract_text_ocr", new=AsyncMock(return_value="")), patch("core.vision.analyze_food_photo", new=AsyncMock(return_value=expected)), patch("core.vision.describe_image_with_vision", new=AsyncMock()) as legacy:
        assert await analyze_image(photo_bytes=b"photo") == expected
    legacy.assert_not_awaited()


@pytest.mark.asyncio
async def test_direct_food_model_failure_allows_legacy_fallback() -> None:
    with patch("core.vision.OLLAMA_FOOD_VISION_MODEL", "qwen3-vl:2b-instruct"), patch("core.vision._ollama_client.chat", new=AsyncMock(side_effect=RuntimeError("offline"))):
        assert await analyze_food_photo(b"photo") is None


@pytest.mark.asyncio
async def test_legacy_food_model_does_not_use_unsupported_direct_path() -> None:
    with patch("core.vision.OLLAMA_FOOD_VISION_MODEL", "llava"), patch("core.vision._ollama_client.chat", new=AsyncMock()) as chat:
        assert await analyze_food_photo(b"photo") is None
    chat.assert_not_awaited()


def test_visual_inventory_retains_unidentified_fried_food() -> None:
    items = foods_from_visual_description("Two fried eggs, toast, bacon, fried food and tomatoes.")
    assert items[0]["count"] == 2
    assert any(item["name"] == "Alimente prăjite — neidentificate" for item in items)
    assert all(item["grams"] is None for item in items)


def test_visual_inventory_does_not_silently_omit_unsupported_foods() -> None:
    items = foods_from_visual_description("two eggs, toast, pizza, pasta, knife, fork and cutting board")
    assert any(item["name"] == "pizza" for item in items)
    assert any(item["name"] == "pasta" for item in items)
    assert not any(item["name"] in {"knife", "fork", "cutting board"} for item in items)
    result = apply_food_references({"items": items})
    assert result["needs_portion_details"]


def test_toasted_bread_preparation_survives_normalization() -> None:
    result = apply_food_references({"items": [{"name": "Pâine prăjită", "count": 2}]})
    assert result["items"][0]["name"] == "Pâine prăjită"
    assert result["items"][0]["grams"] == 56
    assert not result["needs_portion_details"]


def test_references_do_not_copy_model_macros_or_tiny_egg_portions() -> None:
    result = apply_food_references({"items": [food("Ouă", grams=30, count=2), food("Roșie", grams=20, count=1)]})
    assert result["items"][0]["grams"] == 92
    assert result["items"][0]["calories"] == 180.3
    assert result["items"][1]["grams"] == 123
    assert result["items"][1]["calories"] == 22.1
    assert result["items"][1]["fat"] == 0.2


@pytest.mark.asyncio
async def test_complete_food_correction_and_weight_edit_work_without_llm() -> None:
    with patch("core.vision._call_local_llm_json", new=AsyncMock()) as llm:
        extra = await modify_pending_meal({"items": [food("Castravete")]}, "am mancat 3 bucati mici snitele, 2 oua, bucati mici de slanina si o rosie")
        assert not extra["needs_portion_details"]
        assert extra["items"][2]["portion_method"] == "standard_serving"
        assert extra["items"][2]["grams_min"] == 10
        assert extra["items"][2]["grams_max"] == 60
        assert extra["items"][1]["grams"] == 92
        updated = await modify_pending_meal(extra, "slanina 25 g")
        assert not updated["needs_portion_details"]
        assert updated["items"][2]["grams"] == 25
        assert updated["items"][2]["grams_source"] == "user_weight"
        assert updated["items"][2]["calories"] == 203
        assert [item["name"] for item in updated["items"]] == ["Șnițele", "Ouă", "Slănină", "Roșie"]
    llm.assert_not_awaited()


@pytest.mark.asyncio
async def test_visual_weights_preserve_user_grams_and_do_not_mix_food_indices() -> None:
    client = SimpleNamespace(chat=AsyncMock(return_value={"message": {"content": "0|800|700|900\n1|35|30|40\n2|NaN|1|2"}}))
    items = [food("Ouă", grams=105, grams_source="user_weight"), {"name": "Slănină", "grams": None}]
    result = await estimate_visual_portions(client, "qwen3-vl:2b-instruct", b"photo", items)
    assert result[0]["grams"] == 105
    assert result[1]["grams"] == 35
    assert result[1]["grams_min"] <= 23
    assert result[1]["grams_max"] >= 49
    assert result[1]["portion_method"] == "vision"
    assert items[1]["grams"] is None


@pytest.mark.asyncio
async def test_uncertain_foods_do_not_receive_visual_weight_guesses() -> None:
    client = SimpleNamespace(chat=AsyncMock())
    items = [{"name": "Alimente prăjite — neidentificate", "uncertain": True}]
    assert await estimate_visual_portions(client, "qwen3-vl:2b-instruct", b"photo", items) == items
    client.chat.assert_not_awaited()


@pytest.mark.asyncio
async def test_visual_estimator_failure_returns_unchanged_items() -> None:
    client = SimpleNamespace(chat=AsyncMock(side_effect=RuntimeError("offline")))
    items = [{"name": "Slănină", "grams": None}]
    assert await estimate_visual_portions(client, "qwen3-vl:2b-instruct", b"photo", items) == items


@pytest.mark.asyncio
async def test_corrected_photo_meal_is_ready_without_user_weighing() -> None:
    estimates = {"message": {"content": "0|150|120|190\n1|100|80|120\n2|35|20|50\n3|120|90|150"}}
    with patch("core.vision._ollama_client.chat", new=AsyncMock(return_value=estimates)):
        result = await modify_pending_meal({"items": []}, "am mancat 3 bucati mici snitele, 2 oua, bucati mici de slanina si o rosie", photo_bytes=b"photo")
    assert not result["needs_portion_details"]
    assert result["items"][2]["grams"] == 35
    assert result["items"][2]["portion_method"] == "vision"
    assert result["items"][2]["grams_source"] != "user_weight"
    assert all(item["portion_method"] == "vision" for item in result["items"])
    message, _ = render_meal_preview(result)
    assert "aprox" in message
    assert "Nu pot estima" not in message


@pytest.mark.asyncio
async def test_initial_food_review_keeps_telegram_photo_reference() -> None:
    from core.vision import process_vision_result
    result = {"type": "food", "extracted_data": {"description": "Ouă", "items": [food("Ouă")], "total_calories": 150, "total_protein": 20, "total_carbs": 4, "total_fat": 6}}
    with patch("core.vision.set_state", new=AsyncMock()) as set_state:
        await process_vision_result(MagicMock(), result, {}, receipt_telegram_file_id="photo-reference")
    assert set_state.call_args.kwargs["extra"]["food_telegram_file_id"] == "photo-reference"


@pytest.mark.asyncio
async def test_user_can_request_estimation_without_weighing_or_llm_text_translation() -> None:
    extra = apply_food_references({"items": [{"name": "Slănină", "grams": None}]})
    assert extra["needs_portion_details"]
    with patch("core.vision._call_local_llm_json", new=AsyncMock()) as text_llm:
        result = await modify_pending_meal(extra, "nu stiu gramele")
    assert not result["needs_portion_details"]
    assert result["items"][0]["portion_method"] == "standard_serving"
    text_llm.assert_not_awaited()


def test_visual_count_guard_rejects_huge_weight_for_small_schnitzel_pieces() -> None:
    result = apply_food_references({"items": [{"name": "Șnițele", "grams": 900, "count": 3, "portion_method": "vision"}]}, "am mancat 3 bucati mici snitele", estimate_missing=True)
    assert result["items"][0]["grams"] == 120
    assert result["items"][0]["portion_method"] == "standard_serving"


def test_complete_user_meal_replaces_wrong_photo_foods() -> None:
    message = "am mancat 3 bucati mici snitele, 2 oua, bucati mici de slanina si o rosie"
    complete, claims = user_food_claims(message)
    assert complete
    assert [claim["name"] for claim in claims] == ["Șnițele", "Ouă", "Slănină", "Roșie"]
    proposal = normalize_meal_proposal({"items": [food("Toast"), food("Castravete"), food("Șnițele")]}, message)
    assert [item["name"] for item in proposal["items"]] == ["Șnițele", "Ouă", "Slănină", "Roșie"]
    assert proposal["items"][0]["count"] == 3
    assert proposal["items"][1]["count"] == 2
    assert proposal["needs_portion_details"]
    assert proposal["calories"] is None


@pytest.mark.parametrize("message,grams", [("am mancat 150,5 g pui", 150.5), ("puiul are 180 g", 180), ("adauga 0.2 kg pui", 200)])
def test_user_weights_are_authoritative(message: str, grams: float) -> None:
    proposal = normalize_meal_proposal({"items": [food()]}, message)
    item = proposal["items"][0]
    assert item["grams"] == grams
    assert item["grams_source"] == "user_weight"
    assert item["protein"] == round(20 * grams / 100, 1)


def test_previously_measured_weight_is_not_overwritten() -> None:
    proposal = normalize_meal_proposal(
        {"items": [food(grams=250)]}, "schimba masa in cina",
        [food(grams=180, grams_source="user_weight")],
    )
    assert proposal["items"][0]["grams"] == 180


def test_counts_are_not_claimed_as_measured_grams() -> None:
    proposal = normalize_meal_proposal({"items": [food("Ouă", grams=50, count=1, grams_min=40, grams_max=70)]}, "am mancat 2 oua")
    item = proposal["items"][0]
    assert item["count"] == 2
    assert item["grams"] == 100
    assert item["grams_source"] == "photo_estimate"
    assert item["grams_min"] == 80


@pytest.mark.parametrize("value", [None, -3, "NaN", "inf", {}, True])
def test_invalid_or_unknown_portions_remain_unknown(value: object) -> None:
    proposal = normalize_meal_proposal({"items": [food(grams=value)]})
    assert proposal["needs_portion_details"]
    assert proposal["calories"] is None
    message, _ = render_meal_preview(proposal)
    assert "necunoscut" in message
    assert "0 kcal" not in message


def test_inconsistent_energy_is_reconciled_and_estimated() -> None:
    proposal = normalize_meal_proposal({"items": [food(calories=900)]})
    assert proposal["calories"] == 150  # 20*4 + 4*4 + 6*9
    assert proposal["nutrition_estimated"]


def test_implausible_nutrient_mass_requires_review() -> None:
    proposal = normalize_meal_proposal({"items": [food(grams=20, protein=90)]})
    assert proposal["needs_portion_details"]


@pytest.mark.asyncio
async def test_failed_correction_does_not_report_success() -> None:
    extra = {"items": [food()]}
    with patch("core.vision._call_local_llm_json", new=AsyncMock(side_effect=RuntimeError("offline"))):
        with pytest.raises(ValueError, match="păstrate"):
            await modify_pending_meal(extra, "adauga orez")
    assert extra == {"items": [food()]}


@pytest.mark.asyncio
async def test_unknown_meal_cannot_be_confirmed_or_clear_pending_state() -> None:
    extra = normalize_meal_proposal({"items": [{"name": "Șnițele"}]})
    state = {"action": "meal_log", "extra": extra}
    with patch("modules.nutrition.handle_nutrition_intent", new=AsyncMock()) as save, patch("core.vision.clear_state", new=AsyncMock()) as clear:
        response = await confirm_vision_action(MagicMock(), state)
    assert "Nu pot estima încă toată masa" in response
    save.assert_not_awaited()
    clear.assert_not_awaited()


@pytest.mark.asyncio
async def test_confirmation_preserves_real_grams_for_storage() -> None:
    extra = normalize_meal_proposal({"items": [food()]}, "am mancat 180 g pui")
    state = {"action": "meal_log", "extra": extra}
    with patch("modules.nutrition.handle_nutrition_intent", new=AsyncMock(return_value=("✅ Salvat", None, 1))) as save, patch("core.vision.clear_state", new=AsyncMock()) as clear:
        await confirm_vision_action(MagicMock(), state)
    assert save.call_args.args[2]["items"][0]["quantity_g"] == 180
    clear.assert_awaited_once()


@pytest.mark.asyncio
async def test_unknown_portion_button_keeps_correction_controls() -> None:
    state = {"state_type": "awaiting_vision_confirmation", "action": "meal_log", "extra": normalize_meal_proposal({"items": [{"name": "Șnițele"}]})}
    query = SimpleNamespace(answer=AsyncMock(), edit_message_text=AsyncMock())
    with patch("core.vision.get_state", new=AsyncMock(return_value=state)):
        await handle_vision_callback(query, MagicMock(), "vision:confirm")
    assert "Mai am nevoie" in query.answer.call_args.args[0]
    assert query.edit_message_text.call_args.kwargs["reply_markup"] is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["am mancat 3 snitele", "nu este paine, sunt snitele", "adauga oua, da"])
async def test_real_message_handler_applies_correction_not_cancel_or_confirm(text: str) -> None:
    from bot import handler

    state = {"state_type": "awaiting_vision_confirmation", "module": "nutrition", "action": "meal_log", "extra": {"items": [food()]}}
    update = SimpleNamespace(
        update_id=1,
        effective_user=SimpleNamespace(id=6838073664), effective_chat=SimpleNamespace(type="private"),
        message=SimpleNamespace(text=text, voice=None, reply_text=AsyncMock()),
    )
    context = SimpleNamespace(application=SimpleNamespace(bot_data={}), bot=MagicMock())
    updated = normalize_meal_proposal({"items": [food("Șnițele")]})
    with patch("bot.handler.security_check", new=AsyncMock(return_value=True)), patch("bot.handler.get_recent_history", new=AsyncMock(return_value=[])), patch("bot.handler.save_message", new=AsyncMock()), patch("core.state.get_state", new=AsyncMock(return_value=state)), patch("core.state.get_pending_action", new=AsyncMock(return_value=None)), patch("core.vision.modify_pending_meal", new=AsyncMock(return_value=updated)) as modify, patch("bot.handler.set_state", new=AsyncMock()) as set_state:
        await handler.message_handler(update, context, MagicMock(), text=text)
    modify.assert_awaited_once_with(state["extra"], text)
    set_state.assert_awaited_once()
    assert "Am actualizat" in update.message.reply_text.call_args.args[0]


@pytest.mark.asyncio
async def test_message_handler_reuses_photo_for_food_correction() -> None:
    from bot import handler

    text = "am mancat 3 bucati mici snitele, 2 oua si o rosie"
    extra = {"items": [food()], "food_telegram_file_id": "original-photo"}
    state = {"state_type": "awaiting_vision_confirmation", "module": "nutrition", "action": "meal_log", "extra": extra}
    update = SimpleNamespace(update_id=1, effective_user=SimpleNamespace(id=6838073664), effective_chat=SimpleNamespace(type="private"), message=SimpleNamespace(text=text, voice=None, reply_text=AsyncMock()))
    downloaded = SimpleNamespace(download_as_bytearray=AsyncMock(return_value=bytearray(b"photo-bytes")))
    bot = SimpleNamespace(get_file=AsyncMock(return_value=downloaded))
    context = SimpleNamespace(application=SimpleNamespace(bot_data={}), bot=bot)
    corrected = apply_food_references({"items": [{"name": "Roșie", "count": 1}]})
    with patch("bot.handler.security_check", new=AsyncMock(return_value=True)), patch("bot.handler.get_recent_history", new=AsyncMock(return_value=[])), patch("bot.handler.save_message", new=AsyncMock()), patch("core.state.get_state", new=AsyncMock(return_value=state)), patch("core.state.get_pending_action", new=AsyncMock(return_value=None)), patch("core.vision.modify_pending_meal", new=AsyncMock(return_value=corrected)) as modify, patch("bot.handler.set_state", new=AsyncMock()):
        await handler.message_handler(update, context, MagicMock(), text=text)
    bot.get_file.assert_awaited_once_with("original-photo")
    modify.assert_awaited_once_with(extra, text, photo_bytes=b"photo-bytes")
