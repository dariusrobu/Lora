"""Local visual portion estimates: proposals with ranges, never measurements."""

import asyncio
import base64
import json
import logging
import re
from typing import Any

from core.meal_review import _number

logger = logging.getLogger(__name__)

_ENGLISH_NAMES = {
    "Ouă": "fried eggs", "Șnițele": "breaded fried meat pieces",
    "Slănină": "pork backfat pieces", "Bacon": "bacon",
    "Roșie": "tomato", "Pâine prăjită": "toast",
}


async def estimate_visual_portions(
    client: Any, model: str, photo_bytes: bytes, items: list[dict[str, Any]],
    user_text: str = "",
) -> list[dict[str, Any]]:
    """Estimate each identified food against the same photo; preserve user grams.

    Only portion mass is requested. No nutrition, translations or example
    numeric weights contaminate this separate small-model task.
    """
    result = [dict(item) for item in items]
    candidates = {
        index: item for index, item in enumerate(result)
        if item.get("grams_source") != "user_weight" and not item.get("uncertain")
        and "neidentificate" not in item.get("name", "")
    }
    if not candidates or not photo_bytes:
        return result
    inventory = [
        {"id": index, "food": _ENGLISH_NAMES.get(item["name"], item["name"]), "count": item.get("count")}
        for index, item in candidates.items()
    ]
    prompt = f"""Estimate edible portion mass for these foods in the PHOTO:
{json.dumps(inventory, ensure_ascii=False)}
User correction: {user_text or 'none'}
Use food size, thickness and visible piece counts; eggs/utensils are only approximate scale clues.
Estimate the TOTAL grams for each listed food, not grams per piece. Small schnitzel pieces are not full-size schnitzels. Count only the user-described eaten portion if stated.
Do not infer measured weights or unseen food. Provide a broad plausible range.
Output ONLY one line per food: id|estimated_grams|low_grams|high_grams
Use numbers without units. Omit a food if it cannot be estimated. No explanations."""
    try:
        response = await asyncio.wait_for(client.chat(
            model=model,
            messages=[{"role": "user", "content": prompt, "images": [base64.b64encode(photo_bytes).decode("utf-8")]}],
            options={"temperature": 0.2, "num_predict": 200, "num_ctx": 4096},
            keep_alive="1m",
        ), timeout=30)
        text = response.get("message", {}).get("content", "")
        for match in re.finditer(r"(?m)^\s*(\d+)\s*\|\s*([\d.,]+)\s*\|\s*([\d.,]+)\s*\|\s*([\d.,]+)\s*$", text):
            index = int(match.group(1))
            if index not in candidates:
                continue
            center, lower, upper = [_number(value, 3000) for value in match.groups()[1:]]
            if not center or not lower or not upper or not lower <= center <= upper:
                continue
            # A narrow model range must not suggest calibrated precision.
            lower = min(lower, center * 0.65)
            upper = max(upper, center * 1.4)
            result[index].update(grams=center, grams_min=round(lower), grams_max=round(upper), portion_method="vision")
        logger.info("Visual portion estimates: model=%s estimated=%d requested=%d", model, sum(item.get("portion_method") == "vision" for item in result), len(candidates))
    except Exception as error:
        logger.warning("Visual portion estimation unavailable: %s; using labelled serving assumptions", type(error).__name__)
    return result
