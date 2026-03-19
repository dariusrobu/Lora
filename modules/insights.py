from typing import Dict, Any, Tuple
import db.queries.insights as insight_queries
from datetime import datetime
from core.gemini import get_proactive_response

async def generate_insights(pool) -> str:
    """
    Analyzes patterns between mood and productivity and generates a Gemini insight.
    """
    data = await insight_queries.get_insight_data(pool, days=30)
    
    # Check if we have enough mood data (at least 7 days with mood)
    mood_days = [d for d in data if d['mood'] is not None]
    if len(mood_days) < 7:
        return "Nu am suficiente date încă — mai am nevoie de câteva săptămâni de jurnal pentru a observa patterns."

    # Calculate basic stats for prompt
    high_mood_prod = [d['tasks'] + d['habits'] for d in data if d['mood'] and d['mood'] >= 4]
    low_mood_prod = [d['tasks'] + d['habits'] for d in data if d['mood'] and d['mood'] <= 2]
    
    avg_high = sum(high_mood_prod) / len(high_mood_prod) if high_mood_prod else 0
    avg_low = sum(low_mood_prod) / len(low_mood_prod) if low_mood_prod else 0
    
    # Day of week stats
    dow_stats = {}
    for d in data:
        dow = d['day_of_week']
        if dow not in dow_stats: dow_stats[dow] = []
        dow_stats[dow].append(d['tasks'] + d['habits'])
    
    dow_avgs = {k: sum(v)/len(v) for k, v in dow_stats.items()}
    best_dow = max(dow_avgs, key=dow_avgs.get)
    worst_dow = min(dow_avgs, key=dow_avgs.get)

    # Prepare data for Gemini
    data_summary = f"""
ULTIMELE 30 ZILE:
- Avg productivity (tasks+habits) on Good Mood (>=4): {avg_high:.1f}
- Avg productivity (tasks+habits) on Bad Mood (<=2): {avg_low:.1f}
- Best Day of Week: {best_dow} (avg {dow_avgs[best_dow]:.1f})
- Worst Day of Week: {worst_dow} (avg {dow_avgs[worst_dow]:.1f})

TIMELINE DATA (Last 10 days for context):
{data[-10:]}
"""

    system_instruction = """
Ești Lora, un AI 'second brain'. Analizează pattern-urile de productivitate și mood ale utilizatorului.
Pe baza datelor, generează 2-3 insights specifice și utile în română.
Fii concret, nu generic. 
Exemplu bun: 'Marțea ești cel mai productiv — 40% mai multe tasks completate.'
Exemplu rău: 'Încearcă să ai un mood mai bun pentru productivitate.'

Maxim 100 de cuvinte. Style: direct, calm, observator.
"""

    insight = await get_proactive_response(system_instruction, data_summary)
    return insight

async def handle_insight_intent(pool, intent: str, data: Dict[str, Any]) -> Tuple[str, Any]:
    if intent == "get_insights":
        reply = await generate_insights(pool)
        return reply, None
    return "Insights module active!", None
