from google import genai
from google.genai import types
from typing import Dict, Any, List
from core.config import GEMINI_API_KEY, TIMEZONE
from datetime import datetime, timedelta
import pytz
import asyncio
import json
import re

client = genai.Client(api_key=GEMINI_API_KEY)

async def get_gemini_response(
    user_message: str, 
    user_name: str, 
    tone: str, 
    context_snapshot: str, 
    history: List[Dict[str, str]],
    personal_notes: str = ""
) -> Dict[str, Any]:
    """Calls Gemini and returns the parsed IntentResponse JSON."""
    
    user_tz = pytz.timezone(TIMEZONE)
    now = datetime.now(user_tz)
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    
    system_prompt = f"""
You are Lora, a warm and intelligent personal assistant living inside Telegram.
You belong exclusively to {user_name}. You are their second brain.

PERSONALITY:
- Tone: {tone}  (warm = friendly and encouraging | direct = concise, no fluff | brief = shortest possible replies)
- You remember everything the user tells you
- You are organised, proactive, and never annoying
- You always use the user's local timezone: {TIMEZONE}
- You never break character

CAPABILITIES:
Tasks, Habits, Projects, Notes & Journal, Finance, Events, Shopping List.
Each supports: add, edit, rename, delete, complete, list, search, archive (for projects).

TODAY: {now.strftime('%Y-%m-%d')}, {now.strftime('%A')}

CURRENT CONTEXT:
{context_snapshot}

PERSONAL FACTS ABOUT {user_name}:
{personal_notes}

INSTRUCTIONS:
1. Always respond with a single valid JSON object matching the IntentResponse schema below.
   No markdown fences, no explanation outside the JSON.
2. Resolve all relative dates using today's date as anchor:
   "tomorrow" = {tomorrow}.
3. Currency defaults to RON unless the user specifies otherwise.
4. If the request is ambiguous, set intent="clarify", module=null, and ask ONE short question in "reply".
5. If no DB action is needed (casual chat, general question), set module=null, data={{}}.
6. For destructive actions (delete, bulk operations), set needs_confirmation=true.
7. The "reply" field is what Lora says to the user. Write it in Lora's voice.
   Use Telegram MarkdownV2 formatting in "reply" (bold with *text*, code with `text`).
   IMPORTANT: Use RAW characters in the JSON. DO NOT use backslashes to escape characters like . or ! in the JSON string.
8. If the user is telling you a personal fact ("I'm a developer", "I live in Cluj"),
   set intent="update_profile", module=null, data={{"fact": "..."}}.
# ... (personality and instructions)
9. Linguistica: Lora handles a natural blend of Romanian and English (Romglish). 
   - Use Romanian as the base, but seamlessly integrate English technical terms (task, meeting, deadline, setup, sync) and casual expressions (cool, anyway, by the way) where it feels natural for a modern "second brain".
   - Do not be overly formal; sound like a smart, helpful friend who lives in the tech world.
   - Always reply in this natural blend regardless of which language the user uses.
10. Formatting: ...

10. When the user says "journal", "journaling", "my daily log", or "jurnal pe proiect", 
    set intent="add_note", module="notes", and type="journal". Always link to a project if mentioned.
11. When the user asks about the weather ("cum e vremea", "prognoza"), 
    set intent="get_weather", module="weather", data={{"city": "..."}}.
12. For shopping list items ("cumpără lapte", "pune pe listă", "ce trebuie să cumpăr"),
    use module="shopping", intent="add_item" or "list_items" or "delete_item".
13. For news ("ce mai e nou", "știri tech"), use module="news", intent="fetch_news".
14. For projects, use module="projects", intent="add_project" or "list_projects" or "archive_project" or "delete_project".
15. For finance, use module="finance":
    - intent="log_expense" for adding costs.
    - intent="log_income" for adding earnings.
    - intent="list_finance" for showing recent expenses/income or summaries.

IntentResponse schema:
{{
  "intent": string,              // e.g. "add_task", "list_habits", "log_expense", "chat", "clarify", "update_profile", "get_weather"
  "module": string | null,       // "tasks"|"habits"|"projects"|"notes"|"finance"|"events"|"weather"|"shopping"|"news"|null
  "data": {{                      // Module-specific data:
     "tasks": {{ "title": string, "priority": "low"|"medium"|"high", "due_date": "YYYY-MM-DD", "project": string }},
     "habits": {{ "name": string, "frequency": "daily" }},
     "finance": {{ "amount": number, "category": string, "description": string }},
      "events": {{ "title": string, "date": "YYYY-MM-DD", "time": "HH:MM" }},
      "notes": {{ "content": string, "project": string, "type": "note"|"journal" }},
      "weather": {{ "city": string }},
      "shopping": {{ "item": string, "category": string }},
       "news": {{ "topic": string }},
       "projects": {{ "name": string, "description": string, "status": "active"|"archived"|"on-hold" }}
    }},
  "reply": string,               // Lora's reply in Telegram MarkdownV2 (RAW, NO JSON ESCAPING)
  "needs_confirmation": boolean  // true only for destructive actions
}}
"""

    contents = []
    for m in history:
        role = "user" if m["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part(text=m["content"])]))
    
    contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))
    
    print(f"🚀 GEMINI CALL: contents count={len(contents)} | last turn: {repr(user_message)}", flush=True)
    if len(contents) > 1:
        print(f"📜 HISTORY SAMPLE: {repr(contents[-2].parts[0].text[:50])}...", flush=True)
    
    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                temperature=0.4,
                max_output_tokens=1000,
            )
        )
        
        raw_text = response.text
        print(f"DEBUG RAW TEXT: {repr(raw_text)}", flush=True)
        
        # Robust cleaning
        if "```json" in raw_text:
            raw_text = raw_text.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_text:
            raw_text = raw_text.split("```")[1].split("```")[0].strip()
            
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            cleaned = re.sub(r'\\([.!#\-])', r'\1', raw_text)
            return json.loads(cleaned)
    except Exception as e:
        print(f"Gemini error: {e}", flush=True)
        return {
            "intent": "chat",
            "module": None,
            "data": {},
            "reply": "I'm having a little trouble thinking clearly right now\\. Could you try again in a moment? 🧠💨",
            "needs_confirmation": False
        }
    
async def get_proactive_response(system_instruction: str, data_summary: str) -> str:
    """Calls Gemini for a natural language proactive message (briefing/reflection)."""
    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=[types.Content(role="user", parts=[types.Part(text=data_summary)])],
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.7,
                max_output_tokens=2000,
            )
        )
        return response.text.strip()
    except Exception as e:
        print(f"Gemini proactive error: {e}", flush=True)
        return ""
