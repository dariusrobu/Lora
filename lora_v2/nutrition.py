"""Ground AI meal estimates in read-only per-100 g food references."""

import asyncio
import re
import unicodedata
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from core.nutrition_sources import FoodReference, NutritionLookup
from lora_v2.agent import Candidate
from lora_v2.config import Settings
from lora_v2.models import MealItem


class FoodLookup(Protocol):
    async def lookup(self, item: dict[str, str]) -> FoodReference | None: ...


def _plain(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.casefold())
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def _identity(name: str) -> dict[str, str]:
    """Pass only an ingredient and preparation hint to the reference lookup."""
    simple = _plain(name)
    preparation = "raw" if re.search(r"\bcrud\w*\b", simple) else (
        "cooked" if re.search(r"\bgatit\w*\b|\bfiert\w*\b", simple) else ""
    )
    food = re.sub(r"\s*\((?:crud|crude|gătit|gătite)\)\s*$", "", name, flags=re.IGNORECASE).strip()
    plain_food = _plain(food)
    names = {
        "piept de pui": "chicken breast", "orez": "rice", "pui": "chicken",
        "oua": "egg", "ou": "egg", "cartofi": "potatoes", "banana": "banana",
    }
    identity = {"name": food, "nutrition_query": names.get(plain_food, food)}
    if preparation:
        identity["preparation"] = preparation
    return identity


def _compatible_reference(name: str, title: str) -> bool:
    """Reject a cooking method, coating, or variety the user did not state."""
    stated = _plain(name)
    observed = _plain(title)
    forbidden = {
        "breaded": ("pane", "snitel"), "battered": ("pane", "snitel"),
        "tenders": ("tenders",), "nuggets": ("nuggets",),
        "microwaved": ("microunde",), "fried": ("prajit",),
        "grilled": ("gratar",), "roasted": ("copt", "cuptor", "fript"),
        "boiled": ("fiert",), "steamed": ("abur",),
        "white": ("alb",), "brown": ("brun", "integral"),
        "skin": ("piele",), "sauce": ("sos",),
    }
    return all(not re.search(rf"\b{word}\b", observed) or
               any(hint in stated for hint in hints)
               for word, hints in forbidden.items())


@lru_cache(maxsize=2)
def _configured_lookup(api_key: str, cache_path: str, user_agent: str) -> NutritionLookup:
    return NutritionLookup(api_key=api_key, cache_path=Path(cache_path),
                           user_agent=user_agent, enabled=True)


def _scaled(value: float, grams: Decimal) -> Decimal:
    return (Decimal(str(value)) * grams / Decimal("100")).quantize(Decimal("0.1"))


async def enrich_meal_candidate(
    candidate: Candidate, settings: Settings, lookup: FoodLookup | None = None,
) -> Candidate:
    """Discard model macros; fill only matched reference values for known weights."""
    if candidate.type != "log_meal":
        return candidate
    items = [item.model_copy(update={
        "calories": None, "protein_g": None, "carbs_g": None, "fat_g": None,
        "nutrition_provider": None, "nutrition_source_id": None,
        "nutrition_source_title": None, "nutrition_source_url": None,
    }) for item in candidate.items or []]
    references: dict[int, FoodReference] = {}
    if settings.nutrition_enabled:
        active_lookup = lookup or _configured_lookup(
            settings.usda_api_key, settings.nutrition_cache_path, settings.nutrition_user_agent,
        )

        async def collect() -> None:
            for index, item in enumerate(items[:20]):
                if item.grams is not None and item.name.strip():
                    reference = await active_lookup.lookup(_identity(item.name))
                    if reference is not None and _compatible_reference(item.name, reference.title):
                        references[index] = reference

        try:
            await asyncio.wait_for(collect(), timeout=12)
        except asyncio.TimeoutError:
            pass
    enriched: list[MealItem] = []
    missing: list[str] = []
    for index, item in enumerate(items):
        reference = references.get(index)
        if reference is None or item.grams is None:
            missing.append(item.name)
            enriched.append(item)
            continue
        enriched.append(item.model_copy(update={
            "calories": _scaled(reference.calories, item.grams),
            "protein_g": _scaled(reference.protein, item.grams),
            "carbs_g": _scaled(reference.carbs, item.grams),
            "fat_g": _scaled(reference.fat, item.grams),
            "nutrition_provider": reference.provider,
            "nutrition_source_id": reference.source_id,
            "nutrition_source_title": reference.title,
            "nutrition_source_url": reference.url,
        }))
    candidate.items = enriched
    if missing:
        detail = ("Valorile nutriționale rămân necompletate pentru " +
                  ", ".join(f"«{name}»" for name in missing[:3]) +
                  ". Spune metoda de preparare sau tipul alimentului pentru o potrivire mai precisă.")
        candidate.missing_information = " ".join(filter(None, [candidate.missing_information, detail]))
    return candidate
