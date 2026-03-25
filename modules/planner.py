# modules/planner.py

from typing import Tuple
from datetime import datetime
import pytz
from core.config import TIMEZONE
from bot.formatter import safe_markdown


async def generate_time_block(pool) -> Tuple[str, None]:
    from core.gemini import get_proactive_response
    import db.queries.tasks as task_queries
    import db.queries.events as event_queries
    import db.queries.skills as skill_queries
    import db.queries.health as health_queries

    user_tz = pytz.timezone(TIMEZONE)
    now = datetime.now(user_tz)
    today = now.date()

    # Colectează date
    all_tasks = await task_queries.list_tasks(pool)
    events = await event_queries.list_events(pool, today, today)
    skills = await skill_queries.get_all_skills(pool)
    health_today = await health_queries.get_health_log(pool, today)

    # Filtrează tasks relevante
    pending_tasks = [t for t in all_tasks if t.get("status") != "done"][:8]

    # Pending skills (not logged today)
    pending_skills = [s for s in skills if s.get("last_log_date") != today]

    # Build context
    task_lines = []
    for t in pending_tasks:
        priority = f" [{t['priority']}]" if t.get("priority") else ""
        overdue = " OVERDUE" if t.get("due_date") and t["due_date"] < today else ""
        est = f" ~{t.get('estimated_min', 30)}min" if t.get("estimated_min") else ""
        task_lines.append(f"- {t['title']}{priority}{overdue}{est}")

    event_lines = []
    for e in events:
        time_str = (
            e["event_time"].strftime("%H:%M") if e.get("event_time") else "toată ziua"
        )
        event_lines.append(f"- {time_str}: {e['title']}")

    skill_lines = [f"- {s['name']}" for s in pending_skills]

    # Health context — ajustează recomandările dacă somn < 6.5h
    energy_note = ""
    if health_today and health_today.get("sleep_hours"):
        sleep = float(health_today["sleep_hours"])
        if sleep < 6.5:
            energy_note = f"IMPORTANT: userul a dormit doar {sleep}h — evită task-uri cognitive grele dimineața, pune-le după-amiaza."
        elif sleep >= 8:
            energy_note = f"Userul a dormit bine ({sleep}h) — poate face task-uri grele dimineața."

    data_ctx = f"""
ORA CURENTĂ: {now.strftime("%H:%M")}
DATA: {today.strftime("%A, %d %B %Y")}

TASKS PENDING:
{chr(10).join(task_lines) or "Niciun task pending."}

EVENIMENTE FIXE AZI:
{chr(10).join(event_lines) or "Niciun eveniment."}

SKILLS PENDING:
{chr(10).join(skill_lines) or "Totul e la zi."}

{energy_note}
"""

    instruction = """
Ești Lora. Generează un time block pentru ziua de azi bazat pe datele primite.

Reguli:
- Respectă evenimentele fixe la orele lor exacte
- Pune task-urile high priority și OVERDUE primele
- Distribuie realist — nu supraaglomera
- Includ pauze (10-15 min după fiecare 90 min de muncă)
- Dacă e după-amiază târziu, nu planifica task-uri grele
- Maxim 8 blocuri orare
- Integrează skills pending în sloturile libere dacă e relevant
- Fără comentarii sau explicații între paranteze după activități
- Fără sugestii nesolicitate (cafea, muzică, plimbări)
- Fiecare bloc = doar ora + activitatea, nimic altceva
- Activitățile vin EXCLUSIV din tasks, events și skills din context

Format EXACT (MarkdownV2 raw):
🗓 *Time Block — [ziua, data]*

`HH:MM` — `HH:MM` · [activitate]
`HH:MM` — `HH:MM` · [activitate]
...

Fără introduceri, fără concluzii. Doar time block-ul.
"""

    result = await get_proactive_response(instruction, data_ctx)
    if not result:
        return "Nu am putut genera time block-ul\\. Încearcă din nou\\.", None

    return safe_markdown(result), None
