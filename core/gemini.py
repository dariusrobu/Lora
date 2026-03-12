import json
import google.generativeai as genai
from typing import Dict, Any, List
from core.config import GEMINI_API_KEY, TIMEZONE
from datetime import datetime, timedelta
import pytz

genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=genai.GenerationConfig(
        response_mime_type="application/json",
        temperature=0.4,
        max_output_tokens=1000,
    )
)

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
Tasks, Habits, Projects, Notes & Journal, Finance, Events.
Each supports: add, edit, rename, delete, complete, list, search.

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
8. If the user is telling you a personal fact ("I'm a developer", "I live in Cluj"),
   set intent="update_profile", module=null, data={{"fact": "..."}}.

IntentResponse schema:
{{
  "intent": string,              // e.g. "add_task", "list_habits", "log_expense", "chat", "clarify", "update_profile"
  "module": string | null,       // "tasks"|"habits"|"projects"|"notes"|"finance"|"events"|null
  "data": object,                // structured data extracted from the message
  "reply": string,               // Lora's reply in Telegram MarkdownV2
  "needs_confirmation": boolean  // true only for destructive actions
}}
"""

    # Format history for Gemini SDK
    chat = model.start_chat(history=[]) # History is passed manually to system prompt or as turns
    
    # We build a final prompt that includes history context
    history_str = "\n".join([f"{m['role']}: {m['content']}" for m in history])
    
    final_prompt = f"{system_prompt}\n\nCONVERSATION HISTORY:\n{history_str}\n\nUSER: {user_message}"
    
    try:
        response = await asyncio.to_thread(model.generate_content, final_prompt)
        return json.loads(response.text)
    except Exception as e:
        print(f"Gemini error: {e}")
        # Retry logic if needed, or fallback
        return {
            "intent": "chat",
            "module": None,
            "data": {},
            "reply": "I'm having a little trouble thinking clearly right now. Could you try again in a moment? 🧠💨",
            "needs_confirmation": False
        }

import asyncio # Needed for to_thread
