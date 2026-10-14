import asyncio
import base64
import io
import json
import logging
import os
import re
from pathlib import Path
from uuid import uuid4
from typing import Any, Dict, Optional, Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.callback_utils import make_callback_data
from bot.formatter import escape_md, safe_markdown
from core import config
from core.food_reference import apply_food_references, foods_from_visual_description, has_food_reference
from core.food_portions import estimate_visual_portions
from core.meal_review import normalize_meal_proposal, user_food_claims
from core.meal_nutrition import enrich_meal_references
from core.state import clear_state, get_state, set_state
from db.queries.finance import log_transaction
from ollama import AsyncClient

logger = logging.getLogger(__name__)

OLLAMA_HOST = getattr(config, "OLLAMA_HOST", os.getenv("OLLAMA_HOST", "http://localhost:11434"))
OLLAMA_MODEL = getattr(config, "OLLAMA_MODEL", os.getenv("OLLAMA_MODEL", "llama3.2:3b"))
OLLAMA_STRUCTURED_MODEL = getattr(
    config, "OLLAMA_STRUCTURED_MODEL", os.getenv("OLLAMA_STRUCTURED_MODEL", "qwen2.5:7b")
)
OLLAMA_VISION_MODEL = getattr(
    config, "OLLAMA_VISION_MODEL", os.getenv("OLLAMA_VISION_MODEL", "moondream")
)
OLLAMA_FOOD_VISION_MODEL = getattr(config, "OLLAMA_FOOD_VISION_MODEL", OLLAMA_VISION_MODEL)

_ollama_client = AsyncClient(host=OLLAMA_HOST)


def save_optimized_receipt(photo_bytes: bytes) -> Optional[str]:
    """Save a compact local copy of a receipt and return its relative path."""
    if not photo_bytes:
        return None
    storage_path = Path(getattr(config, "RECEIPTS_STORAGE_PATH", "data/finance/receipts"))
    storage_path.mkdir(parents=True, exist_ok=True)
    relative_path = Path("data") / "finance" / "receipts" / f"{uuid4().hex}.webp"
    output_path = storage_path / relative_path.name
    try:
        from PIL import Image, ImageOps

        with Image.open(io.BytesIO(photo_bytes)) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
            image.save(output_path, "WEBP", quality=80, method=6)
        return str(relative_path)
    except Exception:
        logger.exception("Failed to optimize local receipt image")
        return None


def _clean_json_from_text(raw: str) -> Dict[str, Any]:
    """Extracts and parses JSON object from model output."""
    raw = raw.strip()
    if raw.startswith("```"):
        # Strip markdown code blocks
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(raw[start : end + 1])
        raise


_RECEIPT_PRICE_ROW = re.compile(
    r"^\s*\d+(?:[.,]\d+)?\s*(?:buc(?:ăți)?\.?|pcs?\.?|kg|l)?\s*[x×]\s*"
    r"(?P<unit_price>\d+(?:[.,]\d+)?)(?:\s*(?:lei|ron))?"
    r"(?:\s+(?P<line_total>\d+(?:[.,]\d+)?))?\s*[a-z]?\s*$",
    re.IGNORECASE,
)
_RECEIPT_METADATA = (
    "total", "subtotal", "tva", "cota", "numerar", "cash", "card", "pos", "rest",
    "operator", "casier", "cif", "c.i.f", "data", "ora", "valoare timbru", "bon fiscal",
)


def _extract_receipt_items_from_ocr(ocr_text: str) -> list[Dict[str, Any]]:
    """Recovers receipt items from common Romanian OCR layouts without an LLM.

    Some cash registers print the quantity/price row *before* the product name.
    This deterministic fallback prevents one missed LLM item from changing the
    printed total or silently dropping an expense.
    """
    lines = [line.strip() for line in ocr_text.splitlines() if line.strip()]
    recovered: list[Dict[str, Any]] = []

    for index, line in enumerate(lines):
        match = _RECEIPT_PRICE_ROW.match(line)
        if not match:
            continue

        product_name = ""
        for candidate in lines[index + 1 :]:
            if _RECEIPT_PRICE_ROW.match(candidate):
                break
            candidate_lower = candidate.lower()
            if any(marker in candidate_lower for marker in _RECEIPT_METADATA):
                continue
            if len(candidate) >= 3:
                product_name = candidate
                break

        if not product_name:
            continue

        try:
            # The line total is present on some printers; for a one-unit row,
            # the unit price is already the amount to record.
            amount = match.group("line_total") or match.group("unit_price")
            price = round(float(amount.replace(",", ".")), 2)
        except ValueError:
            continue
        if price <= 0:
            continue
        recovered.append({"name": product_name, "price": price, "category": "altele"})

    return recovered


def _merge_receipt_items(
    model_items: list[Dict[str, Any]], ocr_items: list[Dict[str, Any]]
) -> list[Dict[str, Any]]:
    """Adds OCR-recovered items that the model did not return."""
    merged = list(model_items)
    for ocr_item in ocr_items:
        try:
            ocr_price = float(ocr_item.get("price") or 0)
        except (TypeError, ValueError):
            continue
        normalized_ocr_name = re.sub(r"\W+", "", str(ocr_item.get("name") or "").lower())
        duplicate = False
        for model_item in merged:
            try:
                float(model_item.get("price") or 0)
            except (TypeError, ValueError):
                continue
            normalized_model_name = re.sub(
                r"\W+", "", str(model_item.get("name") or "").lower()
            )
            shared_words = set(re.findall(r"[a-zăâîșț]{2,}", normalized_ocr_name)) & set(
                re.findall(r"[a-zăâîșț]{2,}", normalized_model_name)
            )
            same_product = (
                normalized_ocr_name == normalized_model_name
                or normalized_ocr_name in normalized_model_name
                or normalized_model_name in normalized_ocr_name
                or len(shared_words) >= 3
            )
            if same_product:
                # OCR has an explicit price row. Prefer it when the LLM joined
                # this product to the price of the following product.
                model_item["price"] = ocr_price
                if not model_item.get("category"):
                    model_item["category"] = ocr_item["category"]
                duplicate = True
                break
        if not duplicate:
            merged.append(ocr_item)
    return merged


def _normalize_image_for_ocr(photo_bytes: bytes) -> bytes:
    """Preprocesses image for optimal OCR on receipts:
    - Auto-rotates using EXIF orientation (crucial for mobile phone photos).
    - Converts to grayscale.
    - Upscales low-resolution web images to ~300 DPI equivalent so dot-matrix text is sharp.
    - Enhances contrast to separate faint thermal ink from background.
    """
    try:
        from PIL import Image, ImageOps, ImageEnhance

        img = Image.open(io.BytesIO(photo_bytes))
        img = ImageOps.exif_transpose(img)

        # 1. Grayscale
        gray = img.convert("L")

        # 2. Upscale if image is too small (receipts from web/compressed photos are often < 1200px)
        w, h = gray.size
        if w < 1200 or h < 1200:
            scale = min(2.5, max(1200 / w, 1200 / h))
            new_w = int(w * scale)
            new_h = int(h * scale)
            gray = gray.resize((new_w, new_h), Image.Resampling.LANCZOS)

        # 3. Enhance contrast to separate faded thermal ink
        enhancer = ImageEnhance.Contrast(gray)
        enhanced = enhancer.enhance(1.6)

        out = io.BytesIO()
        enhanced.save(out, format="PNG")
        return out.getvalue()
    except Exception as e:
        logger.debug(f"Image normalization failed: {e}")
        return photo_bytes


def get_apple_ocr_path() -> Optional[str]:
    """Returns absolute path to native Apple Vision OCR binary, auto-compiling if needed on macOS."""
    if os.uname().sysname != "Darwin":
        return None
    bin_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bin"))
    apple_ocr_bin = os.path.join(bin_dir, "apple_ocr")
    if os.path.exists(apple_ocr_bin) and os.access(apple_ocr_bin, os.X_OK):
        return apple_ocr_bin
    apple_ocr_src = os.path.join(bin_dir, "apple_ocr.swift")
    if os.path.exists(apple_ocr_src):
        try:
            import subprocess

            subprocess.run(
                ["swiftc", "-O", "-o", apple_ocr_bin, apple_ocr_src],
                check=True,
                timeout=30,
            )
            return apple_ocr_bin
        except Exception as e:
            logger.warning(f"Could not compile apple_ocr: {e}")
    return None


async def extract_text_ocr(photo_bytes: bytes) -> str:
    """Extracts text from image bytes using Apple Vision Neural OCR (100% native, Apple Neural Engine hardware-accelerated)."""
    if not photo_bytes:
        return ""

    # Primary engine: Apple Vision Neural OCR
    apple_ocr_bin = get_apple_ocr_path()
    if apple_ocr_bin:
        try:
            proc = await asyncio.create_subprocess_exec(
                apple_ocr_bin,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(
                proc.communicate(input=photo_bytes), timeout=8.0
            )
            text = stdout.decode("utf-8", errors="ignore").strip()
            if text:
                logger.info(
                    f"🍏 Apple Vision Neural OCR extracted {len(text)} characters:\n{text[:200]}..."
                )
                return text
            else:
                logger.info("🍏 Apple Vision Neural OCR finished: no text detected.")
                return ""
        except Exception as e:
            logger.error(f"Apple Vision OCR failed: {e}")

    # Fallback for non-macOS environments
    try:
        normalized_bytes = await asyncio.to_thread(_normalize_image_for_ocr, photo_bytes)
        proc = await asyncio.create_subprocess_exec(
            "tesseract",
            "stdin",
            "stdout",
            "-l",
            "ron+eng",
            "--psm",
            "6",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(
            proc.communicate(input=normalized_bytes), timeout=10.0
        )
        return stdout.decode("utf-8", errors="ignore").strip()
    except Exception as e:
        logger.debug(f"Fallback OCR failed: {e}")
        return ""


async def _call_local_llm_json(
    prompt: str, max_tokens: int | None = None, model_names: list[str] | None = None,
) -> Dict[str, Any]:
    """Calls local Ollama model with structured JSON enforcement and fallback."""
    models_to_try = model_names or [
        OLLAMA_STRUCTURED_MODEL,
        "qwen2.5:7b",
        "qwen2.5:3b",
        OLLAMA_MODEL,
    ]
    # Remove duplicates while preserving order
    unique_models = []
    for m in models_to_try:
        if m and m not in unique_models:
            unique_models.append(m)

    last_err = None
    for model_name in unique_models:
        try:
            options = {"temperature": 0.2, "num_predict": max_tokens, "num_ctx": 4096} if max_tokens else {}
            res = await _ollama_client.chat(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                format="json",
                **({"think": False} if model_name.startswith("qwen3-vl") and "instruct" not in model_name else {}),
                options=options,
                keep_alive="1m" if max_tokens else None,
            )
            content = res.get("message", {}).get("content", "")
            return _clean_json_from_text(content)
        except Exception as e:
            logger.debug(f"Ollama structured call with {model_name} failed: {e}")
            last_err = e

    raise RuntimeError(f"All local Ollama models failed for structured parsing: {last_err}")


async def describe_image_with_vision(
    photo_bytes: bytes,
    prompt: str = (
        "Name only the visible foods in this photo, with visible piece counts if clear. "
        "Distinguish toast from breaded meat and eggs from other fried foods. "
        "Mention uncertainty when ambiguous. "
        "Do not invent side dishes, oil, sauces or hidden ingredients. "
        "A photo cannot provide measured grams or exact calories. "
        "Keep under 70 words. For non-food describe the object."
    ),
    *,
    food_photo: bool = False,
) -> str:
    """Uses a local Ollama vision model (moondream, llava, etc.) to extract a rich visual description."""
    b64_img = base64.b64encode(photo_bytes).decode("utf-8")
    vision_models = [
        OLLAMA_FOOD_VISION_MODEL if food_photo else OLLAMA_VISION_MODEL,
        OLLAMA_VISION_MODEL, "moondream", "llava",
    ]
    unique_models = []
    for m in vision_models:
        if m and m not in unique_models:
            unique_models.append(m)

    for vm in unique_models:
        try:
            res = await _ollama_client.chat(
                model=vm,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                        "images": [b64_img],
                    }
                ],
                options={"temperature": 0, "num_predict": 180},
            )
            content = res.get("message", {}).get("content", "").strip()
            if content:
                logger.info(f"Local vision model ({vm}) described image: {content[:150]}...")
                return content
        except Exception as e:
            logger.debug(f"Ollama vision model {vm} description failed: {e}")

    return ""


def _food_result(data: Dict[str, Any], user_text: str = "", *, references: bool = False, reviewed: bool = False) -> Dict[str, Any]:
    proposal = data if reviewed else apply_food_references(data, user_text, estimate_missing=True) if references else normalize_meal_proposal(data, user_text)
    return {
        "type": "food", "confidence": 0.5,
        "extracted_data": {
            **proposal,
            **{f"total_{key}": proposal[key] for key in ("calories", "protein", "carbs", "fat")},
        },
        "reply": f"Verifică alimentele și porțiile: {proposal['description']}",
    }


async def analyze_food_photo(photo_bytes: bytes, caption: str | None = None) -> Dict[str, Any] | None:
    """Use a modern local vision model directly, avoiding lossy text translation.

    The legacy vision-description pipeline remains available for older models.
    No model is downloaded automatically by an incoming photo.
    """
    if not OLLAMA_FOOD_VISION_MODEL.startswith(("qwen3-vl", "qwen2.5vl")):
        return None
    # This small model identifies food better in a short inventory than when
    # asked to simultaneously translate, weigh and invent nutrition in JSON.
    prompt = (
        "List all visible edible foods in English, separated by commas. No other sentences. "
        "Include piece counts only when clearly visible. Distinguish toast from breaded meat. "
        "Include food on the nearby cutting board too. "
        "For unidentified fried items say fried food. No weights, nutrition, recipes or hidden ingredients. "
        "If this is not a food photo say NOT FOOD."
    )
    try:
        response = await asyncio.wait_for(_ollama_client.chat(
            model=OLLAMA_FOOD_VISION_MODEL,
            messages=[{"role": "user", "content": prompt, "images": [base64.b64encode(photo_bytes).decode("utf-8")]}],
            options={"temperature": 0.2, "num_predict": 150, "num_ctx": 4096},
            **({"think": False} if OLLAMA_FOOD_VISION_MODEL.startswith("qwen3-vl") and "instruct" not in OLLAMA_FOOD_VISION_MODEL else {}),
            keep_alive="1m",
        ), timeout=75)
        description = response.get("message", {}).get("content", "")
        complete, claims = user_food_claims(caption or "")
        items = claims if complete and claims else foods_from_visual_description(description)
        if items and "NOT FOOD" not in description.upper():
            reviewed = normalize_meal_proposal({"items": items}, caption or "")
            items = await estimate_visual_portions(_ollama_client, OLLAMA_FOOD_VISION_MODEL, photo_bytes, reviewed["items"], caption or "")
            proposal = await enrich_meal_references({"items": items}, caption or "")
            result = _food_result(proposal, reviewed=True)
            logger.info("Local food vision: model=%s items=%d needs_details=%s", OLLAMA_FOOD_VISION_MODEL, len(result["extracted_data"]["items"]), result["extracted_data"]["needs_portion_details"])
            return result
    except Exception as error:
        logger.warning("Direct local food vision failed: %s", type(error).__name__)
    return None


async def analyze_food_from_vision(
    vision_description: str, caption: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Uses local structured LLM (qwen2.5:7b) to determine if vision description represents food,
    and calculates realistic grams, calories, and macronutrients.
    """
    if not vision_description:
        return None

    complete, claims = user_food_claims(caption or "")
    prompt = f"""Extract a food proposal from visible evidence. JSON only.
Visual observations: {vision_description}
User caption (authoritative about what was actually eaten): {caption or 'none'}
User-confirmed food list: {json.dumps(claims if complete else [], ensure_ascii=False)}
Rules:
- If the user lists what they ate, REPLACE the visual guesses with ONLY that list. Copy those food names exactly.
- Otherwise include only observed foods. Prefer simple food names, not a narrative. Mark ambiguous foods uncertain=true.
- Do not invent sauces, cooking oil, sides, or ingredients hidden in a dish.
- This is NOT a measurement: estimate edible grams for the specified pieces/size, with grams_min/grams_max. Counted, identified foods CAN have approximate ranges without weighing; do not set null just because there is no scale. Ask for truly unknown portions using null, never zero. Do not assume an entire serving platter was eaten.
- Explicit user grams/kg are authoritative. All calorie/macronutrient values remain estimates.
- Match preparation (breaded fried meat is not plain grilled chicken). Numeric fields are JSON numbers WITHOUT units; protein/carbs/fat are grams. Calories approximate 4*protein+4*carbs+9*fat.
- If not food, is_food=false. meal_type must be mic_dejun, pranz, cina, gustare or masa.
Example schema (replace the example values with actual estimates):
{{"is_food":true,"meal_type":"masa","items":[{{"name":"Food name","count":1,"uncertain":false,"grams":100,"grams_min":80,"grams_max":120,"calories":150,"protein":20,"carbs":4,"fat":6}}]}}"""

    try:
        data = await _call_local_llm_json(prompt, max_tokens=2048)
        if data.get("is_food") is True:
            return _food_result(await enrich_meal_references(data, caption or ""), reviewed=True)
    except Exception as e:
        logger.warning(f"Error parsing food nutrition from vision description: {e}")

    return None


async def analyze_image(
    client: Any = None, photo_bytes: bytes = b"", caption: Optional[str] = None
) -> Dict[str, Any]:
    """Analyzes image locally via Tesseract OCR + Local Ollama LLM / Vision model.
    
    Extracts individual items, prices, and categories from receipts/invoices,
    or identifies food with nutritional calculation, menus, workouts, notes, book covers.
    """
    try:
        # Step 1: Run local OCR
        ocr_text = await extract_text_ocr(photo_bytes)
        logger.info(f"Local OCR extracted {len(ocr_text)} characters:\n{ocr_text}")

        receipt_indicators = (
            "total", "lei", "ron", "tva", "bon", "fiscal", "discount",
            "kaufland", "profi", "lidl", "mega", "carrefour", "casa", "numerar", "rest",
            "lukoil", "omv", "petrom", "rompetrol", "mol", "benzina", "motorina", "diesel",
            "statie", "peco", "cif", "c.i.f.", "operator"
        )
        is_probable_receipt = (
            len(ocr_text.strip()) >= 15
            and any(kw in ocr_text.lower() for kw in receipt_indicators)
        )

        receipt_prompt = f"""Ești Lora, asistent expert în citirea bonurilor fiscale românești.
Analizează textul extras prin OCR de pe un bon fiscal:
\"\"\"{ocr_text}\"\"\"
{f"Text adițional de la utilizator: {caption}" if caption else ""}

Instrucțiuni precise:
1. COMERCIANT (merchant):
   - Numele magazinului / societății se află în ANTET (primele linii înainte de 'Operator', 'CIF', 'C.I.F.' sau 'RO').
   - Ex: 'SC FERAL IMPEX SRL', 'IKEA', 'Lidl', 'Profi', 'Kaufland', 'Lukoil', 'OMV', 'Petrom', etc.
   - NICIODATĂ nu folosi numele unui produs comercializat (ex: Ursus, Coca Cola) drept comerciant!
2. PRODUSE (items):
   - Produsele încep DUPĂ antet și după linia 'Operator'.
   - Pe bonurile românești, fiecare articol poate avea denumirea pe un rând urmată de rândul 'cantitate X preț = total_linie' SAU invers: rândul cu cantitatea și prețul poate apărea înaintea denumirii. Leagă întotdeauna aceste două rânduri într-un singur produs.
   - Extrage TOATE produsele: fiecare rând de cantitate/preț trebuie să aibă un articol corespondent în lista finală.
   - REGULĂ ABSOLUTĂ ANTI-HALUCINAȚIE: Extrage EXCLUSIV articolele care sunt scrise pe bon. NU inventa produse!
   - Ignoră complet rândurile fiscale, cote de TVA sau detalii de plată (TVA, COTA, TOTAL, NUMERAR, CASH, POS, REST, CASIER, TRZ, BUC, OPERATOR) — acestea NU sunt produse!
   - Corectează inteligent literele deformate din OCR pentru denumirea fiecărui produs găsit pe rândul său.
3. PREȚURI ȘI TOTAL:
   - Extrage prețul net plătit pentru fiecare produs (valoarea de pe rândul respectiv).
   - Dacă sub un produs există linie de DISCOUNT sau REDUCERE, scade discountul din prețul produsului.
   - total_amount: suma totală a produselor cumpărate.
4. CATEGORII:
   - 'transport': combustibil, benzină, motorină, diesel, GPL, rovinietă, parcare, spălătorie auto, produse auto (Lukoil, OMV, Petrom, Rompetrol, Mol).
   - 'mâncare': alimente, băuturi, bere, sucuri, lactate, mezeluri, oțet, dulciuri, înghețată, apă etc.
   - 'țigări': STRICT tutun, vape, e-cigarette, capsule Vuse/Glo/Iqos/Heets/Terea, țigarete (bateriile sau băuturile NU sunt țigări!).
   - 'utilități': baterii, detergenți, becuri, produse pentru casă sau curățenie.
   - 'sănătate': medicamente, produse farmacie.
   - 'shopping': haine, electronice, decorațiuni.
   - 'altele': garanție ambalaj/sticlă, taxe diverse.

Răspunde STRICT cu un JSON valid (fără markdown):
{{
  "type": "receipt",
  "confidence": 0.98,
  "extracted_data": {{
    "merchant": "Nume Magazin / Societate",
    "total_amount": 0.0,
    "items": [
      {{"name": "Denumire Produs", "price": 0.0, "category": "mâncare"}}
    ]
  }},
  "reply": "Sumar scurt în limba română"
}}"""

        # Step 2: If probable receipt, parse it immediately with local structured LLM
        if is_probable_receipt:
            try:
                parsed = await _call_local_llm_json(receipt_prompt)
                logger.info(f"Local LLM parsed receipt result: {parsed}")
                if parsed and parsed.get("type") == "receipt":
                    ext_data = parsed.setdefault("extracted_data", {})
                    items = ext_data.get("items") or []

                    # 1. Normalize merchant from OCR context if needed
                    low_ocr = ocr_text.lower()
                    if "profi" in low_ocr:
                        ext_data["merchant"] = "Profi"
                    elif "kaufland" in low_ocr:
                        ext_data["merchant"] = "Kaufland"
                    elif "lidl" in low_ocr:
                        ext_data["merchant"] = "Lidl"
                    elif "carrefour" in low_ocr:
                        ext_data["merchant"] = "Carrefour"
                    elif "mega image" in low_ocr or ("mega" in low_ocr and "profi" not in low_ocr):
                        ext_data["merchant"] = "Mega Image"
                    elif "penny" in low_ocr:
                        ext_data["merchant"] = "Penny"
                    elif "auchan" in low_ocr:
                        ext_data["merchant"] = "Auchan"
                    elif "ikea" in low_ocr:
                        ext_data["merchant"] = "IKEA"
                    elif "lukoil" in low_ocr:
                        ext_data["merchant"] = "Lukoil"
                    elif "omv" in low_ocr:
                        ext_data["merchant"] = "OMV"
                    elif "petrom" in low_ocr:
                        ext_data["merchant"] = "Petrom"
                    elif "rompetrol" in low_ocr:
                        ext_data["merchant"] = "Rompetrol"
                    elif "mol" in low_ocr:
                        ext_data["merchant"] = "MOL"

                    # Prevent merchant being an item name
                    current_merchant = (ext_data.get("merchant") or "").strip()
                    for it in items:
                        it_name = (it.get("name") or "").strip()
                        if it_name and current_merchant and current_merchant.lower() in it_name.lower():
                            lines = [ln.strip() for ln in ocr_text.splitlines() if len(ln.strip()) >= 3 and not any(k in ln.lower() for k in ["total", "bon", "cif", "operator"])]
                            if lines:
                                ext_data["merchant"] = lines[0]
                            break

                    # 2. Recover price/name rows deterministically, then normalize items and categories.
                    # This covers receipt layouts where the price row precedes the product name.
                    ocr_items = _extract_receipt_items_from_ocr(ocr_text)
                    items = _merge_receipt_items(items, ocr_items)
                    ext_data["items"] = items
                    for it in items:
                        name_low = (it.get("name") or "").lower()
                        if any(kw in name_low for kw in ["baterie", "baterii"]):
                            it["category"] = "utilități"
                        elif any(kw in name_low for kw in ["benzina", "benzină", "motorina", "motorină", "diesel", "gpl", "euro luk", "carburant", "rovinieta", "rovinietă", "spalatorie", "parcare"]):
                            it["category"] = "transport"
                        elif any(kw in name_low for kw in ["garantie", "garanție"]):
                            it["category"] = "altele"
                        elif any(kw in name_low for kw in ["bere", "otet", "oțet", "cidru", "apa", "apă", "suc", "lapte", "paine", "pâine", "vin", "gum", "orbit"]):
                            it["category"] = "mâncare"
                        elif any(kw in name_low for kw in ["vuse", "glo", "iqos", "caps", "heets", "terea", "tigari", "țigări", "tutun", "vape"]):
                            it["category"] = "țigări"

                        if "vise" in name_low:
                            it["name"] = it["name"].replace("VISE", "Vuse").replace("Vise", "Vuse").replace("vise", "vuse")
                            it["category"] = "țigări"

                    # 3. Mathematical validation. The printed receipt total is authoritative:
                    # an incomplete item list must never lower it.
                    if items:
                        computed_total = round(sum(float(it.get("price") or 0.0) for it in items), 2)
                        current_total = float(ext_data.get("total_amount") or 0.0)
                        if current_total == 0.0:
                            ext_data["total_amount"] = computed_total
                        elif abs(computed_total - current_total) > 0.05:
                            logger.warning(
                                "Receipt items sum to %.2f, but printed total is %.2f; keeping printed total.",
                                computed_total,
                                current_total,
                            )

                    # 4. Generate clean reply
                    merchant_name = ext_data.get("merchant", "Magazin")
                    item_strs = [f"{it.get('name')} ({float(it.get('price') or 0):.2f} RON)" for it in items]
                    summary_items = ", ".join(item_strs)
                    parsed["reply"] = f"Bon {merchant_name}: {summary_items}. Total: {float(ext_data.get('total_amount') or 0):.2f} RON."
                    ext_data["ocr_text"] = ocr_text

                return parsed
            except Exception as e:
                logger.error(f"Error parsing OCR receipt with local LLM: {e}")

        # Step 3: Run local vision model to inspect visual scene (especially for food / objects)
        direct_food_result = await analyze_food_photo(photo_bytes, caption)
        if direct_food_result:
            return direct_food_result
        vision_desc = await describe_image_with_vision(photo_bytes, food_photo=True)
        if vision_desc:
            food_result = await analyze_food_from_vision(vision_desc, caption)
            if food_result:
                return food_result

        # Step 4: If OCR had text and wasn't a receipt or food, try general parsing
        if len(ocr_text.strip()) >= 5:
            general_prompt = f"""Ești Lora, asistentul inteligent al utilizatorului.
Am extras următorul text din imagine:
\"\"\"{ocr_text}\"\"\"
{f"Text adițional de la utilizator: {caption}" if caption else ""}

Clasifică imaginea în una din categoriile:
- 'menu' (meniu de restaurant / bar)
- 'workout_screenshot' (captură ecran smartwatch sau aplicație de sport cu durată, km, calorii)
- 'book_cover' (copertă carte: title, author)
- 'handwritten_notes' (notițe sau text: text)
- 'other' (diverse)

Răspunde STRICT cu un JSON valid:
{{
  "type": "handwritten_notes" | "workout_screenshot" | "book_cover" | "menu" | "other",
  "confidence": 0.8,
  "extracted_data": {{}},
  "reply": "Sumar"
}}"""
            try:
                parsed = await _call_local_llm_json(general_prompt)
                if parsed and parsed.get("type") != "other":
                    return parsed
            except Exception as e:
                logger.debug(f"General text classification failed: {e}")

            return {
                "type": "handwritten_notes",
                "confidence": 0.6,
                "extracted_data": {"text": ocr_text.strip()},
                "reply": "Am extras textul din imagine.",
            }

        # Step 5: If vision model gave a description but not food
        if vision_desc:
            return {
                "type": "other",
                "confidence": 0.7,
                "extracted_data": {"description": vision_desc},
                "reply": f"Am analizat imaginea: {vision_desc}",
            }

        return {
            "type": "other",
            "confidence": 0.3,
            "extracted_data": {},
            "reply": "Am analizat imaginea local, dar nu am putut identifica un bon lizibil sau mâncare.",
        }

    except Exception as e:
        logger.error(f"Error analyzing image locally: {e}", exc_info=True)
        return {"type": "error", "reply": f"Eroare la procesarea imaginii: {e}"}


def render_receipt_preview(extra: Dict[str, Any]) -> Tuple[str, InlineKeyboardMarkup]:
    """Generates the MarkdownV2 preview message and inline confirmation keyboard for a receipt."""
    merchant = extra.get("description") or "Necunoscut"
    clean_items = extra.get("items") or []
    final_amount = float(extra.get("amount") or 0.0)
    category = extra.get("category") or "altele"

    if clean_items:
        lines = [f"🧾 Am extras bonul de la *{escape_md(str(merchant))}*:\n"]
        for item in clean_items[:12]:
            i_name = escape_md(str(item.get("name") or "Articol"))
            i_price = float(item.get("price") or 0.0)
            i_cat = escape_md(str(item.get("category") or category))
            lines.append(f"• {i_name} — `{i_price:.2f} RON` _({i_cat})_")

        if len(clean_items) > 12:
            lines.append(f"• _...și încă {len(clean_items) - 12} produse_")

        lines.append(f"\n💰 *Total*: `{final_amount:.2f} RON` ({len(clean_items)} produse)")
        if extra.get("items_reliable", True):
            lines.append("\n_Dorești să înregistrez aceste cheltuieli pe categorii?_")
        else:
            lines.append("\n⚠️ Sumele produselor nu se potrivesc cu totalul tipărit. Voi înregistra doar totalul bonului, ca să nu dublez cheltuiala.")
        lines.append("💡 _Trimite un mesaj pentru corecții (ex: „pune pâinea la 5 lei”, „magazinul e Lukoil”) sau confirmă direct._")
        msg = "\n".join(lines)
    else:
        msg = (
            f"🧾 Am extras un bon de la *{escape_md(str(merchant))}*.\n\n"
            f"Suma: `{final_amount:.2f} RON`\n"
            f"Categorie: {escape_md(category)}\n\n"
            f"_Dorești să înregistrez această cheltuială?_\n"
            f"💡 _Trimite un mesaj pentru corecții sau confirmă direct._"
        )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Confirmă tot",
                    callback_data=make_callback_data("vision", "confirm"),
                ),
                InlineKeyboardButton(
                    "❌ Anulează",
                    callback_data=make_callback_data("vision", "cancel"),
                ),
            ]
        ]
    )
    return msg, keyboard


async def modify_pending_receipt(extra: Dict[str, Any], instruction: str) -> Dict[str, Any]:
    """Applies natural language corrections to pending receipt using local LLM."""
    merchant = extra.get("description", "Necunoscut")
    items = extra.get("items", [])
    total_amount = extra.get("amount", 0.0)
    category = extra.get("category", "altele")

    items_repr = json.dumps(items, ensure_ascii=False)
    prompt = f"""Ești un asistent financiar inteligent care corectează datele extrase dintr-un bon fiscal la cererea utilizatorului.

Date curente ale bonului:
- Comerciant / Magazin: "{merchant}"
- Categorie generală: "{category}"
- Total curent: {total_amount} RON
- Produse ({len(items)}):
{items_repr}

Instrucțiunea utilizatorului pentru corectare:
"{instruction}"

Reguli:
1. Aplică strict modificările solicitate de utilizator:
   - Poate schimba comerciantul (ex: "comerciantul e Lukoil" -> merchant: "Lukoil").
   - Poate schimba categoria unui produs sau a bonului (categorii recomandate: transport, mâncare, utilități, sănătate, shopping, distracție, educație, țigări, altele).
   - Poate ajusta prețul sau denumirea oricărui produs existent.
   - Poate adăuga un produs nou sau șterge un produs.
2. Păstrează toate celelalte produse existente nemodificate dacă utilizatorul nu a cerut schimbarea lor.
3. Recalculează total_amount ca sumă a prețurilor tuturor produselor (sau setează-l dacă utilizatorul specifică un total explicit).

Răspunde STRICT cu un obiect JSON în următorul format:
{{
  "merchant": "nume magazin",
  "category": "categorie generala",
  "items": [
    {{"name": "Denumire Produs", "price": 12.34, "category": "categorie"}}
  ],
  "total_amount": 12.34
}}"""

    try:
        updated_data = await _call_local_llm_json(prompt)
    except Exception as e:
        logger.warning(f"Local LLM failed to modify receipt JSON: {e}")
        return extra

    new_extra = dict(extra)

    # Update merchant
    if updated_data.get("merchant") and isinstance(updated_data["merchant"], str):
        new_extra["description"] = updated_data["merchant"].strip()

    # Update category
    if updated_data.get("category") and isinstance(updated_data["category"], str):
        new_extra["category"] = updated_data["category"].strip().lower()

    # Update items
    raw_items = updated_data.get("items")
    if isinstance(raw_items, list):
        clean_items = []
        for it in raw_items:
            if isinstance(it, dict) and "name" in it:
                try:
                    price = float(it.get("price") or 0.0)
                    clean_items.append({
                        "name": str(it["name"]).strip(),
                        "price": round(price, 2),
                        "category": str(it.get("category") or new_extra["category"]).lower(),
                    })
                except (ValueError, TypeError):
                    continue
        if clean_items:
            new_extra["items"] = clean_items
            items_sum = round(sum(i["price"] for i in clean_items), 2)
            new_extra["amount"] = items_sum
        elif "total_amount" in updated_data:
            try:
                new_extra["amount"] = round(float(updated_data["total_amount"]), 2)
            except (ValueError, TypeError):
                pass
    elif "total_amount" in updated_data:
        try:
            new_extra["amount"] = round(float(updated_data["total_amount"]), 2)
        except (ValueError, TypeError):
            pass

    return new_extra


def render_meal_preview(extra: Dict[str, Any]) -> Tuple[str, InlineKeyboardMarkup]:
    """Generates the MarkdownV2 preview message and inline keyboard for an identified meal."""
    description = extra.get("description") or "Masă"
    def value(field: str, unit: str) -> str:
        number = extra.get(field)
        return "necunoscut" if number is None else f"{number:g}{unit}" if isinstance(number, (float, int)) else f"{number}{unit}"
    items = extra.get("items") or []

    lines = [
        f"🥗 *Verifică masa:* {escape_md(str(description))}\n",
        f"🔥 *Calorii estimate*: `{value('calories', ' kcal')}`",
        f"📊 *Macros estimați*: `{value('protein', 'g P')}` · `{value('carbs', 'g C')}` · `{value('fat', 'g F')}`",
    ]

    if items:
        lines.append("\n*Alimente și porții:*")
        for it in items:
            it_name = it.get("name") or "Aliment"
            it_g = it.get("grams")
            it_cal = it.get("calories")

            if it.get("grams_source") == "user_weight":
                portion = f"{it_g:g} g, specificat de tine"
            elif it.get("grams_min") and it.get("grams_max"):
                portion = f"aprox. {it_g:g} g ({it['grams_min']:g}–{it['grams_max']:g} g)"
                if it.get("portion_method") == "standard_serving":
                    portion += " · porție orientativă"
            elif it_g:
                portion = f"aproximativ {it_g:g} g"
            else:
                portion = "gramaj necunoscut"
            if it.get("count"):
                count_unit = it.get("count_unit", "bucăți")
                if it["count"] == 1 and count_unit == "bucăți":
                    count_unit = "bucată"
                portion = f"{it['count']:g} {count_unit} · {portion}"
            calorie_text = f"{it_cal:g} kcal" if it_cal is not None else "calorii necunoscute"
            lines.append(f"• *{escape_md(str(it_name))}*: {escape_md(portion)} · {escape_md(calorie_text)}")

    lines.append("\n_Gramajele din poză sunt estimări, nu cântărire. Verifică și ce parte ai mâncat._")
    if any(item.get("nutrition_reference") for item in items):
        lines.append("_Caloriile folosesc alimente de referință; rețeta și prepararea pot schimba rezultatul._")
        providers = {item.get("nutrition_provider") for item in items}
        if "USDA FoodData Central" in providers:
            lines.append("Sursă: USDA FoodData Central.")
        if "Open Food Facts" in providers:
            lines.append("Sursă: Open Food Facts · ODbL.")
        for item in items:
            if item.get("nutrition_provider"):
                lines.append(f"↳ {escape_md(str(item['name']))}: {escape_md(str(item['nutrition_reference']))}")
        if any(item.get("nutrition_stale") for item in items):
            lines.append("_Am folosit date din cache; sursa online nu a putut fi actualizată._")
    for question in extra.get("review_questions") or []:
        lines.append(f"• {escape_md(str(question))}")
    if extra.get("needs_portion_details"):
        if extra.get("nutrition_lookup_incomplete"):
            lines.append("\n*Lipsesc date nutriționale verificate pentru o parte din masă.* Nu trebuie să cântărești alimentele.")
        else:
            lines.append("\n*Nu pot estima încă toată masa.* Spune-mi ce este alimentul neidentificat sau cum a fost preparat; nu trebuie să-l cântărești.")
    else:
        lines.append("\n_Confirmi alimentele, porțiile și estimarea pentru salvare?_")
    lines.append("💡 Poți corecta: „am mâncat 3 șnițele mici, 2 ouă și o roșie” sau „puiul are 180 g”.")
    msg = safe_markdown("\n".join(lines))

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Înregistrează masa",
                    callback_data=make_callback_data("vision", "confirm"),
                ),
                InlineKeyboardButton(
                    "❌ Anulează",
                    callback_data=make_callback_data("vision", "cancel"),
                ),
            ]
        ]
    )
    return msg, keyboard


async def modify_pending_meal(extra: Dict[str, Any], instruction: str, *, photo_bytes: bytes | None = None) -> Dict[str, Any]:
    """Applies natural language corrections to pending meal (ingredients, grams, macros, meal type) using local LLM."""
    desc = extra.get("description", "Masă")
    items = extra.get("items", [])
    meal_type = extra.get("meal_type", "pranz")
    calories = extra.get("calories", 0)
    protein = extra.get("protein", 0)
    carbs = extra.get("carbs", 0)
    fat = extra.get("fat", 0)

    complete, claims = user_food_claims(instruction)
    barcode_match = re.fullmatch(r"\s*(?:cod(?:ul)? de bare|barcode|ean)\s*[:=]?\s*(\d{8,14})[.!]?\s*", instruction, re.IGNORECASE)
    if barcode_match:
        if len(items) != 1:
            raise ValueError("Spune-mi pentru care aliment este codul de bare.")
        product = {**items[0], "barcode": barcode_match.group(1), "packaged": True}
        product.pop("uncertain", None)
        return {**extra, **await enrich_meal_references({"meal_type": meal_type, "items": [product]}, previous_items=items)}
    reestimate_words = {
        "estimeaza", "estimează", "aproximeaza", "aproximează", "estimeaza tu", "estimează tu",
        "aproximeaza tu", "aproximează tu", "nu stiu gramele", "nu știu gramele",
        "nu stiu gramajul", "nu știu gramajul",
    }
    if instruction.lower().strip().rstrip(".!?") in reestimate_words:
        reviewed = normalize_meal_proposal(extra, "", items)
        portions = await estimate_visual_portions(_ollama_client, OLLAMA_FOOD_VISION_MODEL, photo_bytes or b"", reviewed["items"])
        return {**extra, **await enrich_meal_references({"meal_type": meal_type, "items": portions}, "", items)}
    if complete and claims:
        # User-provided identities/counts do not need another model translation.
        reviewed = normalize_meal_proposal({"meal_type": meal_type, "items": claims}, instruction, items)
        portions = await estimate_visual_portions(_ollama_client, OLLAMA_FOOD_VISION_MODEL, photo_bytes or b"", reviewed["items"], instruction)
        return {**extra, **await enrich_meal_references({"meal_type": meal_type, "items": portions}, instruction, items)}
    if claims and all(has_food_reference(claim["name"]) and (claim.get("grams") is not None or claim.get("count") is not None) for claim in claims):
        existing_names = {item.get("name") for item in items}
        if all(claim["name"] in existing_names for claim in claims):
            return {**extra, **await enrich_meal_references({"meal_type": meal_type, "items": items}, instruction, items)}
    if complete:
        # Do not contaminate a full correction with fabricated foods from the photo.
        desc = "Descrierea anterioară a fost greșită; se înlocuiește complet."
        items_repr = json.dumps(claims, ensure_ascii=False)
        calories = protein = carbs = fat = "necunoscut"
    else:
        items_repr = json.dumps(items, ensure_ascii=False)
    prompt = f"""Update a meal proposal. JSON only, numeric fields without units.
Current description: {desc}. Meal type: {meal_type}.
Current calories/macros: {calories}, {protein}, {carbs}, {fat}.
Food list: {items_repr}
User instruction: {instruction}
Complete replacement: {complete}
Rules:
- For a complete replacement, use ONLY the supplied food list, copy each name EXACTLY, and preserve counts. Ignore all earlier photo guesses.
- Șnițele = breaded fried meat, Ouă = eggs (fried if pictured), Slănină = pork fat/bacon, Roșie = tomato. Never translate these names into other names.
- Adjust/add/remove only what was requested. Keep any user_weight grams unless explicitly changed.
- For counted foods or specified small/medium/large portions, estimate reasonable edible grams with a broad range grams_min/grams_max. Do not set null merely because they are not weighed: the UI clearly labels estimates. Truly unknown quantities remain null, never zero. No measured weight can be inferred from a photograph.
- Explicit user g/kg weights override estimates. Calories/macros remain estimates for the preparation described. Match calories to 4*protein+4*carbs+9*fat. For each item return ALL four numeric fields or null if impossible to estimate.
- Preserve any barcode and brand for the SAME food; remove them when replacing the food. For a branded/packaged product set packaged=true. preparation may be raw/fried/boiled/grilled/baked/cooked/toasted/breaded. nutrition_query may contain only the English food name/preparation, never the user's message or personal information.
- meal_type is mic_dejun, pranz, cina, gustare or masa.
Schema example (use actual estimates, not the example numbers):
Return meal_type and items. Each item has name (string), count (number or null), grams/grams_min/grams_max (numbers or null), calories/protein/carbs/fat (numbers or null). Do not copy current values for a different food."""

    try:
        updated_data = await asyncio.wait_for(_call_local_llm_json(
            prompt, max_tokens=2048,
            model_names=[OLLAMA_FOOD_VISION_MODEL, OLLAMA_STRUCTURED_MODEL, "qwen2.5:3b"],
        ), timeout=45)
    except Exception as e:
        logger.warning(f"Local LLM failed to modify meal JSON: {e}")
        raise ValueError("Nu am putut recalcula masa. Datele anterioare au fost păstrate.") from e

    return {**extra, **await enrich_meal_references(updated_data, instruction, items)}


async def process_vision_result(
    pool,
    result: Dict[str, Any],
    user_profile: Dict[str, Any],
    client: Any = None,
    receipt_telegram_file_id: Optional[str] = None,
    receipt_local_path: Optional[str] = None,
) -> Tuple[str, Optional[InlineKeyboardMarkup]]:
    """Routes the extracted data to the corresponding module action or asks for confirmation."""
    img_type = result.get("type")
    data = result.get("extracted_data", {})
    base_reply = result.get("reply", "")

    if img_type == "receipt":
        total_amount = data.get("total_amount") or data.get("amount")
        category = (data.get("category") or "altele").lower()
        merchant = data.get("merchant") or "Necunoscut"
        items = data.get("items") or []

        # Validate items structure
        clean_items = []
        for it in items:
            if isinstance(it, dict) and "name" in it:
                try:
                    price = float(it.get("price") or 0)
                    clean_items.append({
                        "name": str(it["name"]).strip(),
                        "price": round(price, 2),
                        "category": str(it.get("category") or category).lower(),
                    })
                except (ValueError, TypeError):
                    continue

        # 1. Lookup learned merchant from OCR context if available
        ocr_text = data.get("ocr_text") or ""
        if ocr_text:
            try:
                from db.queries.product_memory import find_remembered_merchant
                learned_m = await find_remembered_merchant(pool, ocr_text)
                if learned_m:
                    merchant = learned_m
            except Exception as e:
                logger.debug(f"Merchant memory lookup skipped: {e}")

        # 2. Enrich and sanitize items using locally stored learned memory and domain heuristics.
        # Receipt processing must remain local-only; do not send product names to web search.
        for it in clean_items:
            try:
                from db.queries.product_memory import find_remembered_product
                learned_prod = await find_remembered_product(pool, it["name"], merchant)
                if learned_prod:
                    it["name"] = learned_prod["clean_name"]
                    it["category"] = learned_prod["category"]
                    continue
            except Exception as e:
                logger.debug(f"Product memory lookup skipped: {e}")

            name_lower = it["name"].lower()
            if any(term in name_lower for term in ("vuse", "vise", "glo", "iqos", "heets", "terea", "vape")):
                it["category"] = "țigări"
            elif any(term in name_lower for term in ("baterie", "detergent", "bec")):
                it["category"] = "utilități"
            elif any(term in name_lower for term in ("gum", "orbit", "bere", "suc", "lapte", "pâine")):
                it["category"] = "mâncare"
            elif it["category"] == "shopping":
                it["category"] = "altele"

        # The printed receipt total is authoritative. A partial item list is useful
        # for confirmation, but must never replace the total paid by the user.
        items_reliable = True
        if clean_items:
            items_sum = round(sum(i["price"] for i in clean_items), 2)
            if total_amount is None or abs(float(total_amount) - items_sum) > 0.05:
                logger.info(
                    f"Receipt total differs from parsed items: reported {total_amount}, items sum to {items_sum}"
                )
                if total_amount is None:
                    total_amount = items_sum
                # Discounts, deposits and OCR line pairing can make the item list
                # unreliable. Never write each guessed line as a separate expense
                # when it cannot reconcile with the printed amount.
                items_reliable = False

        if total_amount is None and not clean_items:
            return safe_markdown(
                "Am detectat un bon, dar nu am putut citi clar sumele sau produsele."
            ), None

        final_amount = float(total_amount or 0)

        # Pregătește starea pentru confirmare
        extra = {
            "amount": final_amount,
            "category": category,
            "description": merchant,
            "items": clean_items,
            "items_reliable": items_reliable,
            "type": "expense",
            "ocr_text": ocr_text,
            "receipt_telegram_file_id": receipt_telegram_file_id,
            "receipt_local_path": receipt_local_path,
        }
        await set_state(
            pool,
            "awaiting_vision_confirmation",
            "finance",
            "log_expense",
            None,
            extra=extra,
        )

        return render_receipt_preview(extra)

    elif img_type == "menu":
        personal_notes = user_profile.get("personal_notes", "")
        prompt = f"""Ești Lora. Utilizatorul ți-a trimis un meniu de restaurant.
Datele extrase din meniu: {data}
Preferințele utilizatorului: {personal_notes}
Sugerează-i ceva gustos și sănătos de pe acest meniu.
Răspunde direct, în română, formatat elegant cu MarkdownV2. Maximum 3 propoziții."""

        try:
            res = await _ollama_client.chat(
                model=OLLAMA_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            recommendation = res.get("message", {}).get("content", "").strip()
            return safe_markdown(recommendation), None
        except Exception:
            return safe_markdown(
                "Arată apetisant! Din păcate nu am putut genera o recomandare specifică."
            ), None

    elif img_type == "workout_screenshot":
        import db.queries.workout as workout_queries

        sport = data.get("sport_name", "Cardio")
        duration = data.get("duration_min", 0)
        calories = data.get("calories")

        if not duration:
            return safe_markdown(
                f"Antrenament detectat ({sport}), dar nu am găsit durata. Încearcă să o introduci manual."
            ), None

        await workout_queries.log_workout(
            pool,
            workout_date=None,
            sport_name=sport,
            duration_min=duration,
            calories=calories,
            notes="Extras din screenshot",
            exercises=[],
        )
        msg = (
            f"💪 Antrenament salvat din imagine!\n\n"
            f"Sport: *{escape_md(str(sport))}*\n"
            f"Durată: `{duration} min`\n"
            f"Calorii: `{calories or 'N/A'}`"
        )
        return msg, None

    elif img_type == "food":
        calories = data.get("total_calories")
        protein = data.get("total_protein")
        carbs = data.get("total_carbs")
        fat = data.get("total_fat")
        description = data.get("description", "Masă")
        meal_type = data.get("meal_type", "masa")
        items = data.get("items") or []

        extra = {
            "calories": calories,
            "protein": protein,
            "carbs": carbs,
            "fat": fat,
            "description": description,
            "meal_type": meal_type,
            "items": items,
            "nutrition_lookup_incomplete": data.get("nutrition_lookup_incomplete", False),
            "nutrition_estimated": True,
            "needs_portion_details": data.get("needs_portion_details", False),
            "review_questions": data.get("review_questions") or [],
            "food_telegram_file_id": receipt_telegram_file_id,
        }
        await set_state(
            pool,
            "awaiting_vision_confirmation",
            "nutrition",
            "meal_log",
            None,
            extra=extra,
        )

        return render_meal_preview(extra)

    elif img_type == "handwritten_notes":
        text = data.get("text", "")
        if not text:
            return safe_markdown("Nu am putut transcrie un text lizibil."), None

        import db.queries.notes as note_queries

        await note_queries.add_note(pool, content=text, note_type="note")
        return safe_markdown(f"✍️ Notiță salvată cu succes:\n\n_{text}_"), None

    elif img_type == "book_cover":
        title = data.get("title")
        author = data.get("author", "Autor Necunoscut")

        if not title:
            return safe_markdown(
                "Am detectat o copertă de carte, dar nu am putut citi clar titlul."
            ), None

        import db.queries.reading as reading_queries

        await reading_queries.add_book(pool, title=title, author=author)
        return safe_markdown(
            f"📚 Cartea *{title}* de {author} a fost adăugată în lista de citit!"
        ), None

    else:
        return safe_markdown(
            base_reply or "Nu am putut clasifica clar această imagine."
        ), None


async def cancel_vision_action(pool) -> str:
    """Cancels pending vision action and clears state."""
    await clear_state(pool)
    return "❌ Acțiune anulată."


async def confirm_vision_action(pool, state: Dict[str, Any]) -> str:
    """Executes the pending vision action and returns confirmation message."""
    action = state.get("action")
    extra = state.get("extra", {})

    if action == "log_expense":
        items = extra.get("items") or []
        desc = extra.get("description") or "Bon fiscal"
        receipt_file_id = extra.get("receipt_telegram_file_id")
        receipt_local_path = extra.get("receipt_local_path")

        if items and extra.get("items_reliable", True):
            count = 0
            for item in items:
                name = item.get("name") or "Articol"
                price = float(item.get("price") or 0)
                category = (item.get("category") or extra.get("category") or "altele").lower()
                item_desc = f"{name} ({desc})" if desc and desc != "Necunoscut" else name
                transaction_kwargs = {
                    "category": category,
                    "description": item_desc,
                }
                if receipt_file_id:
                    transaction_kwargs["receipt_telegram_file_id"] = receipt_file_id
                if receipt_local_path:
                    transaction_kwargs["receipt_local_path"] = receipt_local_path
                await log_transaction(pool, "expense", price, **transaction_kwargs)
                # Automatically remember product mapping for future receipts
                try:
                    from db.queries.product_memory import remember_product
                    await remember_product(
                        pool,
                        raw_pattern=item.get("raw_name") or name,
                        clean_name=name,
                        category=category,
                        merchant=desc,
                        price=price,
                    )
                except Exception as e:
                    logger.warning(f"Failed to auto-remember product: {e}")
                count += 1

            # If OCR text exists, remember merchant too
            ocr_text = extra.get("ocr_text")
            if ocr_text and desc and desc != "Necunoscut":
                try:
                    from db.queries.product_memory import remember_merchant
                    lines = [
                        ln.strip()
                        for ln in ocr_text.splitlines()
                        if len(ln.strip()) >= 4
                        and not any(k in ln.lower() for k in ["total", "bon", "cif", "operator"])
                    ]
                    if lines:
                        await remember_merchant(pool, lines[0], desc)
                except Exception as e:
                    logger.warning(f"Failed to auto-remember merchant: {e}")

            await clear_state(pool)
            return f"✅ Am înregistrat cu succes {count} produse pe categorii de la *{escape_md(desc)}*."
        else:
            amount = float(extra.get("amount") or 0)
            category = extra.get("category", "altele")
            if items and not extra.get("items_reliable", True):
                logger.warning(
                    "Receipt line items were not reconciled; logging one authoritative total "
                    "instead of guessed line-item expenses"
                )
            transaction_kwargs = {"category": category, "description": desc}
            if receipt_file_id:
                transaction_kwargs["receipt_telegram_file_id"] = receipt_file_id
            if receipt_local_path:
                transaction_kwargs["receipt_local_path"] = receipt_local_path
            await log_transaction(pool, "expense", amount, **transaction_kwargs)
            await clear_state(pool)
            return f"✅ Cheltuială de `{amount:.2f} RON` înregistrată cu succes ({escape_md(category)})."

    if action == "meal_log":
        from modules.nutrition import handle_nutrition_intent

        if extra.get("needs_portion_details"):
            return render_meal_preview(extra)[0]

        meal_data = {
            "calories": extra.get("calories", 0),
            "protein": extra.get("protein", 0),
            "carbs": extra.get("carbs", 0),
            "fat": extra.get("fat", 0),
            "description": extra.get("description", "Masă din poză"),
            "meal_type": extra.get("meal_type", "masa"),
            "items": [
                {**item, "quantity_g": item.get("grams", item.get("quantity_g"))}
                for item in extra.get("items") or []
            ],
        }

        result = await handle_nutrition_intent(pool, "meal_log", meal_data)
        reply = result[0] if isinstance(result, tuple) else result
        if str(reply).startswith(("⚠️", "❌")):
            return reply
        await clear_state(pool)
        return f"{reply}\n\n_Estimările nutriționale au fost confirmate de tine._"

    await clear_state(pool)
    return "Acțiune finalizată."


async def handle_vision_callback(query, pool, callback_data: str):
    """Handles the 'vision:confirm/cancel' buttons for actions requiring user review."""
    state = await get_state(pool)
    if not state or state.get("state_type") != "awaiting_vision_confirmation":
        await query.answer("Acțiunea a expirat sau nu mai este validă.")
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    if callback_data == "vision:cancel":
        msg = await cancel_vision_action(pool)
        await query.answer("Acțiune anulată.")
        await query.edit_message_text(msg)
        return

    if callback_data == "vision:confirm":
        action = state.get("action")
        if action == "meal_log" and (state.get("extra") or {}).get("needs_portion_details"):
            msg, keyboard = render_meal_preview(state["extra"])
            await query.answer("Mai am nevoie de identificarea alimentelor neclare.")
            await query.edit_message_text(msg, parse_mode="MarkdownV2", reply_markup=keyboard)
            return
        msg = await confirm_vision_action(pool, state)
        answer_text = "Poftă bună!" if action == "meal_log" else "Salvat!"
        await query.answer(answer_text)
        await query.edit_message_text(msg, parse_mode="MarkdownV2")
        return

    await query.answer("Tip de acțiune necunoscut.")
    await clear_state(pool)
