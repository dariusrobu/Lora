"""
Council Bot-to-User Translator.
Translates business jargon from Council bots into plain Romanian.
"""

from typing import Optional
from google import genai
from google.genai import types
from core.config import GEMINI_API_KEY

client = genai.Client(api_key=GEMINI_API_KEY)


JARGON_GLOSSARY = {
    "burn rate": "rata de consum - cât cheltuim lunar",
    "burn-rate": "rata de consum - cât cheltuim lunar",
    "ltv": "LTV (Lifetime Value) - cât valorează un client în timp",
    "cac": "CAC (Customer Acquisition Cost) - cât costă să aducem un client",
    "mrr": "MRR (Monthly Recurring Revenue) - venituri lunare recurente",
    "arr": "ARR (Annual Recurring Revenue) - venituri anuale recurente",
    "okr": "OKR - obiective și rezultate cheie",
    "kpi": "KPI - indicator de performanță",
    "runway": "runway - cât mai avem bani",
    "tech debt": "datorie tehnică - probleme tehnice amânate",
    "technical debt": "datorie tehnică - probleme tehnice amânate",
    "churn": "churn - câți clienți pleacă",
    "retention": "retention - câți clienți rămân",
    "pipeline": "pipeline - oportunități de vânzări",
    "run rate": "run rate - ritmul actual de cheltuieli",
    "cash flow": "cash flow - fluxul de bani",
    "roi": "ROI - randamentul investiției",
    "margin": "marja - profitul",
    "arpu": "ARPU - venit mediu per user",
    "daemon": "DAU/MAU - utilizatori activi zilnic/lunar",
    "velocity": "velocity - viteza de creștere",
    "burn": "burn - cheltuieli lunare",
}


async def translate_council_jargon(text: str) -> Optional[str]:
    """
    Translates Council bot jargon to plain Romanian using Gemini.
    Falls back to glossary lookup if API fails.
    """
    if not text:
        return None

    text_lower = text.lower()

    detected_terms = []
    for jargon, meaning in JARGON_GLOSSARY.items():
        if jargon.lower() in text_lower:
            detected_terms.append(f"*{jargon}* → {meaning}")

    if not detected_terms:
        return None

    try:
        prompt = f"""Ești un translator pentru un antreprenor român.
Un bot de business (Consiliul) a trimis un mesaj cu jargon englezesc.
Tradu înromână simplă, cu explicații scurte.

MESAJ ORIGINAL:
{text}

TERMINOLOGIE DETECTATĂ:
{chr(10).join(detected_terms)}

INSTRUCȚIUNI:
- Tradu mesajul în română naturală
- Explică termenii tehnici în paranteze
- Fii scurt și direct
- Ton: prietenos, ca un prieten care explică
- Răspunde doar cu traducerea, fără introduceri"""

        response = await client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=500,
            ),
        )

        if response.text:
            return response.text.strip()

    except Exception as e:
        print(f"Translator API error: {e}")

    fallback = f"💡 *Traducere:* {text}\n\n"
    fallback += "Termeni detectați:\n" + "\n".join(detected_terms)
    return fallback


def quick_translate(text: str) -> Optional[str]:
    """Quick glossary-based translation without API call."""
    if not text:
        return None

    text_lower = text.lower()
    detected = []

    for jargon, meaning in JARGON_GLOSSARY.items():
        if jargon.lower() in text_lower:
            detected.append(f"*{jargon}* = {meaning}")

    if not detected:
        return None

    return "💡 *Din jargon în română:*\n" + "\n".join(detected)
