"""Bridge reviewed local portions to read-only public nutrition references."""

import asyncio
from pathlib import Path
from typing import Any

from core import config
from core.food_reference import apply_food_references
from core.meal_review import normalize_meal_proposal
from core.nutrition_sources import NutritionLookup

_lookup: NutritionLookup | None = None


def get_nutrition_lookup() -> NutritionLookup:
    global _lookup
    if _lookup is None:
        _lookup = NutritionLookup(api_key=config.USDA_FDC_API_KEY,
                                  enabled=config.NUTRITION_CLOUD_ENABLED,
                                  cache_path=Path(config.NUTRITION_CACHE_PATH),
                                  ttl_days=config.NUTRITION_CACHE_TTL_DAYS,
                                  user_agent=config.OPENFOODFACTS_USER_AGENT)
    return _lookup


async def enrich_meal_references(data: dict[str, Any], user_text: str = "",
                                 previous_items: list[dict[str, Any]] | None = None,
                                 *, lookup: NutritionLookup | None = None) -> dict[str, Any]:
    if not config.NUTRITION_CLOUD_ENABLED:
        # Preserve the explicitly local-only legacy mode. Cloud mode does not
        # silently fall back to these bundled values when its API is unavailable.
        return apply_food_references(data, user_text, previous_items, estimate_missing=True)
    reviewed = normalize_meal_proposal(data, user_text, previous_items)
    references = {}
    lookup = lookup or get_nutrition_lookup()
    # Whole-meal bound as well as per-request timeouts; never hang Telegram.
    async def collect() -> None:
        for index, item in enumerate(reviewed["items"][:20]):
            reference = await lookup.lookup(item)
            if reference:
                references[index] = reference
    try:
        await asyncio.wait_for(collect(), timeout=12)
    except asyncio.TimeoutError:
        pass
    result = apply_food_references(reviewed, user_text, previous_items,
                                   estimate_missing=True, references=references)
    result["nutrition_lookup_incomplete"] = any(item["calories"] is None for item in result["items"])
    if result["nutrition_lookup_incomplete"]:
        result["review_questions"] = [
            f"Nu am date nutriționale verificate pentru «{item['name']}». Precizează prepararea, marca sau codul de bare."
            for item in result["items"] if item["calories"] is None
        ][:4]
    return result
