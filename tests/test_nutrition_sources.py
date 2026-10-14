"""External nutrition contracts and real meal-flow boundaries, no network."""

import asyncio
from dataclasses import replace
import json
from pathlib import Path
import sqlite3
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from core import config
from core.meal_nutrition import enrich_meal_references
from core.meal_review import normalize_meal_proposal, user_food_claims
from core.nutrition_sources import NutritionLookup, ReferenceCache, parse_off, parse_usda, validated_reference
from core.vision import analyze_food_photo, modify_pending_meal, render_meal_preview


def usda_food(title: str = "Egg, whole, cooked, fried", **changes: object) -> dict:
    result = {"fdcId": 173423, "description": title, "foodNutrients": [
        {"nutrientId": key, "unitName": unit, "value": value}
        for key, unit, value in [(1008, "KCAL", 196), (1003, "G", 13.61), (1004, "G", 14.84), (1005, "G", .83)]
    ]}
    return {**result, **changes}


def off_product(**changes: object) -> dict:
    return {"code": "3017620422003", "product_name": "Nutella", "brands": "Ferrero",
            "nutrition_data_per": "100g", "nutriments": {"energy-kcal_100g": 539, "proteins_100g": 6.3,
            "carbohydrates_100g": 57.5, "fat_100g": 30.9}, **changes}


@pytest.fixture
def cloud(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "NUTRITION_CLOUD_ENABLED", True)


def test_usda_contract_units_and_nested_detail() -> None:
    ref = parse_usda(usda_food())
    assert ref and ref.calories == 196 and ref.protein == 13.61
    nested = usda_food()
    nested["foodNutrients"] = [{"nutrient": {"id": n["nutrientId"], "unitName": n["unitName"]}, "amount": n["value"]} for n in nested["foodNutrients"]]
    assert parse_usda(nested) == ref
    nested["foodNutrients"][0]["nutrient"]["unitName"] = "KJ"
    assert parse_usda(nested) is None


@pytest.mark.parametrize("change", [
    {"foodNutrients": None}, {"foodNutrients": []}, {"fdcId": "http://evil"},
])
def test_bad_usda_contract(change: dict) -> None:
    assert parse_usda(usda_food(**change)) is None


def test_off_kj_conversion_missing_not_zero_and_ml() -> None:
    ref = parse_off(off_product())
    assert ref and ref.calories == 539
    product = off_product()
    product["nutriments"]["energy-kj_100g"] = product["nutriments"].pop("energy-kcal_100g") * 4.184
    assert parse_off(product).calories == pytest.approx(539)
    assert parse_off(off_product(nutrition_data_per="100ml")) is None
    product["nutriments"].pop("proteins_100g")
    assert parse_off(product) is None


@pytest.mark.parametrize("values", [
    {"calories": float("nan"), "protein": 1, "carbs": 1, "fat": 1},
    {"calories": 100, "protein": -1, "carbs": 1, "fat": 1},
    {"calories": 100, "protein": 100, "carbs": 100, "fat": 1},
    {"calories": 900, "protein": 1, "carbs": 1, "fat": 1},
    {"calories": True, "protein": 1, "carbs": 1, "fat": 1},
])
def test_invalid_reference_rejected(values: dict) -> None:
    assert validated_reference("test", "1", "food", values, "") is None


async def test_usda_lookup_cache_and_privacy(tmp_path: Path) -> None:
    calls = []
    def transport(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"foods": [usda_food()]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        lookup = NutritionLookup(api_key="private-key", enabled=True, cache_path=tmp_path / "cache.sqlite", client=client)
        first = await lookup.lookup({"name": "Ouă", "grams": 125, "caption": "private text", "photo": b"private"})
        second = await lookup.lookup({"name": "Ouă", "grams": 300})
    assert first and second and second.cached and len(calls) == 1
    request = calls[0]
    assert request.headers["X-Api-Key"] == "private-key"
    assert "private" not in str(request.url) and "125" not in str(request.url)
    payload = json.loads(request.content)
    assert request.method == "POST" and payload["query"] == "egg fried"
    assert isinstance(payload["dataType"], list)
    assert set(payload) == {"query", "dataType", "pageSize"}
    with sqlite3.connect(tmp_path / "cache.sqlite") as conn:
        data = str(conn.execute("SELECT * FROM food_references").fetchall())
        assert "private" not in data and "125" not in data


async def test_off_exact_barcode_does_not_fallback_usda(tmp_path: Path) -> None:
    calls = []
    def transport(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"product": off_product()})
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        lookup = NutritionLookup(api_key="secret", enabled=True, cache_path=tmp_path / "c", client=client)
        ref = await lookup.lookup({"name": "Nutella", "barcode": "3017620422003"})
    assert ref and ref.provider == "Open Food Facts"
    assert len(calls) == 1 and calls[0].url.host == "world.openfoodfacts.org"
    assert "X-Api-Key" not in calls[0].headers
    assert calls[0].headers["User-Agent"].startswith("Lora/")


async def test_branded_search_rejects_wrong_brand(tmp_path: Path) -> None:
    def transport(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"products": [off_product(brands="Wrong brand")]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        lookup = NutritionLookup(enabled=True, cache_path=tmp_path / "c", client=client)
        assert await lookup.lookup({"name": "Nutella", "brand": "Ferrero"}) is None


async def test_matching_uses_preparation_not_first_result(tmp_path: Path) -> None:
    def transport(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"foods": [usda_food("Egg, whole, raw"), usda_food()]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        lookup = NutritionLookup(api_key="key", enabled=True, cache_path=tmp_path / "c", client=client)
        assert (await lookup.lookup({"name": "Ouă"})).title.endswith("fried")
        assert (await lookup.lookup({"name": "Ouă", "preparation": "raw"})).title.endswith("raw")


def test_ambiguous_different_nutrition_not_selected() -> None:
    first = parse_usda(usda_food())
    second = replace(first, calories=300, fat=26)
    assert NutritionLookup._select("egg fried", [first, second]) is None


@pytest.mark.parametrize("title", ["Chicken meatless breaded fried", "Chicken substitute breaded fried", "Chicken breaded fried sandwich"])
def test_generic_meat_never_matches_substitute_or_sandwich(title: str) -> None:
    ref = parse_usda(usda_food(title))
    assert NutritionLookup._select("chicken breaded fried", [ref]) is None


@pytest.mark.parametrize("status", [401, 403, 429, 503])
async def test_provider_error_cooldown_and_stale_cache(tmp_path: Path, status: int) -> None:
    calls = []
    def transport(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(status, json={"error": "unavailable"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        lookup = NutritionLookup(api_key="key", enabled=True, cache_path=tmp_path / "c", client=client)
        assert await lookup.lookup({"name": "Ouă"}) is None
        assert await lookup.lookup({"name": "Ouă"}) is None
    assert len(calls) == 1


async def test_no_key_no_demo_no_network(tmp_path: Path) -> None:
    transport = httpx.MockTransport(lambda request: pytest.fail("Must not call USDA without a key"))
    async with httpx.AsyncClient(transport=transport) as client:
        lookup = NutritionLookup(enabled=True, cache_path=tmp_path / "c", client=client)
        assert await lookup.lookup({"name": "Ouă"}) is None


async def test_offline_stale_and_expiry(tmp_path: Path) -> None:
    cache = ReferenceCache(tmp_path / "c", ttl_days=1)
    ref = parse_usda(usda_food())
    cache.put("key", ref)
    with sqlite3.connect(cache.path) as conn:
        conn.execute("UPDATE food_references SET saved_at = saved_at - 172800")
    assert cache.get("key") == (False, None)
    assert cache.get("key", stale=True)[1].stale
    with sqlite3.connect(cache.path) as conn:
        conn.execute("UPDATE food_references SET saved_at = saved_at - 172800")
    assert cache.get("key", stale=True) == (False, None)


async def test_coalesced_and_rate_limited(tmp_path: Path) -> None:
    calls = []
    def transport(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"product": off_product()})
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        lookup = NutritionLookup(enabled=True, cache_path=tmp_path / "c", client=client)
        await asyncio.gather(*(lookup.lookup({"name": "Nutella", "barcode": "3017620422003"}) for _ in range(4)))
        assert len(calls) == 1
        import time
        lookup.requests["off_product"].extend([time.monotonic()] * 15)
        assert await lookup.lookup({"name": "Other", "barcode": "12345678"}) is None
        assert len(calls) == 1


async def test_cache_permission_failure_does_not_block_lookup(tmp_path: Path) -> None:
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"foods": [usda_food()]}))) as client:
        lookup = NutritionLookup(api_key="key", enabled=True, cache_path=tmp_path / "c", client=client)
        with patch.object(lookup.cache, "get", side_effect=PermissionError), patch.object(lookup.cache, "put", side_effect=PermissionError):
            assert await lookup.lookup({"name": "Ouă"}) is not None


def test_preserves_brand_barcode_and_preparation() -> None:
    text = "am mancat 100 g Nutella marca Ferrero cod de bare 3017620422003"
    complete, items = user_food_claims(text)
    assert complete and items[0]["brand"] == "ferrero" and items[0]["barcode"] == "3017620422003"
    normalized = normalize_meal_proposal({"items": items}, text)
    assert normalized["items"][0]["packaged"]
    assert normalized["items"][0]["grams_source"] == "user_weight"
    assert user_food_claims("am mancat 2 oua fierte")[1][0]["preparation"] == "boiled"


async def test_cloud_meal_replaces_llm_macros_and_retains_source(cloud: None) -> None:
    ref = parse_usda(usda_food())
    with patch("core.meal_nutrition.get_nutrition_lookup") as get_lookup:
        get_lookup.return_value.lookup = AsyncMock(return_value=ref)
        proposal = await enrich_meal_references({"items": [{"name": "Ouă", "grams": 100, "calories": 999}]}, "am mancat 2 oua")
    assert proposal["calories"] == pytest.approx(180.3)  # serving estimate 2 x 46 g
    assert proposal["items"][0]["nutrition_provider"] == "USDA FoodData Central"
    assert proposal["nutrition_lookup_incomplete"] is False
    message, _ = render_meal_preview(proposal)
    assert "USDA" in message


async def test_cloud_missing_reference_cannot_use_fixed_catalog_or_llm(cloud: None) -> None:
    with patch("core.meal_nutrition.get_nutrition_lookup") as get_lookup:
        get_lookup.return_value.lookup = AsyncMock(return_value=None)
        result = await enrich_meal_references({"items": [{"name": "Ouă", "grams": 100, "calories": 196, "protein": 13.61, "carbs": .83, "fat": 14.84}]})
    assert result["calories"] is None and result["needs_portion_details"] and result["nutrition_lookup_incomplete"]


async def test_photo_to_cloud_reference_without_uploading_image(cloud: None) -> None:
    ref = parse_usda(usda_food())
    with patch("core.meal_nutrition.get_nutrition_lookup") as get_lookup, patch("core.vision.OLLAMA_FOOD_VISION_MODEL", "qwen3-vl:2b-instruct"), patch("core.vision._ollama_client.chat", new=AsyncMock(return_value={"message": {"content": "two fried eggs"}})), patch("core.vision.estimate_visual_portions", new=AsyncMock(return_value=[{"name": "Ouă", "count": 2, "grams": 100, "portion_method": "vision"}])):
        get_lookup.return_value.lookup = AsyncMock(return_value=ref)
        result = await analyze_food_photo(b"private-photo")
        item = get_lookup.return_value.lookup.call_args.args[0]
    assert "photo" not in item and result["extracted_data"]["total_calories"] == 196
    assert result["extracted_data"]["items"][0]["nutrition_source_id"] == "173423"


async def test_corrected_product_barcode_and_confirmed_list(cloud: None) -> None:
    with patch("core.meal_nutrition.get_nutrition_lookup") as get_lookup:
        get_lookup.return_value.lookup = AsyncMock(return_value=parse_off(off_product()))
        result = await modify_pending_meal({"items": [{"name": "Nutella", "grams": 20, "grams_source": "user_weight"}]}, "cod de bare 3017620422003")
        assert result["calories"] == pytest.approx(107.8)
        assert result["items"][0]["barcode"] == "3017620422003"
        assert result["items"][0]["grams_source"] == "user_weight"
        assert "Open Food Facts" in render_meal_preview(result)[0]
    with pytest.raises(ValueError, match="care aliment"):
        await modify_pending_meal({"items": [{"name": "A"}, {"name": "B"}]}, "cod de bare 3017620422003")


async def test_malformed_payload_and_timeout_are_safe(tmp_path: Path) -> None:
    for response in (httpx.Response(200, json={"foods": None}), httpx.Response(200, content=b"not JSON")):
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: response)) as client:
            lookup = NutritionLookup(api_key="key", enabled=True, cache_path=tmp_path / "c", client=client)
            assert await lookup.lookup({"name": "Ouă"}) is None


def test_no_sensitive_fields_in_cache_record(tmp_path: Path) -> None:
    cache = ReferenceCache(tmp_path / "c")
    cache.put("hash", parse_off(off_product()))
    with sqlite3.connect(cache.path) as conn:
        record = json.loads(conn.execute("SELECT value FROM food_references").fetchone()[0])
    assert set(record) == {"provider", "source_id", "title", "calories", "protein", "carbs", "fat", "url", "cached", "stale"}


async def test_duplicate_names_different_products_keep_separate_references(cloud: None) -> None:
    ref = parse_off(off_product())
    other = replace(ref, source_id="12345678", title="Nutella alternative", calories=400, fat=15.5)
    items = [{"name": "Nutella", "grams": 100, "brand": brand} for brand in ("Ferrero", "Other")]
    with patch("core.meal_nutrition.get_nutrition_lookup") as get_lookup:
        get_lookup.return_value.lookup = AsyncMock(side_effect=[ref, other])
        result = await enrich_meal_references({"items": items})
    assert result["items"][0]["calories"] == 539
    assert result["items"][1]["calories"] == 400
    assert [item["nutrition_source_id"] for item in result["items"]] == ["3017620422003", "12345678"]


async def test_http_timeout_not_negative_cached_and_no_sensitive_logs(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    def transport(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("private-key private-food", request=request)
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        lookup = NutritionLookup(api_key="private-key", enabled=True, cache_path=tmp_path / "c", client=client)
        assert await lookup.lookup({"name": "Ouă"}) is None
    assert "private-key" not in caplog.text and "private-food" not in caplog.text
    with sqlite3.connect(lookup.cache.path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM food_references").fetchone()[0] == 0
