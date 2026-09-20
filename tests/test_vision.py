"""
Tests for core/vision.py — Local OCR, itemized receipt extraction, and multi-transaction logging.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.vision import (
    _clean_json_from_text,
    _extract_receipt_items_from_ocr,
    _merge_receipt_items,
    handle_vision_callback,
    process_vision_result,
)


def test_clean_json_from_text():
    # Direct JSON
    raw1 = '{"type": "receipt", "confidence": 0.95}'
    assert _clean_json_from_text(raw1)["type"] == "receipt"

    # Markdown wrapped JSON
    raw2 = '```json\n{"type": "receipt", "confidence": 0.95}\n```'
    assert _clean_json_from_text(raw2)["type"] == "receipt"

    # Text before and after JSON
    raw3 = 'Iată datele extrase:\n{"type": "receipt", "confidence": 0.95}\nSper că ajută!'
    assert _clean_json_from_text(raw3)["type"] == "receipt"


def test_extract_receipt_items_from_price_before_name_layout():
    """A common Mega Image layout places the price row before the product name."""
    ocr_text = """
    MEGA IMAGE
    1,000 Buc x 20.50 20,50 A
    VUSE CAPS BLUEBERRY
    1,000 Buc X 3,55 3.55 B
    ORBIT GUM MINT
    TOTAL 24,05
    """

    items = _extract_receipt_items_from_ocr(ocr_text)

    assert items == [
        {"name": "VUSE CAPS BLUEBERRY", "price": 20.50, "category": "altele"},
        {"name": "ORBIT GUM MINT", "price": 3.55, "category": "altele"},
    ]


def test_action_price_rows_correct_a_model_price_attached_to_next_product():
    """ACTION prints `LEI` on the price row and the name on the next row."""
    ocr_text = """
    1 BUC x 13,59 LEI
    SITECOM SET ADAPTOR USB 2BUC 13,59 A
    1 BUC x 3,87 LEI 3,87 A
    LAB31 MOUSEPAD IMPERME 25X20CM DI.CUL
    1 BUC x 49,95 LEI
    PHILIPS STICK USB 2-IN-1 A/C 49,95 A
    TOTAL LEI 58,00
    """
    model_items = [
        {"name": "SITECOM SET ADAPTOR USB 2BUC", "price": 13.59, "category": "altele"},
        {"name": "LAB31 MOUSEPAD IMPERME 25X20CM DI.CUL", "price": 49.95, "category": "altele"},
        {"name": "PHILIPS STICK USB 2-IN-1 A/C", "price": 49.95, "category": "altele"},
    ]

    recovered = _extract_receipt_items_from_ocr(ocr_text)
    merged = _merge_receipt_items(model_items, recovered)

    assert [item["price"] for item in recovered] == [13.59, 3.87, 49.95]
    assert [item["price"] for item in merged] == [13.59, 3.87, 49.95]
    assert sum(item["price"] for item in merged) == 67.41


@pytest.mark.asyncio
async def test_process_receipt_keeps_printed_total_when_item_list_is_incomplete():
    pool = MagicMock()
    result = {
        "type": "receipt",
        "extracted_data": {
            "merchant": "Magazin",
            "total_amount": 24.05,
            "items": [{"name": "Produs citit", "price": 20.50, "category": "altele"}],
        },
    }

    with patch("core.vision.set_state", new=AsyncMock()) as mock_set_state:
        message, _ = await process_vision_result(pool, result, {"personal_notes": ""})

    assert "24.05 RON" in message
    assert mock_set_state.call_args.kwargs["extra"]["amount"] == 24.05


@pytest.mark.asyncio
async def test_process_vision_result_itemized_receipt():
    pool = MagicMock()
    user_profile = {"personal_notes": ""}

    sample_result = {
        "type": "receipt",
        "confidence": 0.95,
        "extracted_data": {
            "merchant": "Lidl",
            "total_amount": 25.18,
            "items": [
                {"name": "Banane 1kg", "price": 6.99, "category": "mâncare"},
                {"name": "Iaurt grecesc 10%", "price": 4.49, "category": "mâncare"},
                {"name": "Detergent vase 500ml", "price": 8.50, "category": "utilități"},
                {"name": "Paracetamol 500mg", "price": 5.20, "category": "sănătate"},
            ],
        },
        "reply": "Am extras bonul de la Lidl cu 4 produse.",
    }

    with patch("core.vision.set_state", new=AsyncMock()) as mock_set_state:
        msg, keyboard = await process_vision_result(pool, sample_result, user_profile)

        # Check message content
        assert "Lidl" in msg
        assert "Banane 1kg" in msg
        assert "6.99 RON" in msg
        assert "mâncare" in msg
        assert "utilități" in msg
        assert "25.18 RON" in msg
        assert "4 produse" in msg
        assert keyboard is not None

        # Check state saved with items
        mock_set_state.assert_called_once()
        args, kwargs = mock_set_state.call_args
        assert args[1] == "awaiting_vision_confirmation"
        assert args[2] == "finance"
        assert args[3] == "log_expense"
        extra = kwargs.get("extra")
        assert extra is not None
        assert len(extra["items"]) == 4
        assert extra["amount"] == 25.18
        assert extra["description"] == "Lidl"


@pytest.mark.asyncio
async def test_handle_vision_callback_logs_all_items():
    pool = MagicMock()
    query = MagicMock()
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()

    mock_state = {
        "state_type": "awaiting_vision_confirmation",
        "action": "log_expense",
        "extra": {
            "amount": 25.18,
            "description": "Lidl",
            "items": [
                {"name": "Banane 1kg", "price": 6.99, "category": "mâncare"},
                {"name": "Iaurt grecesc 10%", "price": 4.49, "category": "mâncare"},
                {"name": "Detergent vase 500ml", "price": 8.50, "category": "utilități"},
                {"name": "Paracetamol 500mg", "price": 5.20, "category": "sănătate"},
            ],
        },
    }

    with patch("core.vision.get_state", new=AsyncMock(return_value=mock_state)), \
         patch("core.vision.clear_state", new=AsyncMock()) as mock_clear, \
         patch("core.vision.log_transaction", new=AsyncMock()) as mock_log:

        await handle_vision_callback(query, pool, "vision:confirm")

        # Verify log_transaction called 4 times for the 4 items
        assert mock_log.call_count == 4
        # Verify individual items logged with categories
        calls = mock_log.call_args_list
        assert calls[0].args[1] == "expense"
        assert calls[0].args[2] == 6.99
        assert calls[0].kwargs["category"] == "mâncare"
        assert "Banane 1kg" in calls[0].kwargs["description"]

        assert calls[2].args[2] == 8.50
        assert calls[2].kwargs["category"] == "utilități"

        # Verify state cleared and confirmation answered
        mock_clear.assert_called_once()
        query.answer.assert_called_once_with("Salvat!")
        query.edit_message_text.assert_called_once()
        assert "4 produse" in query.edit_message_text.call_args.args[0]


@pytest.mark.asyncio
async def test_identify_product_vape_and_food():
    from core.web_search import identify_product_with_web

    # Typo + brand detection for vape/e-cigarette
    name, cat = await identify_product_with_web("VISE CAPS BLUEBERRY")
    assert "Vuse" in name
    assert cat == "țigări"

    # Romanian meat product
    name2, cat2 = await identify_product_with_web("CARNATI CABANANDS")
    assert "Cabanos" in name2
    assert cat2 == "mâncare"


@pytest.mark.asyncio
async def test_process_vision_result_food_meal():
    pool = MagicMock()
    user_profile = {"personal_notes": ""}

    sample_food_result = {
        "type": "food",
        "confidence": 0.9,
        "extracted_data": {
            "description": "Piept de pui la grătar cu orez",
            "meal_type": "pranz",
            "total_calories": 520,
            "total_protein": 42,
            "total_carbs": 48,
            "total_fat": 12,
            "items": [
                {"name": "Piept de pui", "grams": 150, "calories": 240, "protein": 31, "carbs": 0, "fat": 4},
                {"name": "Orez fiert", "grams": 200, "calories": 260, "protein": 5, "carbs": 46, "fat": 1},
            ],
        },
        "reply": "Am identificat mâncarea.",
    }

    with patch("core.vision.set_state", new=AsyncMock()) as mock_set_state:
        msg, keyboard = await process_vision_result(pool, sample_food_result, user_profile)

        assert "Piept de pui la grătar cu orez" in msg
        assert "520 kcal" in msg
        assert "42g P" in msg
        assert "48g C" in msg
        assert "12g F" in msg
        assert "Piept de pui" in msg
        assert keyboard is not None

        mock_set_state.assert_called_once()
        args, kwargs = mock_set_state.call_args
        assert args[1] == "awaiting_vision_confirmation"
        assert args[2] == "nutrition"
        assert args[3] == "meal_log"
        extra = kwargs.get("extra")
        assert extra["calories"] == 520
        assert len(extra["items"]) == 2


@pytest.mark.asyncio
async def test_handle_vision_callback_meal_log():
    pool = MagicMock()
    query = MagicMock()
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()

    mock_state = {
        "state_type": "awaiting_vision_confirmation",
        "action": "meal_log",
        "extra": {
            "calories": 520,
            "protein": 42,
            "carbs": 48,
            "fat": 12,
            "description": "Piept de pui cu orez",
            "meal_type": "pranz",
            "items": [{"name": "Piept de pui", "grams": 150, "calories": 240}],
        },
    }

    with patch("core.vision.get_state", new=AsyncMock(return_value=mock_state)), \
         patch("core.vision.clear_state", new=AsyncMock()) as mock_clear, \
         patch("modules.nutrition.handle_nutrition_intent", new=AsyncMock(return_value=("Masă salvată cu succes!", None, 1))) as mock_handle_nutrition:

        await handle_vision_callback(query, pool, "vision:confirm")

        mock_handle_nutrition.assert_called_once()
        mock_clear.assert_called_once()
        query.answer.assert_called_once_with("Poftă bună!")
        query.edit_message_text.assert_called_once()
        assert "Masă salvată cu succes!" in query.edit_message_text.call_args.args[0]


@pytest.mark.asyncio
async def test_analyze_food_from_vision():
    from core.vision import analyze_food_from_vision

    sample_json = {
        "is_food": True,
        "description": "Omletă cu legume și pâine prăjită",
        "meal_type": "mic_dejun",
        "total_calories": 380,
        "total_protein": 22,
        "total_carbs": 26,
        "total_fat": 18,
        "items": [
            {"name": "Omletă din 3 ouă", "grams": 180, "calories": 270, "protein": 19, "carbs": 2, "fat": 17},
            {"name": "Pâine prăjită", "grams": 40, "calories": 110, "protein": 3, "carbs": 24, "fat": 1},
        ],
    }

    with patch("core.vision._call_local_llm_json", new=AsyncMock(return_value=sample_json)):
        result = await analyze_food_from_vision("A plate of fluffy scrambled eggs with a slice of toasted sourdough bread.")
        assert result is not None
        assert result["type"] == "food"
        assert result["extracted_data"]["total_calories"] == 380
        assert result["extracted_data"]["total_protein"] == 22
        assert len(result["extracted_data"]["items"]) == 2


@pytest.mark.asyncio
async def test_product_memory_lookup_and_learning():
    from db.queries.product_memory import _clean_pattern

    assert _clean_pattern("CAMELION BATERIE OR2032") == "camelion baterie or2032"
    assert _clean_pattern("DSC ING VANIZM. 4,99") == "dsc ing vanizm 4 99"
    assert _clean_pattern("URSUS PREMIUM ST, 0.8L") == "ursus premium st 0 8l"

    pool = MagicMock()
    user_profile = {"personal_notes": ""}

    sample_result = {
        "type": "receipt",
        "confidence": 0.95,
        "extracted_data": {
            "merchant": "URSUS PREMIUM",
            "total_amount": 16.48,
            "items": [
                {"name": "CAMELION BATERIE OR2032", "price": 3.40, "category": "altele"},
                {"name": "ARO OTET 9 GRADE", "price": 6.00, "category": "altele"},
            ],
            "ocr_text": "SE FERAL IMPS SAL Loc.Cumpana\nURSUS PREMIUM ST\nCAMELION BATERIE",
        },
        "reply": "Sumar",
    }

    mock_learned_product = {
        "clean_name": "Baterie Camelion CR2032",
        "category": "utilități",
        "last_price": 3.40,
    }

    with patch("db.queries.product_memory.find_remembered_merchant", new=AsyncMock(return_value="SC FERAL IMPEX SRL")), \
         patch("db.queries.product_memory.find_remembered_product", new=AsyncMock(side_effect=[mock_learned_product, None])), \
         patch("core.vision.set_state", new=AsyncMock()) as mock_set_state:

        msg, keyboard = await process_vision_result(pool, sample_result, user_profile)

        # Verify merchant was corrected from learned memory
        assert "SC FERAL IMPEX SRL" in msg
        # Verify product was corrected from learned memory
        assert "Baterie Camelion CR2032" in msg
        assert "utilități" in msg
        mock_set_state.assert_called_once()


@pytest.mark.asyncio
async def test_modify_pending_receipt():
    from core.vision import modify_pending_receipt

    extra = {
        "amount": 105.02,
        "category": "transport",
        "description": "Necunoscut",
        "items": [
            {"name": "Euro Luk 95", "price": 105.02, "category": "altele"},
        ],
        "type": "expense",
        "ocr_text": "LUKOIL ROMANIA\nEuro Luk 95",
    }

    mock_llm_return = {
        "merchant": "Lukoil",
        "category": "transport",
        "items": [
            {"name": "Benzină Euro Luk 95", "price": 105.02, "category": "transport"},
            {"name": "Cafea Espresso", "price": 10.00, "category": "mâncare"},
        ],
        "total_amount": 115.02,
    }

    with patch("core.vision._call_local_llm_json", new=AsyncMock(return_value=mock_llm_return)):
        updated_extra = await modify_pending_receipt(
            extra, "comerciantul e Lukoil și adaugă o cafea de 10 lei"
        )

        assert updated_extra["description"] == "Lukoil"
        assert updated_extra["category"] == "transport"
        assert len(updated_extra["items"]) == 2
        assert updated_extra["items"][0]["category"] == "transport"
        assert updated_extra["items"][1]["name"] == "Cafea Espresso"
        assert updated_extra["amount"] == 115.02


def test_render_receipt_preview():
    from core.vision import render_receipt_preview

    extra = {
        "amount": 115.02,
        "category": "transport",
        "description": "Lukoil",
        "items": [
            {"name": "Benzină Euro Luk 95", "price": 105.02, "category": "transport"},
            {"name": "Cafea Espresso", "price": 10.00, "category": "mâncare"},
        ],
    }

    msg, keyboard = render_receipt_preview(extra)
    assert "Lukoil" in msg
    assert "Benzină Euro Luk 95" in msg
    assert "105.02 RON" in msg
    assert "transport" in msg
    assert "115.02 RON" in msg
    assert keyboard is not None
    buttons = [b.text for row in keyboard.inline_keyboard for b in row]
    assert "✅ Confirmă tot" in buttons
    assert "❌ Anulează" in buttons


@pytest.mark.asyncio
async def test_confirm_and_cancel_vision_action():
    from core.vision import confirm_vision_action, cancel_vision_action

    pool = MagicMock()
    state = {
        "state_type": "awaiting_vision_confirmation",
        "action": "log_expense",
        "extra": {
            "amount": 50.0,
            "category": "transport",
            "description": "Petrom",
            "items": [
                {"name": "Motorină Standard", "price": 50.0, "category": "transport"}
            ],
            "type": "expense",
            "ocr_text": "PETROM",
        },
    }

    with patch("core.vision.log_transaction", new=AsyncMock()) as mock_log, \
         patch("core.vision.clear_state", new=AsyncMock()) as mock_clear, \
         patch("db.queries.product_memory.remember_product", new=AsyncMock()) as mock_rem_prod, \
         patch("db.queries.product_memory.remember_merchant", new=AsyncMock()) as mock_rem_merch:

        reply = await confirm_vision_action(pool, state)
        assert "Am înregistrat cu succes 1 produse" in reply
        assert "Petrom" in reply
        mock_log.assert_called_once()
        mock_clear.assert_called_once()
        mock_rem_prod.assert_called_once()
        mock_rem_merch.assert_called_once()

    with patch("core.vision.clear_state", new=AsyncMock()) as mock_clear:
        cancel_reply = await cancel_vision_action(pool)
        assert "anulată" in cancel_reply
        mock_clear.assert_called_once()


def test_render_meal_preview():
    from core.vision import render_meal_preview

    extra = {
        "description": "Piept de pui la grătar cu lămâie",
        "calories": 220,
        "protein": 35,
        "carbs": 0,
        "fat": 4,
        "items": [
            {"name": "Piept de pui", "grams": 150, "calories": 220, "protein": 35, "carbs": 0, "fat": 4}
        ],
    }

    msg, keyboard = render_meal_preview(extra)
    assert "Piept de pui la grătar cu lămâie" in msg
    assert "220 kcal" in msg
    assert "35g P" in msg
    assert keyboard is not None
    buttons = [b.text for row in keyboard.inline_keyboard for b in row]
    assert "✅ Înregistrează masa" in buttons
    assert "❌ Anulează" in buttons


@pytest.mark.asyncio
async def test_modify_pending_meal():
    from core.vision import modify_pending_meal

    extra = {
        "description": "Piept de pui la grătar",
        "meal_type": "pranz",
        "calories": 220,
        "protein": 35,
        "carbs": 0,
        "fat": 4,
        "items": [
            {"name": "Piept de pui", "grams": 150, "calories": 220, "protein": 35, "carbs": 0, "fat": 4}
        ],
    }

    mock_llm_return = {
        "description": "Piept de pui la grătar cu orez",
        "meal_type": "pranz",
        "items": [
            {"name": "Piept de pui", "grams": 150, "calories": 220, "protein": 35, "carbs": 0, "fat": 4},
            {"name": "Orez fiert", "grams": 100, "calories": 130, "protein": 3, "carbs": 28, "fat": 0},
        ],
    }

    with patch("core.vision._call_local_llm_json", new=AsyncMock(return_value=mock_llm_return)):
        updated_extra = await modify_pending_meal(extra, "adaugă și 100g orez fiert")

        assert updated_extra["description"] == "Piept de pui la grătar cu orez"
        assert len(updated_extra["items"]) == 2
        assert updated_extra["calories"] == 350
        assert updated_extra["protein"] == 38
        assert updated_extra["carbs"] == 28
        assert updated_extra["fat"] == 4


