"""Offline food references, not model-generated nutrition or measured portions.

Per-100g values are USDA FoodData Central SR Legacy records, fetched/checked
2026-10-07. No API calls or user data leave the machine at runtime. Breaded
chicken is only a proxy for schnitzel; pork backfat is a proxy for slanina.
Recipes, cooking fat and brands vary. All calculated nutrition is estimated.
Piece ranges below are broad serving assumptions, not image measurements.
"""

import re
from typing import Any

from core.meal_review import _food_key, _plain, normalize_meal_proposal, user_food_claims
from core.nutrition_sources import FoodReference

# name: (FDC ID, kcal, protein, carbs, fat per 100g)
_REFERENCES = {
    "Ouă": (173423, 196.0, 13.61, 0.83, 14.84),  # fried egg
    "Roșie": (170457, 18.0, 0.88, 3.89, 0.20),
    "Pâine prăjită": (174925, 290.0, 9.0, 54.5, 4.0),
    "Șnițele": (170756, 230.0, 23.5, 6.03, 12.4),  # preparation proxy
    "Slănină": (167811, 812.0, 2.92, 0.0, 88.7),  # not lean bacon/ham
    "Bacon": (168322, 468.0, 33.9, 1.7, 35.1),  # pan-fried, pre-sliced bacon
}
_PIECES = {"Ouă": (46, 35, 65), "Roșie": (123, 60, 200), "Pâine prăjită": (28, 15, 45)}
_SERVINGS = {
    "Ouă": (46, 25, 100), "Roșie": (123, 60, 220), "Pâine prăjită": (28, 15, 60),
    "Șnițele": (120, 60, 220), "Slănină": (25, 10, 60), "Bacon": (30, 10, 70),
}
_VISIBLE = {
    r"\beggs?\b": "Ouă", r"\btoast(?:ed bread)?\b": "Pâine prăjită",
    r"\btomato(?:es)?\b": "Roșie", r"\bbacon\b": "Bacon", r"\bpork fat\b": "Slănină",
    r"\bschnitzels?\b|\bbreaded (?:fried )?(?:meat|chicken)\b": "Șnițele",
    r"\bfried (?:food|item|pieces?)\b": "Alimente prăjite — neidentificate",
}
_NON_FOOD = re.compile(
    r"^(?:(?:a|an|the)\s+)?(?:(?:white|metal|wooden|plastic)\s+)?"
    r"(?:knives|knife|forks?|spoons?|plates?|utensils?|napkins?|cutting boards?|tables?|cups?|glasses?)$"
)


def has_food_reference(name: str) -> bool:
    """Whether a normalized food has an offline nutrition reference."""
    return _food_key(name) in _REFERENCES


def foods_from_visual_description(description: str) -> list[dict[str, Any]]:
    """Keep a short English inventory, without translating it through another LLM."""
    text = description.lower()
    items: list[dict[str, Any]] = []
    for pattern, name in _VISIBLE.items():
        match = re.search(pattern, text)
        if not match:
            continue
        count_match = re.search(r"(?:\b(\d+|one|two|three|four)\s+(?:fried\s+|slices? of\s+)?)$", text[max(0, match.start() - 35):match.start()])
        count = None
        if count_match:
            value = count_match.group(1)
            count = {"one": 1, "two": 2, "three": 3, "four": 4}.get(value)
            if count is None:
                count = int(value)
        item: dict[str, Any] = {"name": name, "grams": None}
        if count:
            item["count"] = count
        if name in {"Bacon", "Slănină", "Alimente prăjite — neidentificate"}:
            item["uncertain"] = True
        items.append(item)
    # Do not silently drop foods outside the small reference catalogue.
    inventory = re.sub(r"^(?:the visible foods (?:are|include)|foods?:)\s*", "", text.strip())
    for part in re.split(r",|\s+and\s+|\n", inventory):
        part = part.strip(" .-*\n")
        if not part or _NON_FOOD.fullmatch(part) or any(re.search(pattern, part) for pattern in _VISIBLE):
            continue
        items.append({"name": part[:100], "grams": None, "uncertain": True})
    return items


def apply_food_references(
    data: dict[str, Any], user_text: str = "", previous_items: list[dict[str, Any]] | None = None,
    *, estimate_missing: bool = False,
    references: dict[int, FoodReference] | None = None,
) -> dict[str, Any]:
    """Calculate supported foods from an offline reference; unknown portions stay unknown."""
    proposal = normalize_meal_proposal(data, user_text, previous_items)
    _, claims = user_food_claims(user_text)
    for index, item in enumerate(proposal["items"]):
        external = references.get(index) if references is not None else None
        reference = _REFERENCES.get(item["name"]) if references is None else None
        count = item.get("count")
        visual = item.get("portion_method") == "vision"
        if visual and count and item["name"] in _PIECES:
            _, lower, upper = _PIECES[item["name"]]
            per_piece = (item.get("grams") or 0) / count
            if not lower <= per_piece <= upper:
                visual = False
        if visual and count and item["name"] == "Șnițele" and "mici" in _plain(user_text):
            if not 20 <= (item.get("grams") or 0) / count <= 60:
                visual = False
        if item["grams_source"] != "user_weight" and not visual and count and item["name"] in _PIECES:
            center, lower, upper = _PIECES[item["name"]]
            item.update(grams=center * count, grams_min=lower * count, grams_max=upper * count, portion_method="standard_serving")
        elif item["grams_source"] != "user_weight" and not visual and count and item["name"] == "Șnițele" and "mici" in _plain(user_text):
            # Small pieces are not full schnitzels. Always show the broad range.
            item.update(grams=40 * count, grams_min=20 * count, grams_max=60 * count, portion_method="standard_serving")
        if not item.get("grams") and estimate_missing and item["name"] in _SERVINGS:
            center, lower, upper = _SERVINGS[item["name"]]
            item.update(grams=center, grams_min=lower, grams_max=upper, portion_method="standard_serving")
        grams = item.get("grams")
        if references is not None and not external:
            # With cloud references enabled, model-generated macros and the old
            # bundled six-food catalogue are NEVER used as a hidden fallback.
            item.update({field: None for field in ("calories", "protein", "carbs", "fat")})
            continue
        if not grams:
            continue
        if external:
            fdc_id, calories, protein, carbs, fat = external.source_id, external.calories, external.protein, external.carbs, external.fat
        elif reference:
            fdc_id, calories, protein, carbs, fat = reference
        else:
            continue
        for field, value in zip(("calories", "protein", "carbs", "fat"), (calories, protein, carbs, fat)):
            item[field] = round(value * grams / 100, 1)
        item["nutrition_reference"] = f"{external.provider} · {external.title}" if external else f"USDA FDC {fdc_id} (aproximare)"
        if external:
            item.update(nutrition_source_url=external.url, nutrition_source_id=external.source_id,
                        nutrition_provider=external.provider, nutrition_cached=external.cached,
                        nutrition_stale=external.stale)
    result = normalize_meal_proposal({**proposal, "items": proposal["items"]}, user_text, previous_items)
    for item, prior in zip(result["items"], proposal["items"]):
        for field in ("nutrition_reference", "nutrition_source_url", "nutrition_source_id", "nutrition_provider", "nutrition_cached", "nutrition_stale"):
            if field in prior:
                item[field] = prior[field]
    # Keep unresolved identification questions, rather than hiding uncertainty
    # after the numeric calculation. Explicit user food lists resolve identity.
    complete, _ = user_food_claims(user_text)
    if not complete:
        result["review_questions"] = list(dict.fromkeys(result["review_questions"] + [question for question in proposal["review_questions"] if "identificat" in question]))[:4]
    if claims:
        result["description"] = ", ".join(item["name"] for item in result["items"])
    return result
