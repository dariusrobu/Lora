"""Public-reference smoke test, no photos, Telegram messages or meal writes.

Run: .venv/bin/python -m scripts.check_nutrition_sources [--demo]
The optional public DEMO_KEY is used ONLY by this diagnostic, never by Lora.
"""

import argparse
import asyncio
from pathlib import Path
import tempfile

from core import config
from core.meal_nutrition import enrich_meal_references
from core.nutrition_sources import NutritionLookup


async def check(demo: bool = False, meal: bool = False) -> int:
    failures = 0
    with tempfile.TemporaryDirectory(prefix="lora-nutrition-check-") as temporary:
        lookup = NutritionLookup(api_key=config.USDA_FDC_API_KEY or ("DEMO_KEY" if demo else ""),
                                  enabled=True, cache_path=Path(temporary) / "references.sqlite3",
                                  user_agent=config.OPENFOODFACTS_USER_AGENT)
        for provider, food in (("USDA", {"name": "Ouă"}),
                               ("Open Food Facts", {"name": "Nutella", "barcode": "3017620422003"})):
            if provider == "USDA" and not lookup.api_key:
                print("USDA: lipsește USDA_FDC_API_KEY; verificarea a fost omisă.")
                continue
            reference = await lookup.lookup(food)
            if reference:
                print(f"{provider}: OK · {reference.title} · {reference.calories:g} kcal/100 g · ID {reference.source_id}")
                cached = await lookup.lookup(food)
                print(f"{provider}: cache {'OK' if cached and cached.cached else 'FAIL'}")
            else:
                failures += 1
                print(f"{provider}: fără rezultat verificat (rețea, limită, cheie sau potrivire ambiguă).")
        if meal:
            proposal = await enrich_meal_references({"items": [
                {"name": "Ouă", "grams": 100, "count": 2, "portion_method": "vision"},
                {"name": "Șnițele", "grams": 120, "count": 3, "portion_method": "vision"},
                {"name": "Slănină", "grams": 25, "portion_method": "standard_serving"},
                {"name": "Roșie", "grams": 123, "count": 1, "portion_method": "vision"},
            ]}, lookup=lookup)
            for item in proposal["items"]:
                print(f"Flux masă (fără salvare): {item['name']} · {item.get('nutrition_reference', 'referință negăsită')} · {item['calories']} kcal")
            print(f"Total exemplu: {proposal['calories']} kcal; complet: {not proposal['needs_portion_details']}")
    return failures


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help="Test USDA with its public, strictly limited DEMO_KEY")
    parser.add_argument("--meal", action="store_true", help="Also dry-run a public four-food example, without saving a meal")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(check(args.demo, args.meal)))
