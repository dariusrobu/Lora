import logging
import re
from typing import List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)


async def search_web(query: str, max_results: int = 3) -> List[str]:
    """Searches the web via DuckDuckGo HTML and returns concise text snippets."""
    query = query.strip()
    if not query:
        return []

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "ro-RO,ro;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    try:
        async with httpx.AsyncClient(timeout=4.0, follow_redirects=True) as client:
            resp = await client.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query},
                headers=headers,
            )
            if resp.status_code == 200:
                matches = re.findall(
                    r'<a class="result__snippet[^"]*"[^>]*>(.*?)</a>',
                    resp.text,
                    re.DOTALL,
                )
                snippets = []
                for m in matches[:max_results]:
                    clean = re.sub(r"<.*?>", "", m).strip()
                    if clean:
                        snippets.append(clean)
                return snippets
    except Exception as e:
        logger.debug(f"Web search for '{query}' failed: {e}")

    return []


async def identify_product_with_web(
    product_name: str, candidate_categories: Optional[List[str]] = None
) -> Tuple[str, Optional[str]]:
    """Uses OCR correction, brand heuristics, and web search to identify product and its category.
    
    Returns (corrected_name, category)
    """
    clean_name = product_name.strip()

    # Common OCR typo corrections for popular Romanian brands & words
    clean_name = re.sub(r"\bVISE\b", "Vuse", clean_name, flags=re.IGNORECASE)
    clean_name = re.sub(r"\bCABANANDS\b", "Cabanos", clean_name, flags=re.IGNORECASE)
    clean_name = re.sub(r"\bCABANANOS\b", "Cabanos", clean_name, flags=re.IGNORECASE)
    clean_name = re.sub(r"\bCARNATI\b", "Cârnați", clean_name, flags=re.IGNORECASE)

    lower = clean_name.lower()

    # Fast path: Common direct keywords
    tobacco_kw = (
        "vuse", "glo", "iqos", "heets", "terea", "pods", "vape",
        "tigari", "tutun", "bricheta", "sobranie", "marlboro",
        "winston", "kent", "dunhill", "pall mall", "camel", "elfbar",
    )
    food_kw = (
        "carnat", "cabanos", "carne", "pui", "porc", "vita", "lapte",
        "paine", "iaurt", "branza", "oua", "fruct", "legum", "mar",
        "banana", "chips", "biscuit", "ciocolat", "apa", "suc", "bere",
        "vin", "cafea", "ceai", "mezel", "salam", "sunca", "otet",
    )
    transport_kw = (
        "benzina", "benzină", "motorina", "motorină", "diesel", "gpl", "lukoil", "omv",
        "petrom", "rompetrol", "mol", "euro luk", "carburant", "combustibil", "parcare",
        "spalatorie", "spălătorie", "rovinieta", "rovinietă", "itp", "uber", "bolt", "taxi",
    )
    health_kw = ("paracetamol", "nurofen", "aspirin", "algocalmin", "vitamina", "pastile")
    util_kw = ("baterie", "baterii", "detergent", "fairy", "ariel", "domestos", "saci menajeri", "hartie igienica")

    if any(re.search(rf"\b{re.escape(kw)}\b", lower) for kw in tobacco_kw):
        return clean_name, "țigări"
    if any(re.search(rf"\b{re.escape(kw)}\b", lower) for kw in transport_kw):
        return clean_name, "transport"
    if any(re.search(rf"\b{re.escape(kw)}\b", lower) for kw in food_kw):
        return clean_name, "mâncare"
    if any(re.search(rf"\b{re.escape(kw)}\b", lower) for kw in health_kw):
        return clean_name, "sănătate"
    if any(re.search(rf"\b{re.escape(kw)}\b", lower) for kw in util_kw):
        return clean_name, "utilități"

    # Slow path: Web search lookup if category is uncertain
    try:
        snippets = await search_web(f"ce este {clean_name}")
        if not snippets:
            snippets = await search_web(clean_name)

        snippet_text = " ".join(snippets).lower()

        if any(w in snippet_text for w in ("țigarete", "tigarete", "dispozitiv", "vape", "tutun", "fumat", "nicotin", "e-lichid", "vuse", "iqos", "glo")):
            return clean_name, "țigări"
        if any(w in snippet_text for w in ("aliment", "reteta", "mancare", "carne", "mezel", "snack", "dulciuri", "ingrediente")):
            return clean_name, "mâncare"
        if any(w in snippet_text for w in ("combustibil", "carburant", "statie peco", "stație peco", "benzinarie", "benzinărie", "ulei motor", "antigel")):
            return clean_name, "transport"
        if any(w in snippet_text for w in ("medicament", "farmacie", "tratament", "dureri", "comprimate", "capsule medicale")):
            return clean_name, "sănătate"
        if any(w in snippet_text for w in ("detergent", "curatenie", "menaj", "spalare")):
            return clean_name, "utilități"
    except Exception as e:
        logger.debug(f"Web identification failed: {e}")

    return clean_name, None
