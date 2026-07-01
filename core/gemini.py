from typing import Dict, Any, List
from core.config import TIMEZONE
from datetime import datetime, timedelta
import pytz
import asyncio
import json
import logging
import os
import re
from pydantic import BaseModel, Field, model_validator
from core.context import build_temporal_context
from ollama import AsyncClient
from google import genai as google_genai
from core.config import OLLAMA_HOST, OLLAMA_MODEL

# Ollama client (local LLM)
_ollama_client = AsyncClient(host=OLLAMA_HOST)

# Google Generative AI client — used ONLY for embeddings
_google_genai_client = google_genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))

# Resilience state
_api_available = True
_failure_count = 0


async def get_embedding(text: str) -> List[float]:
    """
    Generates an embedding for the given text using Google text-embedding-005.
    """
    if not text:
        return []

    try:
        result = await asyncio.to_thread(
            _google_genai_client.models.embed_content,
            model="text-embedding-005",
            contents=text,
        )
        return result.embeddings[0].values
    except Exception as e:
        logging.error(f"Error generating embedding: {e}")
        return []


def preprocess_text(text: str) -> str:
    """
    Applies basic normalizations and corrections for common Romanian typos and abbreviations.
    """
    if not text:
        return text

    # Use regex for word boundary matching
    # Normalizations: abbreviations and common words without diacritics
    norm_map = {
        r"\bazi\b": "astăzi",
        r"\bsapt\b": "săptămâna",
        r"\bmin\b": "minute",
        r"\bmancare\b": "mâncare",
        r"\bcheltuiala\b": "cheltuială",
        r"\bcat\b": "cât",
        r"\bsa\b": "să",
        r"\bsutn\b": "sunt",
        r"\bm[t|g]g\b": "meeting",
        r"\bsedinta\b": "ședință",
        r"\bfinante\b": "finance",
        r"\bproiectul\b": "proiect",
    }

    processed = text.lower()
    for pattern, replacement in norm_map.items():
        processed = re.sub(pattern, replacement, processed)

    return processed


class FinanceEntry(BaseModel):
    amount: float | None = Field(
        default=None, description="Financial transaction amount"
    )
    category: str | None = Field(default=None, description="Category name")
    description: str | None = Field(
        default=None, description="Detailed description or item name"
    )
    type: str | None = Field(
        default=None, description="Type of transaction: expense, income"
    )


class IntentData(BaseModel):
    # Task / Project fields
    title: str | None = Field(
        default=None, description="Title of task, event, reminder, skill, note, etc."
    )
    priority: str | None = Field(
        default=None, description="Priority level: high, medium, low"
    )
    due_date: str | None = Field(
        default=None, description="Due date or target date, e.g. YYYY-MM-DD"
    )
    project: str | None = Field(
        default=None, description="Project name or category association"
    )
    status: str | None = Field(
        default=None, description="Status level or state of item"
    )
    task_id: int | None = Field(default=None, description="Task ID")
    name: str | None = Field(
        default=None, description="Name of project, skill, habit, etc."
    )
    description: str | None = Field(
        default=None, description="Detailed description or body content"
    )
    deadline: str | None = Field(default=None, description="Deadline of project, etc.")
    category: str | None = Field(default=None, description="Category name")
    project_id: int | None = Field(default=None, description="Project ID")
    progress_pct: float | None = Field(
        default=None, description="Project progress percentage"
    )

    # Finance fields
    amount: float | None = Field(
        default=None, description="Financial transaction amount"
    )
    type: str | None = Field(
        default=None, description="Type of transaction: expense, income, etc."
    )
    limit: float | None = Field(default=None, description="Finance budget limit")
    monthly_limit: float | None = Field(default=None, description="Monthly limit")
    entries: List[FinanceEntry] | None = Field(
        default=None,
        description="List of transaction entries, each with amount, category, description, and type"
    )

    # Skills / Habits fields
    is_active: bool | None = Field(default=None, description="Is skill/habit active")
    target_days: List[int] | None = Field(
        default=None, description="Days of week for habit target"
    )
    habit_id: int | None = Field(default=None, description="Habit ID")
    skill_name: str | None = Field(default=None, description="Skill name")
    value: float | None = Field(
        default=None, description="Log value for skill progress"
    )

    # Health fields
    mood: int | None = Field(default=None, description="Mood rating")
    energy: int | None = Field(default=None, description="Energy rating")
    cigarettes: int | None = Field(default=None, description="Number of cigarettes")
    sleep_hours: float | None = Field(default=None, description="Hours of sleep")
    water_ml: int | None = Field(default=None, description="Water intake in ml")
    log_date: str | None = Field(default=None, description="Health log date")

    # Workout fields
    sport_name: str | None = Field(default=None, description="Sport name")
    duration_min: int | None = Field(default=None, description="Duration in minutes")
    exercises: List[str] | None = Field(
        default=None, description="List of exercises in workout"
    )
    pr_id: int | None = Field(default=None, description="Personal record ID")
    sport_id: int | None = Field(default=None, description="Sport ID")

    # Event / Calendar fields
    event_time: str | None = Field(default=None, description="Event time")
    date: str | None = Field(default=None, description="Event date")
    event_date: str | None = Field(default=None, description="Specific event date")
    summary: str | None = Field(default=None, description="Calendar summary")
    start: str | None = Field(default=None, description="Start date/time")
    end: str | None = Field(default=None, description="End date/time")
    location: str | None = Field(default=None, description="Location name")

    # Note / Focus / Integration fields
    body: str | None = Field(default=None, description="Body content of note/email")
    task_description: str | None = Field(
        default=None, description="Focus task description"
    )
    hour: int | None = Field(default=None, description="Hour of alarm")
    minute: int | None = Field(default=None, description="Minute of alarm")
    label: str | None = Field(default=None, description="Alarm label")
    to: str | None = Field(default=None, description="Recipient of email")
    subject: str | None = Field(default=None, description="Subject of email")
    service: str | None = Field(default=None, description="Integration service")

    # General / Other fields
    confirmed: bool | None = Field(default=None, description="Confirmation status")
    id: int | None = Field(default=None, description="Item ID")
    item_id: int | None = Field(default=None, description="Target item ID")


class MemoryExtract(BaseModel):
    fact: str = Field(description="The fact to memorize")
    category: str = Field(default="general", description="Category of the fact")
    confidence: float = Field(default=1.0, description="Confidence score")


class SecondaryIntent(BaseModel):
    intent: str = Field(
        description="Identified action, e.g. add_task, chat, log_expense"
    )
    module: str | None = Field(
        description="The target module, e.g. tasks, projects, finance."
    )
    data: IntentData = Field(
        description="Module-specific structured data extracted from the user message"
    )
    reply: str = Field(description="Assistant reply formatted in MarkdownV2")
    needs_confirmation: bool = Field(
        description="True if the action requires confirmation"
    )
    needs_agent: bool = Field(
        description="True if the query is complex and needs multi-step agent reasoning"
    )
    confidence: float = Field(default=1.0, description="Certitude score")


class IntentResponse(BaseModel):
    intent: str = Field(
        description="Identified action, e.g. add_task, chat, log_expense"
    )
    module: str | None = Field(
        description="The target module, e.g. tasks, projects, finance. Use null/None for general chat or intent='chat'."
    )
    data: IntentData = Field(
        description="Module-specific structured data extracted from the user message"
    )
    reply: str = Field(description="Assistant reply formatted in MarkdownV2")
    needs_confirmation: bool = Field(
        description="True if the action is destructive and requires user confirmation"
    )
    needs_agent: bool = Field(
        description="True if the query is complex and needs multi-step agent reasoning"
    )
    agent_tools_needed: List[str] | None = Field(
        default=None,
        description="List of tools needed by the agent if needs_agent is True",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Scorul de certitudine al intent-ului detectat. Sub 0.7 = incert.",
    )
    source: str = Field(
        default="text", pattern="^(text|voice)$", description="Sursa mesajului"
    )
    clarification_needed: bool = Field(
        default=False,
        description="True dacă mesajul e ambiguu și necesită clarificare înainte de execuție",
    )
    clarification_question: str | None = Field(
        default=None,
        description="Întrebarea de clarificare dacă clarification_needed e True",
    )
    memory_extracts: List[MemoryExtract] | None = Field(
        default=None,
        description="Fapte importante de memorat extrase din mesaj: {fact, category, confidence, expires_at?}",
    )
    additional_intents: List[SecondaryIntent] | None = Field(
        default=None,
        description="Lista de intenții secundare dacă mesajul conține mai multe acțiuni simultane",
    )

    @model_validator(mode="after")
    def validate_temporal_bounds(self) -> "IntentResponse":
        """
        Validates date fields in the 'data' dictionary.
        If a date is > 1 year in the past or > 2 years in the future,
        confidence is lowered to 0.5.
        """
        if not self.data:
            return self

        user_tz = pytz.timezone(TIMEZONE)
        now = datetime.now(user_tz)
        # Convert to offset-naive for comparison if parsed_date is naive
        # Or better, make parsed_date aware if needed. ISO dates from Gemini are naive.
        now_naive = now.replace(tzinfo=None)

        one_year_ago = now_naive - timedelta(days=365)
        two_years_ahead = now_naive + timedelta(days=365 * 2)

        # Common date keys in Lora's schema
        date_keys = [
            "due_date",
            "date",
            "event_date",
            "start_date",
            "end_date",
            "exam_date",
        ]

        data_dict = (
            self.data.model_dump()
            if hasattr(self.data, "model_dump")
            else (self.data or {})
        )
        for key in date_keys:
            val = data_dict.get(key)
            if not val or not isinstance(val, str):
                continue

            try:
                # Try parsing ISO format YYYY-MM-DD
                parsed_date = datetime.strptime(val[:10], "%Y-%m-%d")

                if parsed_date < one_year_ago or parsed_date > two_years_ahead:
                    print(
                        f"⚠️ Temporal Out-of-Bounds: {key}={val}. Lowering confidence."
                    )
                    self.confidence = min(self.confidence, 0.5)
                    self.clarification_needed = True
                    if not self.clarification_question:
                        self.clarification_question = f"Sigur data {val} este corectă?"
            except ValueError:
                continue  # Not a date or wrong format

        return self


async def _log_api_downtime(pool, error_type: str, user_id: int = None):
    """Logs API downtime to execution_log."""
    if not pool:
        return
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO execution_log (user_id, success, error_type) VALUES ($1, FALSE, $2)",
                user_id,
                error_type,
            )
    except Exception as e:
        print(f"Failed to log downtime: {e}")


async def _call_cerebras_with_retry(pool, user_id, api_func, *args, **kwargs):
    """Wrapper for Cerebras API calls with retry logic and state tracking."""
    global _api_available, _failure_count

    delays = [2, 4]
    last_err = None

    for i in range(len(delays) + 1):
        try:
            response = await api_func(*args, **kwargs)

            recovery_prefix = ""
            if not _api_available:
                recovery_prefix = "Sunt din nou online\\! 🚀\\n\n"
                print("Cerebras API recovered! 🚀")

            _api_available = True
            _failure_count = 0
            return response, recovery_prefix

        except asyncio.TimeoutError as e:
            last_err = e
            print(f"Cerebras API attempt {i + 1} failed (timeout): {e}")

            if i < len(delays):
                await asyncio.sleep(delays[i])
                continue

            _failure_count += 1
            if _failure_count >= 3:
                _api_available = False

            if pool:
                await _log_api_downtime(pool, "api_unavailable", user_id)
            raise last_err
        except Exception as e:
            print(f"Cerebras API attempt {i + 1} failed (non-transient): {e}")
            raise e


def dereference_schema(schema: dict) -> dict:
    """Recursively inlines $defs references and forces additionalProperties=False for Groq JSON schema."""
    defs = schema.get("$defs", {})

    def resolve(val):
        if isinstance(val, dict):
            if "$ref" in val:
                ref_path = val["$ref"]
                if ref_path.startswith("#/$defs/"):
                    def_name = ref_path.split("/")[-1]
                    resolved = resolve(defs[def_name])
                    merged = {k: resolve(v) for k, v in val.items() if k != "$ref"}
                    resolved_dict = {**resolved, **merged}
                else:
                    resolved_dict = {k: resolve(v) for k, v in val.items()}
            else:
                resolved_dict = {k: resolve(v) for k, v in val.items()}

            if resolved_dict.get("type") == "object":
                resolved_dict["additionalProperties"] = False
            if "pattern" in resolved_dict:
                del resolved_dict["pattern"]
            return resolved_dict
        elif isinstance(val, list):
            return [resolve(x) for x in val]
        return val

    dereferenced = resolve(schema)
    if "$defs" in dereferenced:
        del dereferenced["$defs"]
    return dereferenced


def _get_retry_delay(err_str: str, default_delay: float) -> float:
    match = re.search(r"Please retry in (\d+(?:\.\d+)?)s", err_str)
    if match:
        return float(match.group(1)) + 1.0
    match = re.search(r"retryDelay':\s*'(\d+)s'", err_str)
    if match:
        return float(match.group(1)) + 1.0
    return default_delay


async def generate_structured_response(messages: list, schema: BaseModel, model: str | None = None) -> str:
    """Generates a structured JSON response using Ollama. Falls back to OLLAMA_MODEL env."""
    effective_model = model or OLLAMA_MODEL
    print(f"🚀 OLLAMA STRUCTURED CALL: {len(messages)} messages | model={effective_model}", flush=True)

    max_retries = 3
    delay = 2.0

    for attempt in range(max_retries):
        try:
            response = await _ollama_client.chat(
                model=effective_model,
                messages=messages,
                format="json",
                options={"temperature": 0.3, "num_predict": 4096},
            )
            return response["message"]["content"]
        except Exception as e:
            err_str = str(e)
            is_transient = "timeout" in err_str.lower() or "connection" in err_str.lower()
            if is_transient and attempt < max_retries - 1:
                print(f"⚠️ Ollama structured warning (attempt {attempt+1}/{max_retries}): {e}. Retrying in {delay}s...", flush=True)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30.0)
            else:
                raise e


async def generate_text_response(messages: list, model: str | None = None) -> str:
    """Generates a plain text response using Ollama. Falls back to OLLAMA_MODEL env."""
    effective_model = model or OLLAMA_MODEL
    print(f"🚀 OLLAMA TEXT CALL: {len(messages)} messages | model={effective_model}", flush=True)

    max_retries = 3
    delay = 2.0

    for attempt in range(max_retries):
        try:
            response = await _ollama_client.chat(
                model=effective_model,
                messages=messages,
                options={"temperature": 0.3, "num_predict": 2048},
            )
            return response["message"]["content"].strip()
        except Exception as e:
            err_str = str(e)
            is_transient = "timeout" in err_str.lower() or "connection" in err_str.lower()
            if is_transient and attempt < max_retries - 1:
                print(f"⚠️ Ollama text warning (attempt {attempt+1}/{max_retries}): {e}. Retrying in {delay}s...", flush=True)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30.0)
            else:
                raise e


async def get_gemini_response(
    pool,
    user_id: int,
    user_message: str,
    user_name: str,
    tone: str,
    context_snapshot: str,
    history: List[Dict[str, str]],
    personal_notes: str = "",
    system_hint: str = "",
    voice_uri: str | None = None,
    model: str | None = None,
) -> Dict[str, Any]:
    """Calls LLM and returns the parsed IntentResponse JSON. `model` overrides OLLAMA_MODEL env."""

    temporal_context = build_temporal_context(TIMEZONE)

    # Pre-process user message for typo tolerance
    user_message = preprocess_text(user_message)

    user_tz = pytz.timezone(TIMEZONE)
    now = datetime.now(user_tz)
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")

    system_prompt = f"""## IDENTITATE
Tu ești Lora — asistentul personal al lui [NUMELE_USER], în Telegram.
Vorbești Romglish (română + termeni tehnici englezi).
Ton: {{tone}}. NICIODATĂ: "Sigur!", "Cu plăcere!", "Bineînțeles!"."""
    system_prompt = system_prompt.replace("[NUMELE_USER]", user_name)
    system_prompt = system_prompt.replace("{{tone}}", tone)

    system_prompt += f"""

{temporal_context}

CONVERSAȚIE RECENTĂ:
{{_format_history_for_prompt(history)}}

## MODE
- CHAT (module=null, intent="chat"): userul discută liber, nu forța module. Sugerează acțiuni, nu executa.
- ACTION (module=X, intent=Y): userul cere EXPLICIT o acțiune. Extrage datele, setează intent-ul corect.

## REGULI
1. Multi-intent: dacă mesajul conține mai multe acțiuni, primary=intent principal, additional_intents=restul
2. Confidence < 0.7 dacă lipsește un element cheie → clarification_needed=true
3. needs_agent=true pentru analize complexe sau întrebări ce necesită web search
4. memory_extracts: extrage fapte noi despre user (preference/pattern/personal/achievement)
5. Dacă voice_uri e prezent, adaptează reply-ul la tonul vocal al userului

## CONTEXT
Azi: {{now.strftime("%Y-%m-%d")}}, {{now.strftime("%A")}}
{{context_snapshot}}
Despre {{user_name}}:
{{personal_notes}}

## MODULE ȘI INTENT-URI
tasks:    add_task, list_tasks, complete_task, delete_task, edit_task
          Data: title, due_date (YYYY-MM-DD), project, priority (high|medium|low)
projects: add_project, list_projects, view_projects, update_project, delete_project
finance:  finance_log (entries=[amount,category,type,description]), finance_summary, delete_finance, finance_undo
events:   add_event, add_reminder, list_events, delete_event, edit_event_reminder
          Data: title, event_date (YYYY-MM-DD), event_time (HH:MM)
          Regulă: "în X ore" calculează time = acum + X ore
skills:   log_skill, view_skills, add_habit, log_habit, list_habits, delete_habit
          Data: skill_name, value (float), weight (float|null)
health:   health_log (sleep_hours,water_ml,weight_kg,cigarettes,nutrition), log_cigarettes, log_water,
          health_summary, health_chart, health_status_today
          Regulă apă: "2L"→2000, "un pahar"→250. Somn: "7h30"→7.5.
nutrition: meal_log (meal_type,description,calories,protein,carbs,fat), nutrition_summary, nutrition_target
          Regulă: calculează macro direct, nu returna null.
workout:  workout_log (sport_name,duration_min,calories,notes,exercises), workout_list, workout_stats, workout_prs
          "sală"→"Gym", "1h30"→90. exercises: name, sets, reps, weight_kg.
university: uni_add_subject, uni_list, uni_log_attendance, uni_add_grade, uni_add_exam, uni_exams,
            uni_restante, uni_attendance_warning, uni_update_subject, uni_delete_subject,
            uni_update_grade, uni_delete_grade, uni_update_exam, uni_delete_exam
schedule: schedule_today, schedule_week
reading:  reading_add, reading_update, reading_complete, reading_note, reading_list, reading_stats
          Data: title, author, total_pages, pages_read, rating
goals:    add_goal (title,time_horizon,linked_keywords), update_goal, complete_goal, add_subtask,
          complete_subtask, view_goals, delete_goal
shopping: add_item, list_items, delete_item, clear_items (Data: item, category)
wishlist: add_wish, list_wish, delete_wish (Data: item, description, price, priority)
travel:   travel_add (items,list_name,trip_type), travel_list, travel_check, travel_packed, travel_clear
mood:     log_mood (mood: great|good|neutral|bad|terrible), get_mood_chart
focus:    focus_start (duration_min), focus_stop, focus_list
planner:  time_block
memory:   memory_view, memory_delete, memory_optimize, memory_recall, memory_search
weather:  get_weather (city)
calendar_module: calendar_today, calendar_week, calendar_add (summary,start,end,location), calendar_sync
insights: get_insights, ask_insights
integrations: mac_note_create, mac_alarm_set (hour,minute,label), email_send (to,subject,body), email_check
news:     get_tech_news (topic)
correct_last: "undo", "am greșit" (Data: correction_text)
trigger_morning_briefing: când userul se trezește
"""

    messages = [{"role": "system", "content": system_prompt}]

    for m in history:
        role = "user" if m["role"] == "user" else "assistant"
        messages.append({"role": role, "content": m["content"]})

    # Add current user message
    # Note: Ollama python doesn't officially support passing multiple parts with audio
    # like Gemini yet, so we just pass the text. Voice transcription already happened.
    messages.append({"role": "user", "content": user_message})

    print(
        f"🚀 OLLAMA CALL: messages count={len(messages)} | last turn: {repr(user_message)} | model={OLLAMA_MODEL}",
        flush=True,
    )

    try:
        raw_text = await generate_structured_response(messages, IntentResponse, model=model)
        recovery_prefix = ""
        print(f"DEBUG RAW TEXT: {repr(raw_text[:300])}", flush=True)

        # Robust JSON parsing with multiple fallback strategies
        parsed = None

        # Strategy 1: Direct parse (works for short, clean responses)
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            pass

        # Strategy 2: Extract reply separately, parse the rest
        if parsed is None:
            try:
                reply_match = re.search(
                    r'"reply"\s*:\s*"(.*?)",\s*\n\s*"needs_confirmation"',
                    raw_text,
                    re.DOTALL,
                )
                if reply_match:
                    original_reply = reply_match.group(1)
                    clean_json = (
                        raw_text[: reply_match.start(1)]
                        + "__PLACEHOLDER__"
                        + raw_text[reply_match.end(1) :]
                    )
                    parsed = json.loads(clean_json)
                    parsed["reply"] = original_reply.replace("\\n", "\n").replace(
                        '\\"', '"'
                    )
                else:
                    cleaned = raw_text.replace('\\\\"', "'")
                    parsed = json.loads(cleaned)
            except json.JSONDecodeError:
                pass

        # Strategy 3: Regex extraction as last resort
        if parsed is None:
            try:
                intent_m = re.search(r'"intent"\s*:\s*"([^"]+)"', raw_text)
                module_m = re.search(r'"module"\s*:\s*(?:"([^"]+)"|null)', raw_text)
                agent_m = re.search(r'"needs_agent"\s*:\s*(true|false)', raw_text)
                reply_m = re.search(r'"reply"\s*:\s*"(.*?)",\s*\n', raw_text, re.DOTALL)
                reply_text = (
                    reply_m.group(1).replace("\\n", "\n").replace('\\"', '"')
                    if reply_m
                    else "Scuze, nu am putut procesa răspunsul."
                )
                parsed = {
                    "intent": intent_m.group(1) if intent_m else "chat",
                    "module": module_m.group(1) if module_m else None,
                    "data": {},
                    "reply": reply_text,
                    "needs_confirmation": False,
                    "needs_agent": agent_m.group(1) == "true" if agent_m else False,
                    "confidence": 1.0,
                }
                print(
                    f"⚠️ JSON FALLBACK: Used regex extraction for intent={parsed['intent']}",
                    flush=True,
                )
            except Exception as fallback_err:
                print(f"Gemini JSON fallback also failed: {fallback_err}", flush=True)
                parsed = {
                    "intent": "chat",
                    "module": None,
                    "data": {},
                    "reply": "Am avut o problemă la procesarea răspunsului. Încearcă din nou.",
                    "needs_confirmation": False,
                    "needs_agent": False,
                    "confidence": 1.0,
                }

        if isinstance(parsed, list) and len(parsed) > 0:
            parsed = parsed[0]

        # Add recovery message if needed
        if recovery_prefix:
            parsed["reply"] = recovery_prefix + parsed.get("reply", "")

        # Fire-and-forget: extract personal facts in background without blocking
        # (DISABLED: now handled via memory_extracts in IntentResponse for efficiency)
        # asyncio.create_task(
        #     extract_and_save_facts(
        #         pool, client, user_id, user_message, parsed.get("reply", "")
        #     )
        # )

        return parsed
    except Exception as e:
        print(f"Gemini error: {e}", flush=True)
        import traceback

        traceback.print_exc()
        return {
            "intent": "api_unavailable",
            "module": None,
            "data": {},
            "reply": "Sunt offline momentan, încearcă din nou în câteva minute. 🔧",
            "needs_confirmation": False,
        }


async def analyze_intent(pool, text: str, context: str = "", model: str | None = None) -> Dict[str, Any]:
    """Legacy wrapper for get_gemini_response. `model` overrides OLLAMA_MODEL env."""
    from core.config import TELEGRAM_USER_ID

    return await get_gemini_response(
        pool=pool,
        user_id=TELEGRAM_USER_ID,
        user_message=text,
        user_name="User",
        tone="direct",
        context_snapshot=context,
        history=[],
        system_hint="Analizează acest mesaj și returnează intent-ul corect.",
        model=model,
    )


async def get_proactive_response(system_instruction: str, data_summary: str, model: str | None = None) -> str:
    """Calls LLM for a natural language proactive message (briefing/reflection). `model` overrides OLLAMA_MODEL."""
    tone_rules = """
REGULI GLOBALE DE TON (oricând ești proactivă):

STIL VOCAL & CONȚINUT:
- Scrie ca și cum vorbești (natural), nu ca un document.
- Propoziții scurte. TRANZIȚII fluide, nu bullet-uri.
- TEXT BRIEFING: Fii detaliată, organizată și COMPLETĂ. MAXIM 500 cuvinte.
- PODCAST/VOCE: MAXIM 150 cuvinte. Fii concisă, zero comentarii inutile.

CORECȚIE VOCABULAR:
- EXCLUSIV ROMÂNĂ. Excepții permise: task, habit, meeting, gym, chess, focus.
- Ton cald dar DIRECT. Fără hype, fără superlative exagerate.

FORMATARE:
- Telegram MarkdownV2: bold cu *text*, code cu `text`, italic cu _text_.
- Dacă un task sau proiect conține caractere speciale (-, _, *), asigură-te că închizi corect formatarea bold/italic sau nu o folosi.
- NU folosi JSON, nu pune ghilimele la început/sfârșit, răspunde cu textul RAW.
"""
    full_instruction = system_instruction + tone_rules
    try:
        messages = [
            {"role": "system", "content": full_instruction},
            {"role": "user", "content": data_summary},
        ]
        text = await generate_text_response(messages, model=model)
        return text
    except Exception as e:
        import traceback

        print(f"Gemini proactive error: {type(e).__name__} - {e}", flush=True)
        traceback.print_exc()
        return ""


_voice_logger = logging.getLogger("core.voice_normalize")


async def normalize_voice_text(raw: str, model: str | None = None) -> str:
    """
    Calls Gemini to reformat a raw STT transcript into a clean, unambiguous command.
    Falls back to the original text if the call fails.
    """
    prompt = (
        "Textul următor vine dintr-o transcriere vocală și poate fi informal, fragmentat sau conține bâlbâieli. "
        "Reformulează-l ca o comandă sau un mesaj clar, corectând greșelile gramaticale evidente, dar păstrând EXACT intenția și toate datele (sume, ore, nume, intervale de timp). "
        "Păstrează toate cifrele și unitățile de măsură (ex: 8 ore, 50 lei, 2 litri). "
        "Dacă sunt mai multe acțiuni, separă-le clar. "
        "Nu adăuga informații noi. Răspunde DOAR cu textul reformulat, fără explicații. "
        f"Transcriere: {raw}"
    )
    try:
        messages = [{"role": "user", "content": prompt}]
        normalized = await generate_text_response(messages, model=model)

        _voice_logger.info(
            "VOICE NORMALIZE | original=%r | normalized=%r", raw, normalized
        )
        print(
            f"🎙 VOICE NORMALIZE | original: {repr(raw)} → normalized: {repr(normalized)}",
            flush=True,
        )
        return normalized
    except Exception as e:
        _voice_logger.warning(
            "VOICE NORMALIZE FAILED (%s) — using raw text: %r", e, raw
        )
        print(f"⚠️ VOICE NORMALIZE FAILED ({e}) — using raw: {repr(raw)}", flush=True)
        return raw


def _format_history_for_prompt(history: List[Dict[str, str]]) -> str:
    """Formats history for inclusion in the system prompt."""
    if not history:
        return "Fără istoric recent."

    lines = []
    for m in history:
        role = "U" if m["role"] == "user" else "A"
        lines.append(f"{role}: {m['content']}")
    return "\n".join(lines)
