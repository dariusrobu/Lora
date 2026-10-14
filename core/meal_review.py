"""Validate photo-meal proposals and keep user quantities above model guesses."""

import math
import re
import unicodedata
from typing import Any


def _plain(value: str) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFKD", value.lower())
        if not unicodedata.combining(char)
    )


_FOOD_NAMES = {
    "snitel": "Șnițele", "schnitzel": "Șnițele", "breaded meat": "Șnițele",
    "oua": "Ouă", "ou ": "Ouă", "egg": "Ouă", "slanin": "Slănină", "bacon": "Bacon", "pork fat": "Slănină",
    "rosie": "Roșie", "rosii": "Roșie", "castrav": "Castravete",
    "orez": "Orez", "pui": "Pui", "paine": "Pâine", "toast": "Pâine prăjită",
    "cartof": "Cartofi", "paste": "Paste", "salata": "Salată",
    "tomato": "Roșie", "cucumber": "Castravete", "rice": "Orez", "chicken": "Pui",
    "bread": "Pâine", "potato": "Cartofi", "pasta": "Paste", "salad": "Salată",
    "pepper": "Ardei", "ardei": "Ardei", "cheese": "Brânză", "branza": "Brânză",
    "yogurt": "Iaurt", "iaurt": "Iaurt", "milk": "Lapte", "lapte": "Lapte",
    "fish": "Pește", "peste": "Pește", "salmon": "Somon", "somon": "Somon",
    "beef": "Vită", "vita": "Vită", "soup": "Supă", "supa": "Supă",
}
_QUANTITY = re.compile(
    r"(?P<amount>\d+(?:[.,]\d+)?|doua|doi|trei|patru|un|o)\s*"
    r"(?P<unit>kilograme|grame|kg|gr|g|bucati|buc|felii)?\b\s*"
    r"(?:mici\s+|mari\s+|de\s+)*(?P<food>.+)$"
)
_WORDS = {"o": 1, "un": 1, "doi": 2, "doua": 2, "trei": 3, "patru": 4}


def _food_key(name: str) -> str:
    plain = _plain(name).strip()
    for canonical in _FOOD_NAMES.values():
        if plain == _plain(canonical):
            return canonical
    for stem, canonical in _FOOD_NAMES.items():
        if stem in plain + " ":
            return canonical
    return plain


def user_food_claims(text: str) -> tuple[bool, list[dict[str, Any]]]:
    """Parse a complete meal statement or quantity edits, without inventing grams."""
    plain = _plain(text).strip().rstrip(".!?")
    prefix = re.match(r"^(?:am mancat|am consumat|masa (?:este|a fost))\s+", plain)
    complete = prefix is not None
    body = plain[prefix.end():] if prefix else plain
    claims: list[dict[str, Any]] = []
    for part in re.split(r",(?!\d)|\s+si\s+|\s+plus\s+", body):
        part = re.sub(r"^(?:adauga(?: si)?|pune|schimba cu|inlocuieste cu)\s+", "", part.strip())
        trailing = re.match(r"(.+?)\s+(?:(?:are|au|este|e|:)\s*)?(\d+(?:[.,]\d+)?\s*(?:g|gr|grame|kg))$", part)
        if trailing:
            part = f"{trailing.group(2)} {trailing.group(1)}"
        match = _QUANTITY.match(part)
        food = match.group("food") if match else part
        food = re.sub(r"^(?:bucati mici|bucati|putina|putin)\s+(?:de\s+)?", "", food).strip()
        if not food or (not complete and not match):
            continue
        hints: dict[str, Any] = {}
        barcode = re.search(r"\s+(?:cod(?:ul)? de bare|barcode|ean)\s*[:=]?\s*(\d{8,14})$", food)
        if barcode:
            hints.update(barcode=barcode.group(1), packaged=True)
            food = food[:barcode.start()].strip()
        brand = re.search(r"\s+(?:marca|brand)\s+(.+)$", food)
        if brand:
            hints.update(brand=brand.group(1).strip()[:80], packaged=True)
            food = food[:brand.start()].strip()
        for pattern, preparation in ((r"\bfiert\w*\b", "boiled"), (r"\bprajit\w*\b|\bochiuri\b", "fried"),
                                     (r"\bcrud\w*\b", "raw"), (r"\bla gratar\b", "grilled"), (r"\bla cuptor\b", "baked")):
            if re.search(pattern, food):
                hints["preparation"] = preparation
                break
        claim: dict[str, Any] = {"name": _food_key(food), **hints}
        if match:
            amount = match.group("amount")
            value = float(_WORDS[amount]) if amount in _WORDS else float(amount.replace(",", "."))
            unit = match.group("unit") or "buc"
            if unit in {"g", "gr", "grame", "kg", "kilograme"}:
                claim["grams"] = value * (1000 if unit in {"kg", "kilograme"} else 1)
            else:
                claim["count"] = value
                claim["count_unit"] = "felii" if unit == "felii" else "bucăți"
        claims.append(claim)
    return complete, claims


def _number(value: Any, maximum: float) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and 0 <= number <= maximum else None


def normalize_meal_proposal(
    data: dict[str, Any], user_text: str = "", previous_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Normalize totals, retain uncertainty and enforce explicitly supplied foods/weights.

    Gram ranges are model estimates, never a calibrated confidence interval.
    Nutrition remains estimated even when the user supplies a measured weight.
    """
    raw_items = data.get("items")
    if not isinstance(raw_items, list):
        raise ValueError("Lista de alimente nu este validă.")
    raw_items = [dict(item) for item in raw_items if isinstance(item, dict) and isinstance(item.get("name"), str) and item["name"].strip()]
    complete, claims = user_food_claims(user_text)
    if complete and claims:
        # A complete user description replaces the photo guess, not appends to it.
        selected = []
        for claim in claims:
            candidate = next((item for item in raw_items if _food_key(item["name"]) == claim["name"]), {})
            selected.append({**candidate, "name": claim["name"]})
        raw_items = selected
    if not raw_items:
        raise ValueError("Nu am identificat alimente. Spune-mi ce ai mâncat.")

    previous = {_food_key(item["name"]): item for item in previous_items or [] if isinstance(item.get("name"), str)}
    items = []
    questions = []
    for raw in raw_items:
        name = raw["name"].strip()[:100]
        key = _food_key(name)
        if key in _FOOD_NAMES.values():
            name = key
        claim = next((entry for entry in claims if entry["name"] == key), {})
        prior = previous.get(key, {})
        model_grams = _number(raw.get("grams"), 3000)
        grams = model_grams if model_grams and model_grams > 0 else None
        source = "photo_estimate"
        user_grams = claim.get("grams")
        if user_grams is None and not complete and prior.get("grams_source") == "user_weight":
            user_grams = prior.get("grams")
        if user_grams is not None:
            grams = _number(user_grams, 3000)
            if not grams:
                raise ValueError(f"Gramajul pentru {name} nu este valid.")
            source = "user_weight"
        macros = {field: _number(raw.get(field), 30000 if field == "calories" else 3000) for field in ("calories", "protein", "carbs", "fat")}
        claimed_count = _number(claim.get("count"), 100)
        model_count = _number(raw.get("count"), 100)
        count_factor = 1.0
        if source != "user_weight" and claimed_count and model_count and claimed_count != model_count:
            count_factor = claimed_count / model_count
            grams = grams * count_factor if grams else None
            macros = {field: value * count_factor if value is not None else None for field, value in macros.items()}
        # Rescale the model's per-portion estimates when it ignored a user weight.
        if source == "user_weight" and model_grams and grams != model_grams:
            macros = {field: (value * grams / model_grams if value is not None else None) for field, value in macros.items()}
        reliable = grams is not None and all(value is not None for value in macros.values())
        if reliable:
            nutrient_mass = sum(macros[field] for field in ("protein", "carbs", "fat"))
            if nutrient_mass > grams * 1.1 or macros["calories"] > grams * 10:
                reliable = False
            else:
                energy = 4 * macros["protein"] + 4 * macros["carbs"] + 9 * macros["fat"]
                if energy == 0 and key not in {"apa", "cafea", "ceai"}:
                    reliable = False
                if abs(macros["calories"] - energy) > max(20, energy * 0.25):
                    macros["calories"] = energy
        if not reliable:
            macros = {field: None for field in macros}
            questions.append(f"Verifică porția și prepararea pentru {name}.")
        item: dict[str, Any] = {
            "name": name, "grams": grams, "grams_source": source,
            **{field: round(value, 1) if value is not None else None for field, value in macros.items()},
        }
        # Preserve bounded lookup identity across correction/re-estimation. Never
        # forward a caption or free-form conversation to nutrition providers.
        for field in ("brand", "nutrition_query"):
            text = claim.get(field, raw.get(field))
            if isinstance(text, str) and len(text) <= 120 and not re.search(r"[\n\r:@/\\]", text):
                item[field] = text.strip()
        barcode = str(claim.get("barcode", raw.get("barcode")) or "")
        if re.fullmatch(r"\d{8,14}", barcode):
            item["barcode"] = barcode
        preparation = claim.get("preparation", raw.get("preparation"))
        if preparation in {"raw", "fried", "boiled", "grilled", "baked", "cooked", "toasted", "breaded"}:
            item["preparation"] = preparation
        if claim.get("packaged", raw.get("packaged")) is True:
            item["packaged"] = True
        if source != "user_weight" and raw.get("portion_method") in {"vision", "standard_serving"}:
            item["portion_method"] = raw["portion_method"]
        if raw.get("uncertain") and not complete:
            item["uncertain"] = True
        count = _number(claim.get("count", raw.get("count", prior.get("count"))), 100)
        if count:
            item.update(count=count, count_unit=claim.get("count_unit", "bucăți"))
        lower = _number(raw.get("grams_min"), 3000)
        upper = _number(raw.get("grams_max"), 3000)
        lower = lower * count_factor if lower else None
        upper = upper * count_factor if upper else None
        if source != "user_weight" and lower and upper and lower <= (grams or 0) <= upper and lower < upper:
            item.update(grams_min=lower, grams_max=upper)
        if raw.get("uncertain") and not complete:
            questions.append(f"Este corect identificat alimentul «{name}»?")
        items.append(item)

    # Unknown nutrition must not silently become a zero-calorie meal.
    needs_details = any(item["calories"] is None for item in items)
    result: dict[str, Any] = {
        "description": ", ".join(item["name"] for item in items)[:250],
        "meal_type": data.get("meal_type") if data.get("meal_type") in {"mic_dejun", "pranz", "cina", "gustare", "masa"} else "masa",
        "items": items, "nutrition_estimated": True, "needs_portion_details": needs_details,
        "review_questions": list(dict.fromkeys(questions))[:4],
    }
    for field in ("calories", "protein", "carbs", "fat"):
        result[field] = None if needs_details else round(sum(item[field] for item in items), 1)
    return result
