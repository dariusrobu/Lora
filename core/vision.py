import asyncio
import base64
import io
import json
import logging
import os
import re
from typing import Any, Dict, Optional, Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.callback_utils import make_callback_data
from bot.formatter import escape_md, safe_markdown
from core import config
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

_ollama_client = AsyncClient(host=OLLAMA_HOST)


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


async def _call_local_llm_json(prompt: str) -> Dict[str, Any]:
    """Calls local Ollama model with structured JSON enforcement and fallback."""
    models_to_try = [
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
            res = await _ollama_client.chat(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                format="json",
            )
            content = res.get("message", {}).get("content", "")
            return _clean_json_from_text(content)
        except Exception as e:
            logger.debug(f"Ollama structured call with {model_name} failed: {e}")
            last_err = e

    raise RuntimeError(f"All local Ollama models failed for structured parsing: {last_err}")


async def describe_image_with_vision(
    photo_bytes: bytes,
    prompt: str = "Describe what is shown in this image in detail. If there is food, a meal, or drinks, list each dish, ingredient, and estimated portion sizes.",
) -> str:
    """Uses a local Ollama vision model (moondream, llava, etc.) to extract a rich visual description."""
    b64_img = base64.b64encode(photo_bytes).decode("utf-8")
    vision_models = [OLLAMA_VISION_MODEL, "moondream", "llama3.2-vision", "llava"]
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
            )
            content = res.get("message", {}).get("content", "").strip()
            if content:
                logger.info(f"Local vision model ({vm}) described image: {content[:150]}...")
                return content
        except Exception as e:
            logger.debug(f"Ollama vision model {vm} description failed: {e}")

    return ""


async def analyze_food_from_vision(
    vision_description: str, caption: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Uses local structured LLM (qwen2.5:7b) to determine if vision description represents food,
    and calculates realistic grams, calories, and macronutrients.
    """
    if not vision_description:
        return None

    prompt = f"""Ești un nutriționist și asistent expert.
Analizează descrierea vizuală a unei farfurii / mese:
\"\"\"{vision_description}\"\"\"
{f"Text adițional de la utilizator: {caption}" if caption else ""}

Întrebare: Imaginea conține mâncare, alimente, o masă sau băuturi?
Dacă DA:
- Identifică preparatul în limba română (ex: "Piept de pui la grătar cu lămâie").
- Stabilește tipul mesei: "mic_dejun", "pranz", "cina" sau "gustare".
- REGULI STRICTE:
  1. Include EXCLUSIV alimentele și ingredientele menționate în descrierea vizuală. NU inventa garnituri (nu adăuga orez, cartofi, salată, pâine etc. dacă NU apar în descriere!). Farfuria albă sau spațiile goale NU sunt mâncare/orez!
  2. Dacă este o farfurie mare de servire (platou) cu mai multe bucăți, estimează o porție individuală standard (1 persoană, ex: 1 piept de pui ~150-180g) dacă utilizatorul nu a cerut tot platoul.
  3. Feliile de lămâie sau verdețurile folosite ca decor/aromă au calorii minime (~5-10 kcal, carbohidrați neglijabili).
  4. Pieptul de pui simplu la grătar NU conține carbohidrați (0g carbohidrați).
  5. Folosește termeni corecți și firești în limba română (ex: 'Piept de pui', 'Lămâie', NU 'limon' sau invenții de cuvinte).

Dacă NU este mâncare (este un obiect, peisaj, animal, persoană etc.), setează is_food: false.

Răspunde STRICT cu un JSON valid (fără markdown):
{{
  "is_food": true,
  "description": "Denumire preparat identificat",
  "meal_type": "pranz",
  "items": [
    {{"name": "Denumire aliment", "grams": 150, "calories": 220, "protein": 35, "carbs": 0, "fat": 4}}
  ]
}}"""

    try:
        data = await _call_local_llm_json(prompt)
        if data.get("is_food"):
            desc = (data.get("description") or "Masă").strip()
            desc = desc.replace("Pițipui", "Piept de pui").replace("pițipui", "piept de pui")
            data["description"] = desc

            items = data.get("items") or []
            # Normalize naming and recalculate totals directly from items for mathematical consistency
            for it in items:
                it_name = it.get("name", "")
                if "limon" in it_name.lower():
                    it["name"] = it_name.replace("limon", "lămâie").replace("Limon", "Lămâie")
                if "pițipui" in it_name.lower():
                    it["name"] = it_name.replace("pițipui", "piept de pui").replace("Pițipui", "Piept de pui")

            if items:
                total_calories = sum(int(it.get("calories") or 0) for it in items)
                total_protein = sum(int(it.get("protein") or 0) for it in items)
                total_carbs = sum(int(it.get("carbs") or 0) for it in items)
                total_fat = sum(int(it.get("fat") or 0) for it in items)
            else:
                total_calories = int(data.get("total_calories") or 0)
                total_protein = int(data.get("total_protein") or 0)
                total_carbs = int(data.get("total_carbs") or 0)
                total_fat = int(data.get("total_fat") or 0)

            return {
                "type": "food",
                "confidence": 0.88,
                "extracted_data": {
                    "description": data.get("description") or "Masă",
                    "meal_type": data.get("meal_type") or "pranz",
                    "total_calories": total_calories,
                    "total_protein": total_protein,
                    "total_carbs": total_carbs,
                    "total_fat": total_fat,
                    "items": items,
                },
                "reply": f"Am identificat: {data.get('description')}",
            }
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
        vision_desc = await describe_image_with_vision(photo_bytes)
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
        lines.append("\n_Dorești să înregistrez aceste cheltuieli pe categorii?_")
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
    calories = int(extra.get("calories") or 0)
    protein = int(extra.get("protein") or 0)
    carbs = int(extra.get("carbs") or 0)
    fat = int(extra.get("fat") or 0)
    items = extra.get("items") or []

    lines = [
        f"🥗 Am identificat: *{escape_md(str(description))}*\n",
        f"🔥 *Calorii*: `{calories} kcal`",
        f"📊 *Macros*: `{protein}g P` · `{carbs}g C` · `{fat}g F`",
    ]

    if items:
        lines.append("\n*Componență estimată:*")
        for it in items:
            it_name = it.get("name") or "Aliment"
            it_g = it.get("grams")
            it_cal = it.get("calories")
            it_p = it.get("protein")
            it_c = it.get("carbs")
            it_f = it.get("fat")

            g_str = f" (~{it_g}g)" if it_g else ""
            macro_details = []
            if it_p is not None:
                macro_details.append(f"{it_p}g P")
            if it_c is not None:
                macro_details.append(f"{it_c}g C")
            if it_f is not None:
                macro_details.append(f"{it_f}g F")
            macro_str = f" · _{', '.join(macro_details)}_" if macro_details else ""
            lines.append(f"• *{escape_md(str(it_name))}*{escape_md(g_str)}: `{it_cal or 0} kcal`{macro_str}")

    lines.append("\n_Dorești să înregistrez această masă în jurnal?_")
    lines.append("💡 _Trimite un mesaj pentru corecții (ex: „am mâncat 200g”, „adaugă și 100g orez”) sau confirmă direct._")
    msg = "\n".join(lines)

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


async def modify_pending_meal(extra: Dict[str, Any], instruction: str) -> Dict[str, Any]:
    """Applies natural language corrections to pending meal (ingredients, grams, macros, meal type) using local LLM."""
    desc = extra.get("description", "Masă")
    items = extra.get("items", [])
    meal_type = extra.get("meal_type", "pranz")
    calories = extra.get("calories", 0)
    protein = extra.get("protein", 0)
    carbs = extra.get("carbs", 0)
    fat = extra.get("fat", 0)

    items_repr = json.dumps(items, ensure_ascii=False)
    prompt = f"""Ești un nutriționist expert care ajustează datele unei mese la cererea utilizatorului.

Date curente ale mesei:
- Preparat: "{desc}"
- Tip masă: "{meal_type}"
- Calorii curente: {calories} kcal
- Macros curenți: {protein}g P, {carbs}g C, {fat}g F
- Ingrediente:
{items_repr}

Instrucțiunea utilizatorului:
"{instruction}"

Reguli:
1. Ajustează ingredientele, gramajele, tipul mesei sau denumirea conform instrucțiunii utilizatorului (ex: schimbă cantitatea, adaugă un aliment nou, elimină un ingredient).
2. Recalculează precis caloriile și macronutrienții (protein, carbs, fat) pentru fiecare aliment și pentru total.
3. Răspunde STRICT cu un JSON valid:
{{
  "description": "Denumire preparat actualizată",
  "meal_type": "mic_dejun|pranz|cina|gustare",
  "items": [
    {{"name": "Denumire aliment", "grams": 150, "calories": 220, "protein": 35, "carbs": 0, "fat": 4}}
  ]
}}"""

    try:
        updated_data = await _call_local_llm_json(prompt)
    except Exception as e:
        logger.warning(f"Local LLM failed to modify meal JSON: {e}")
        return extra

    new_extra = dict(extra)
    if updated_data.get("description"):
        new_extra["description"] = str(updated_data["description"]).strip()
    if updated_data.get("meal_type"):
        new_extra["meal_type"] = str(updated_data["meal_type"]).strip()

    raw_items = updated_data.get("items")
    if isinstance(raw_items, list) and raw_items:
        clean_items = []
        for it in raw_items:
            if isinstance(it, dict) and "name" in it:
                try:
                    clean_items.append({
                        "name": str(it["name"]).strip(),
                        "grams": int(it.get("grams") or 0),
                        "calories": int(it.get("calories") or 0),
                        "protein": int(it.get("protein") or 0),
                        "carbs": int(it.get("carbs") or 0),
                        "fat": int(it.get("fat") or 0),
                    })
                except (ValueError, TypeError):
                    continue
        if clean_items:
            new_extra["items"] = clean_items
            new_extra["calories"] = sum(i["calories"] for i in clean_items)
            new_extra["protein"] = sum(i["protein"] for i in clean_items)
            new_extra["carbs"] = sum(i["carbs"] for i in clean_items)
            new_extra["fat"] = sum(i["fat"] for i in clean_items)

    return new_extra


async def process_vision_result(
    pool,
    result: Dict[str, Any],
    user_profile: Dict[str, Any],
    client: Any = None,
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
        if clean_items:
            items_sum = round(sum(i["price"] for i in clean_items), 2)
            if total_amount is None or abs(float(total_amount) - items_sum) > 0.05:
                logger.info(
                    f"Receipt total differs from parsed items: reported {total_amount}, items sum to {items_sum}"
                )
                if total_amount is None:
                    total_amount = items_sum

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
            "type": "expense",
            "ocr_text": ocr_text,
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
        calories = int(data.get("total_calories") or 0)
        protein = int(data.get("total_protein") or 0)
        carbs = int(data.get("total_carbs") or 0)
        fat = int(data.get("total_fat") or 0)
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

        if items:
            count = 0
            for item in items:
                name = item.get("name") or "Articol"
                price = float(item.get("price") or 0)
                category = (item.get("category") or extra.get("category") or "altele").lower()
                item_desc = f"{name} ({desc})" if desc and desc != "Necunoscut" else name
                await log_transaction(
                    pool, "expense", price, category=category, description=item_desc
                )
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
            await log_transaction(
                pool, "expense", amount, category=category, description=desc
            )
            await clear_state(pool)
            return f"✅ Cheltuială de `{amount:.2f} RON` înregistrată cu succes ({escape_md(category)})."

    if action == "meal_log":
        from modules.nutrition import handle_nutrition_intent

        meal_data = {
            "calories": extra.get("calories", 0),
            "protein": extra.get("protein", 0),
            "carbs": extra.get("carbs", 0),
            "fat": extra.get("fat", 0),
            "description": extra.get("description", "Masă din poză"),
            "meal_type": extra.get("meal_type", "masa"),
            "items": extra.get("items") or [],
        }

        result = await handle_nutrition_intent(pool, "meal_log", meal_data)
        reply = result[0] if isinstance(result, tuple) else result
        await clear_state(pool)
        return reply

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
        msg = await confirm_vision_action(pool, state)
        answer_text = "Poftă bună!" if action == "meal_log" else "Salvat!"
        await query.answer(answer_text)
        await query.edit_message_text(msg, parse_mode="MarkdownV2")
        return

    await query.answer("Tip de acțiune necunoscut.")
    await clear_state(pool)
