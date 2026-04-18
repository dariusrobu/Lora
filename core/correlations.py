# core/correlations.py

import json
import asyncio
from typing import List, Dict, Any
from google.genai import types
from core.gemini import client
from db.queries.correlations import get_30day_snapshot, get_weekly_patterns
from db.queries.memory import list_all_memories, save_memory_fact


async def compute_correlations(pool) -> List[Dict[str, Any]]:
    """Analyzes life data to find meaningful cross-domain correlations using Gemini."""

    # 1. Gather data
    snapshot, weekly = await asyncio.gather(
        get_30day_snapshot(pool), get_weekly_patterns(pool)
    )

    # Count days that actually have some health or productivity data
    days_with_data = sum(
        1
        for d in snapshot
        if d.get("sleep_hours") is not None or d.get("tasks_completed", 0) > 0
    )

    if days_with_data < 7:
        print(
            f"Correlation Engine: Not enough actual data (only {days_with_data} days).",
            flush=True,
        )
        return []

    # 2. Format data for Gemini
    snapshot_str = json.dumps(snapshot, default=str, indent=2)
    weekly_str = json.dumps(weekly, default=str, indent=2)

    prompt = f"""
Analizează datele de mai jos și identifică 3 corelații semnificative între domenii diferite (somn, apă, mood, tasks, gym, focus, cheltuieli, habit-uri).

DATE SNAPSHOT (ULTIMELE 30 ZILE):
{snapshot_str}

DATE AGREGATE PE ZILELE SĂPTĂMÂNII:
{weekly_str}

EXEMPLE DE CĂUTAT:
- Somn < 6.5h → habit completion rate scade semnificativ ziua următoare.
- Zile fără workout/gym → cheltuielile pe mâncare cresc (comfort food/ieșiri).
- Mood rău → focus minutes scad sau tasks completate scad.
- Focus sessions lungi (>2h) → mood îmbogățit seara.
- Streak de habit-uri > 5 zile → progresul la goals (indirect tasks) accelerează.

REGULI:
1. Identifică doar corelații cu o bază reală în cifrele primite.
2. Oferă recomandări acționabile și specifice.
3. Răspunde EXCLUSIV în format JSON (listă de obiecte).

SCHEMA JSON:
[
  {{
    "correlation": "descriere scurtă a relației detectate în română",
    "strength": "puternică" | "moderată",
    "recommendation": "sfat concret pentru user în română",
    "data_evidence": "explicație scurtă bazată pe date (ex: 'În cele 4 zile cu somn sub 6h, ai avut 0 focus sessions')"
  }}
]
"""

    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,  # Low temp for data analysis stability
            ),
        )
        correlations = json.loads(response.text)
        return correlations
    except Exception as e:
        print(f"Correlation Engine Error: {e}", flush=True)
        return []


async def get_unseen_correlations(
    pool, computed: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Filters out correlations already shared with the user in the last 7 days using memory_facts."""

    # 1. Fetch existing patterns from memory_facts
    # Filter for 'pattern' category
    existing_facts = await list_all_memories(pool)
    known_patterns = [f["fact"] for f in existing_facts if f["category"] == "pattern"]

    unseen = []

    for item in computed:
        corr_text = item["correlation"]

        # Simple similarity check: is this correlation already in memory?
        # We can use a simple keyword overlap or just check if the exact text exists.
        # Given Gemini might rephrase, we'll store the core correlation text.

        is_known = False
        for pattern in known_patterns:
            # If the new correlation text is broadly similar to a known one
            if (
                corr_text.lower() in pattern.lower()
                or pattern.lower() in corr_text.lower()
            ):
                is_known = True
                break

        if not is_known:
            unseen.append(item)

    return unseen


async def save_correlation_as_fact(pool, correlation: Dict[str, Any]):
    """Saves a confirmed correlation to memory_facts to prevent redundancy."""
    fact_text = f"Pattern detectat: {correlation['correlation']}. Dovadă: {correlation['data_evidence']}"
    await save_memory_fact(
        pool, "pattern", fact_text, source="inferred", confidence=0.8
    )
