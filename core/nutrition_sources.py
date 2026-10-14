"""Read-only nutrition lookups. Never upload images, portions or conversation.

References are per 100 g, not measured meal nutrition. SQLite stores only public
food references and lookup identities; no meal history or credentials is cached.
"""

import asyncio
from collections import defaultdict, deque
from contextlib import closing
from dataclasses import asdict, dataclass
import hashlib
import json
import logging
import math
from pathlib import Path
import re
import sqlite3
import time
from typing import Any

import httpx

from core.meal_review import _plain

logger = logging.getLogger(__name__)
FIELDS = ("calories", "protein", "carbs", "fat")
# Translation/preparation hints only: nutrition comes from the provider.
QUERIES = {
    "oua": "egg fried", "rosie": "tomatoes raw", "paine prajita": "bread toasted",
    # Preparation proxies, always exposed by their actual provider title.
    "snitele": "chicken breast fried flour", "slanina": "pork backfat raw",
    "bacon": "bacon cooked pan fried", "pui": "chicken", "orez": "rice",
    "castravete": "cucumber raw", "paine": "bread", "cartofi": "potatoes",
    "paste": "pasta", "salata": "salad", "ardei": "peppers raw", "lapte": "milk",
    "branza": "cheese", "iaurt": "yogurt", "peste": "fish", "somon": "salmon",
    "vita": "beef", "supa": "soup", "banana": "banana raw", "mar": "apple raw",
}
PREPARATIONS = {"raw", "fried", "boiled", "grilled", "baked", "cooked", "toasted", "breaded"}
_STOP = {"and", "with", "of", "the", "a", "an", "in", "or"}


def clean_food_text(value: Any) -> str:
    """Bound a food-only field; reject URLs, control characters and prose."""
    if not isinstance(value, str) or len(value) > 120 or re.search(r"[\n\r:@/\\]", value):
        return ""
    return value.strip()


def tokens(value: str) -> set[str]:
    words = set(re.findall(r"[a-z0-9]+", _plain(value))) - _STOP
    aliases = {"eggs": "egg", "tomatoes": "tomato", "potatoes": "potato", "peppers": "pepper", "apples": "apple", "bananas": "banana"}
    return {aliases.get(word, word) for word in words}


@dataclass(frozen=True)
class FoodReference:
    provider: str
    source_id: str
    title: str
    calories: float
    protein: float
    carbs: float
    fat: float
    url: str
    cached: bool = False
    stale: bool = False


def validated_reference(provider: str, source_id: str, title: str, values: dict[str, Any], url: str) -> FoodReference | None:
    try:
        if any(isinstance(values.get(key), bool) for key in FIELDS):
            return None
        numbers = {key: float(values[key]) for key in FIELDS}
    except (KeyError, TypeError, ValueError):
        return None
    if not all(math.isfinite(value) and value >= 0 for value in numbers.values()):
        return None
    if numbers["calories"] > 950 or sum(numbers[key] for key in FIELDS[1:]) > 105:
        return None
    energy = 4 * numbers["protein"] + 4 * numbers["carbs"] + 9 * numbers["fat"]
    if abs(numbers["calories"] - energy) > max(30, energy * .30):
        return None
    return FoodReference(provider, source_id, title[:160], **numbers, url=url)


def parse_usda(food: dict[str, Any]) -> FoodReference | None:
    values: dict[str, float] = {}
    ids = {1008: "calories", 2047: "calories", 2048: "calories", 1003: "protein", 1004: "fat", 1005: "carbs"}
    entries = food.get("foodNutrients")
    if not isinstance(entries, list):
        return None
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        nutrient = entry.get("nutrient", entry)
        if not isinstance(nutrient, dict):
            continue
        nutrient_id = nutrient.get("id", entry.get("nutrientId"))
        field = ids.get(nutrient_id)
        if field is None:
            continue
        unit = str(nutrient.get("unitName", entry.get("unitName", ""))).upper()
        if unit != ("KCAL" if field == "calories" else "G"):
            continue
        values[field] = entry.get("amount", entry.get("value"))
    source_id = str(food.get("fdcId", ""))
    if not source_id.isdigit():
        return None
    return validated_reference("USDA FoodData Central", source_id, str(food.get("description", "")), values,
                               f"https://fdc.nal.usda.gov/food-details/{source_id}/nutrients")


def parse_off(product: dict[str, Any]) -> FoodReference | None:
    if product.get("nutrition_data_per") == "100ml" or product.get("no_nutrition_data") == "on" or product.get("no_nutrition_data") is True:
        return None  # Never assume 100 ml == 100 g.
    nutrients = product.get("nutriments")
    code = str(product.get("code", ""))
    if not isinstance(nutrients, dict) or not re.fullmatch(r"\d{8,14}", code):
        return None
    values = {"calories": nutrients.get("energy-kcal_100g"), "protein": nutrients.get("proteins_100g"),
              "carbs": nutrients.get("carbohydrates_100g"), "fat": nutrients.get("fat_100g")}
    if values["calories"] is None and nutrients.get("energy-kj_100g") is not None:
        try:
            values["calories"] = float(nutrients["energy-kj_100g"]) / 4.184
        except (TypeError, ValueError):
            return None
    title = str(product.get("product_name_ro") or product.get("product_name") or "")
    if not title:
        return None
    return validated_reference("Open Food Facts", code, title, values, f"https://world.openfoodfacts.org/product/{code}")


class ReferenceCache:
    """Short SQLite transactions, called off the asyncio event loop."""

    def __init__(self, path: Path, ttl_days: int = 30) -> None:
        self.path = path
        self.ttl = ttl_days * 86400

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=2)
        conn.execute("CREATE TABLE IF NOT EXISTS food_references (key TEXT PRIMARY KEY, value TEXT, saved_at REAL NOT NULL)")
        return conn

    def get(self, key: str, stale: bool = False) -> tuple[bool, FoodReference | None]:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT value, saved_at FROM food_references WHERE key = ?", (key,)).fetchone()
        if not row:
            return False, None
        age = time.time() - row[1]
        ttl = self.ttl if row[0] else 900
        if age > (self.ttl * 3 if stale and row[0] else ttl):
            return False, None
        if not row[0]:
            return True, None
        try:
            data = json.loads(row[0])
            reference = validated_reference(data["provider"], data["source_id"], data["title"], data, data["url"])
            if reference is None:
                return False, None
            return True, FoodReference(**{**asdict(reference), "cached": True, "stale": age > self.ttl})
        except (TypeError, ValueError, KeyError):
            return False, None

    def put(self, key: str, reference: FoodReference | None) -> None:
        with closing(self._connect()) as conn:
            conn.execute("INSERT OR REPLACE INTO food_references VALUES (?, ?, ?)",
                         (key, json.dumps(asdict(reference), ensure_ascii=False) if reference else None, time.time()))
            conn.commit()


class NutritionLookup:
    def __init__(self, *, api_key: str = "", cache_path: Path, enabled: bool = False,
                 user_agent: str = "Lora/1.0 (personal nutrition assistant)", ttl_days: int = 30,
                 client: httpx.AsyncClient | None = None) -> None:
        self.api_key = api_key
        self.enabled = enabled
        self.user_agent = user_agent
        self.cache = ReferenceCache(cache_path, ttl_days)
        self.client = client
        self.requests: dict[str, deque[float]] = defaultdict(deque)
        self.cooldown: dict[str, float] = {}
        self.lock = asyncio.Lock()

    async def _cache_get(self, key: str, stale: bool = False) -> tuple[bool, FoodReference | None]:
        try:
            return await asyncio.to_thread(self.cache.get, key, stale)
        except (OSError, sqlite3.Error):
            logger.warning("Nutrition cache unavailable (read)")
            return False, None

    async def _cache_put(self, key: str, reference: FoodReference | None) -> None:
        try:
            await asyncio.to_thread(self.cache.put, key, reference)
        except (OSError, sqlite3.Error):
            logger.warning("Nutrition cache unavailable (write)")

    async def _request(self, provider: str, url: str, params: dict[str, Any]) -> dict[str, Any] | None:
        limit, window = {"usda": (900, 3600), "off_product": (15, 60), "off_search": (10, 60)}[provider]
        now = time.monotonic()
        queue = self.requests[provider]
        while queue and queue[0] < now - window:
            queue.popleft()
        if len(queue) >= limit or self.cooldown.get(provider, 0) > now:
            return None  # Never delay a Telegram response waiting for a rate window.
        queue.append(now)
        headers = {"User-Agent": self.user_agent}
        if provider == "usda":
            headers["X-Api-Key"] = self.api_key  # Not in URLs/logs.
        method = "POST" if provider == "usda" else "GET"
        arguments = {"json": params} if provider == "usda" else {"params": params}
        try:
            if self.client is not None:
                response = await self.client.request(method, url, **arguments, headers=headers, timeout=5)
            else:
                async with httpx.AsyncClient(timeout=5, follow_redirects=False) as client:
                    response = await client.request(method, url, **arguments, headers=headers)
            if response.status_code in {429, 401, 403} or response.status_code >= 500:
                self.cooldown[provider] = now + (3600 if provider == "usda" and response.status_code == 429 else 60)
            response.raise_for_status()
            result = response.json()
            return result if isinstance(result, dict) else None
        except httpx.HTTPStatusError as error:
            logger.warning("Nutrition provider unavailable: %s status=%d", provider, error.response.status_code)
            return None
        except (httpx.HTTPError, ValueError) as error:
            # Never log exception text: it may contain food queries or credentials.
            logger.warning("Nutrition provider unavailable: %s error=%s", provider, type(error).__name__)
            return None

    @staticmethod
    def _select(query: str, candidates: list[FoodReference]) -> FoodReference | None:
        requested = tokens(query)
        ranked: list[tuple[float, FoodReference]] = []
        for candidate in candidates:
            observed = tokens(candidate.title)
            if not requested or not requested <= observed:
                continue
            # A generic ingredient must not match a substitute, baby food,
            # mixed dish or a different preparation merely containing its name.
            excluded = {"meatless", "substitute", "imitation", "vegan", "vegetarian", "babyfood", "powder", "dried", "dehydrated", "soup", "sandwich", "salad", "noodle", "noodles", "pizza"}
            if (observed & excluded) - requested:
                continue
            if "fried" in requested and observed & {"boiled", "poached", "grilled"}:
                continue
            if ("raw" in requested and observed & {"fried", "boiled", "cooked", "baked", "grilled"}) or ("raw" in observed and requested & {"fried", "boiled", "cooked", "baked", "grilled"}):
                continue
            score = len(requested) / max(len(observed), 1)
            ranked.append((score, candidate))
        ranked.sort(key=lambda pair: pair[0], reverse=True)
        if not ranked:
            return None
        best = ranked[0][1]
        if len(ranked) > 1 and abs(ranked[0][0] - ranked[1][0]) < .12:
            other = ranked[1][1]
            if any(abs(getattr(best, field) - getattr(other, field)) > max(2, getattr(best, field) * .15) for field in FIELDS):
                return None  # Multiple materially different preparations/products.
        return best

    async def lookup(self, item: dict[str, Any]) -> FoodReference | None:
        name = clean_food_text(item.get("name"))
        brand = clean_food_text(item.get("brand"))
        barcode = str(item.get("barcode") or "")
        if barcode and not re.fullmatch(r"\d{8,14}", barcode):
            return None
        if not name or item.get("uncertain") or "neidentificat" in _plain(name):
            return None
        query = clean_food_text(item.get("nutrition_query")) or QUERIES.get(_plain(name), name)
        preparation = item.get("preparation")
        if preparation in PREPARATIONS:
            query = " ".join(word for word in query.split() if word not in PREPARATIONS) + " " + preparation
        # A barcode/product request must not fall back to a different generic food.
        packaged = bool(barcode or brand or item.get("packaged"))
        if packaged:
            query = name
        identity = json.dumps(["v2", query, brand, barcode, packaged], ensure_ascii=False)
        key = hashlib.sha256(identity.encode()).hexdigest()
        async with self.lock:  # Coalesce concurrent identical requests and rate counters.
            found, cached = await self._cache_get(key)
            if found:
                return cached
            _, stale = await self._cache_get(key, stale=True)
            if not self.enabled:
                return stale
            result: FoodReference | None = None
            responded = False
            if packaged:
                fields = "code,product_name,product_name_ro,brands,nutriments,nutrition_data_per,no_nutrition_data"
                if barcode:
                    response = await self._request("off_product", f"https://world.openfoodfacts.org/api/v3/product/{barcode}.json", {"fields": fields})
                    if response is not None:
                        product = response.get("product")
                        if isinstance(product, dict) and str(product.get("code")) == barcode:
                            result = parse_off(product)
                else:
                    # OFF currently documents this as its legacy keyword-search endpoint.
                    response = await self._request("off_search", "https://world.openfoodfacts.org/cgi/search.pl",
                                                   {"search_terms": " ".join(filter(None, [name, brand])), "search_simple": 1, "action": "process", "json": 1, "page_size": 10, "fields": fields})
                    if response is not None:
                        candidates = []
                        products = response.get("products")
                        for product in (products if isinstance(products, list) else [])[:10]:
                            if not isinstance(product, dict) or (brand and not tokens(brand) <= tokens(str(product.get("brands", "")))):
                                continue
                            reference = parse_off(product)
                            if reference:
                                candidates.append(reference)
                        result = self._select(name, candidates)
                responded = response is not None
            elif self.api_key:
                response = await self._request("usda", "https://api.nal.usda.gov/fdc/v1/foods/search",
                                               {"query": query, "dataType": ["Foundation", "SR Legacy", "Survey (FNDDS)"], "pageSize": 12})
                responded = response is not None
                if response is not None:
                    foods = response.get("foods")
                    candidates = [ref for food in (foods if isinstance(foods, list) else [])[:12] if isinstance(food, dict) and (ref := parse_usda(food)) is not None]
                    result = self._select(query, candidates)
            if result is not None:
                await self._cache_put(key, result)
                return result
            if not responded:
                return stale
            await self._cache_put(key, None)  # Only cache genuine empty/ambiguous results.
            return None
