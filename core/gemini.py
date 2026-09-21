from typing import Dict, Any, List
from core.config import TIMEZONE
from datetime import datetime, timedelta
import pytz
import asyncio
import json
import logging
import re
from pydantic import BaseModel, Field, model_validator
from core.context import build_temporal_context
from ollama import AsyncClient
from core.config import OLLAMA_HOST, OLLAMA_MODEL

logger = logging.getLogger(__name__)

# Ollama is Lora's only LLM runtime.
_ollama_client = AsyncClient(host=OLLAMA_HOST)

# Compatibility alias for legacy agentic code.  Cloud Gemini execution is
# intentionally disabled; router.py falls back to the local agent loop.
client = None

# Resilience state
_api_available = True
_failure_count = 0


async def get_embedding(text: str) -> List[float]:
    """
    Generates an embedding for the given text. Delegates to core.embeddings.
    """
    from core.embeddings import get_embedding as _embed
    return await _embed(text)


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
        two_years_future = now_naive + timedelta(days=730)

        data_dict = self.data.model_dump() if hasattr(self.data, 'model_dump') else self.data
        date_fields = ["due_date", "event_date", "date", "start_date", "end_date", "exam_date"]

        for field_name in date_fields:
            raw_date = data_dict.get(field_name)
            if not raw_date:
                continue
            try:
                parsed_date = datetime.fromisoformat(raw_date) if isinstance(raw_date, str) else raw_date
                if isinstance(parsed_date, datetime):
                    parsed_date_naive = parsed_date.replace(tzinfo=None)
                    if parsed_date_naive < one_year_ago or parsed_date_naive > two_years_future:
                        self.confidence = min(self.confidence, 0.5)
                        break
            except (ValueError, TypeError):
                continue

        return self


class AgentAction(BaseModel):
    action_type: str = Field(
        description="'tool' to execute a tool, 'final' to give final answer to user"
    )
    thought: str = Field(
        description="Brief reasoning about the current step"
    )
    intent: str | None = Field(
        default=None,
        description="The intent/tool name to execute (only when action_type='tool')",
    )
    module: str | None = Field(
        default=None,
        description="The module for the tool (only when action_type='tool')",
    )
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters for the tool (only when action_type='tool')",
    )
    final_reply: str | None = Field(
        default=None,
        description="Final answer to user in Romanian (only when action_type='final')",
    )
    additional_intents: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Additional independent actions detected in the same message",
    )


    @model_validator(mode="after")
    def validate_action(self) -> "AgentAction":
        if self.action_type == "tool" and not self.intent:
            raise ValueError("action_type='tool' requires a non-null intent")
        if self.action_type == "final" and not self.final_reply:
            raise ValueError("action_type='final' requires a non-null final_reply")
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
        logger.error(f"Failed to log downtime: {e}")


async def _call_with_retry(pool, user_id, api_func, *args, **kwargs):
    """Generic retry wrapper retained for local runtime compatibility."""
    global _api_available, _failure_count

    delays = [2, 4]
    last_err = None

    for i in range(len(delays) + 1):
        try:
            response = await api_func(*args, **kwargs)

            recovery_prefix = ""
            if not _api_available:
                recovery_prefix = "Sunt din nou online\\! 🚀\\n\n"
                logger.info("Local LLM recovered! 🚀")

            _api_available = True
            _failure_count = 0
            return response, recovery_prefix

        except asyncio.TimeoutError as e:
            last_err = e
            logger.warning(f"Local LLM attempt {i + 1} failed (timeout): {e}")

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
            logger.error(f"Local LLM attempt {i + 1} failed (non-transient): {e}")
            raise e


def dereference_schema(schema: dict) -> dict:
    """Recursively inline schema references for local structured output."""
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
    """Generates structured JSON locally through Ollama."""
    fallback_model = model or OLLAMA_MODEL
    logger.info("Ollama structured call: %s messages | model=%s", len(messages), fallback_model)
    for attempt in range(3):
        try:
            response = await _ollama_client.chat(
                model=fallback_model,
                messages=messages,
                format="json",
                options={"temperature": 0.3, "num_predict": 4096},
            )
            return response["message"]["content"]
        except Exception:
            if attempt < 2:
                await asyncio.sleep(2)
                continue
            raise


async def generate_text_response(messages: list, model: str | None = None) -> str:
    """Generates text locally through Ollama."""
    fallback_model = model or OLLAMA_MODEL
    logger.info(f"🔄 FALLBACK: Ollama {fallback_model} for text")
    for attempt in range(3):
        try:
            response = await _ollama_client.chat(
                model=fallback_model,
                messages=messages,
                options={"temperature": 0.3, "num_predict": 2048},
            )
            return response["message"]["content"].strip()
        except Exception:
            if attempt < 2:
                await asyncio.sleep(2)
                continue
            raise


async def get_llm_response(
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
    """Calls the local Ollama LLM and returns parsed IntentResponse JSON."""

    temporal_context = build_temporal_context(TIMEZONE)

    # Pre-process user message for typo tolerance
    user_message = preprocess_text(user_message)

    # --- Structured output prompt (short, focused on intent schema) ---
    recent_ctx = _format_history_for_prompt(history[-6:] if len(history) > 6 else history)
    hint = f"\nHINT: {system_hint}" if system_hint else ""
    structured_prompt = f"""You are an intent classifier. Respond ONLY with valid JSON matching this exact schema:

{{
  "intent": "<intent_name>",
  "module": "<module_name>",
  "data": {{}},
  "reply": "<your response in Romanian>",
  "needs_confirmation": false,
  "needs_agent": false,
  "confidence": 0.0-1.0,
  "clarification_needed": false,
  "memory_extracts": null
}}

INTENTS BY MODULE:
chat → general conversation (module=null)
tasks → add_task, list_tasks, complete_task, delete_task, edit_task
projects → add_project, list_projects, update_project, delete_project
events → add_event, list_events, delete_event, edit_event_reminder
finance → finance_log, finance_summary, delete_finance, finance_undo
health → health_log, health_summary
nutrition → meal_log, nutrition_summary
workout → workout_log, workout_list, workout_stats
mood → log_mood
goals → add_goal, view_goals, complete_goal, delete_goal
skills → log_skill, view_skills, add_habit, log_habit
shopping → add_item, list_items, delete_item
reading → reading_add, reading_update, reading_list
travel → travel_add, travel_list
focus → focus_start, focus_stop
weather → get_weather
memory → memory_view, memory_search
schedule → schedule_today, schedule_week
university → uni_add_subject, uni_list, uni_add_grade, uni_add_exam
integrations → mac_note_create, mac_alarm_set
news → get_news (data: {"topic": "politica"|"economie"|"tech"|"general"|"all"|"<custom>"}), get_tech_news

RULES:
- CHAT mode (module=null): user is chatting freely, just reply naturally
- ACTION mode (module=X): user wants something done, extract data
- CONVERSATION mode: answer questions, give advice, and continue the current topic
  naturally; do not invent an action just because a module keyword appears.
- Treat pronouns and relative references ("asta", "cel de mai devreme", "mâine")
  using the recent conversation before asking for clarification.
- If unclear → clarification_needed=true
- reply must be in Romanian (Romglish OK)
- keep reply concise (1-2 sentences)
- ADRESARE STRICTĂ: NICIODATĂ nu folosi numele utilizatorului (NU spune 'Darius', 'Robu' sau niciun alt nume). Adresează-te direct, natural, la persoana a II-a singular.
- FĂRĂ FORMULE DE UMPLUTURĂ: NICIODATĂ nu începe cu "Sigur!", "Cu plăcere!", "Bineînțeles!", "Salut Darius", "Desigur!". Treci direct la subiect.

Recent conversation:
{recent_ctx}

User message: {user_message}{hint}"""

    # --- Full prompt for text generation (rich, contextual replies) ---
    system_prompt = f"""## IDENTITATE & VOCABULAR
Tu ești Lora — asistentul personal inteligent, autonom și direct în Telegram.
Vorbești Romglish natural (bază română fluidă + termeni tehnici uzuali precum task, meeting, deadline, sprint, review, gym, focus, bug).

## REGULI STRICTE DE ADRESARE & VOCABULAR:
1. INTERZIS NUMELE: NICIODATĂ nu folosi numele utilizatorului (NU spune 'Darius', 'Robu' sau orice alt nume propriu). Adresează-te direct, la persoana a II-a singular (ex: "Am adăugat task-ul", "Ai 3 cursuri azi", "Uite lista").
2. FĂRĂ FORMULE DE UMPLUTURĂ: NICIODATĂ nu începe cu "Sigur!", "Cu plăcere!", "Bineînțeles!", "Salut!", "Desigur!".
3. Ton: {tone}. Fii concisă, empatică dar orientată pe eficiență, claritate și acțiune.
4. Răspunsuri concise: 1-2 propoziții pentru acțiuni, fără poliloghie inutilă.

{temporal_context}

CONVERSAȚIE RECENTĂ:
{_format_history_for_prompt(history)}

## MODE
- CHAT (module=null, intent="chat"): userul discută liber, nu forța module. Sugerează acțiuni, nu executa.
- ACTION (module=X, intent=Y): userul cere EXPLICIT o acțiune. Extrage datele, setează intent-ul corect.

## REGULI
1. Multi-intent: dacă mesajul conține mai multe acțiuni, primary=intent principal, additional_intents=restul
2. Confidence < 0.7 dacă lipsește un element cheie → clarification_needed=true
3. needs_agent=true pentru analize complexe sau întrebări ce necesită web search
4. memory_extracts: extrage fapte noi despre user (preference/pattern/personal/achievement)
   only when the fact is stable and useful. Never extract passwords, tokens,
   exact financial amounts, or sensitive medical details as long-term memory.
5. Be proactive for planning, routines, and blocked goals: suggest one concrete
   next step, but do not write data or schedule anything without confirmation.
5. Dacă voice_uri e prezent, adaptează reply-ul la tonul vocal al userului

## CONTEXT
Azi: {datetime.now().strftime("%Y-%m-%d")}, {datetime.now().strftime("%A")}
{context_snapshot}
Despre utilizator:
{personal_notes}

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
news:     get_news (topic: "all"|"politica"|"economie"|"tech"|"general"|custom), get_tech_news
correct_last: "undo", "am greșit" (Data: correction_text)
trigger_morning_briefing: când userul se trezește
"""

    # Messages for structured output — short prompt
    structured_messages = [{"role": "system", "content": structured_prompt}]
    structured_messages.append({"role": "user", "content": user_message})

    # Messages for text generation — full context-rich prompt
    text_messages = [{"role": "system", "content": system_prompt}]
    for m in history:
        role = "user" if m["role"] == "user" else "assistant"
        text_messages.append({"role": role, "content": m["content"]})
    text_messages.append({"role": "user", "content": user_message})

    logger.info(f"Ollama call: structured_messages={len(structured_messages)}, full_messages={len(text_messages)} | model={model or OLLAMA_MODEL}")

    try:
        raw_text = await generate_structured_response(structured_messages, IntentResponse, model=model)
        recovery_prefix = ""
        logger.info(f"DEBUG RAW TEXT: {repr(raw_text[:600])}")

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
                logger.warning(f"⚠️ JSON FALLBACK: Used regex extraction for intent={parsed['intent']}")
            except Exception as fallback_err:
                logger.error(f"Gemini JSON fallback also failed: {fallback_err}")
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

        # Validate that the response has required fields
        if not isinstance(parsed, dict) or not parsed.get("intent"):
            logger.warning(f"⚠️ JSON missing or null intent, using fallback. Got: {repr(raw_text[:200])}")
            parsed = {
                "intent": "chat",
                "module": None,
                "data": {},
                "reply": "Scuze, nu am înțeles.",
                "needs_confirmation": False,
                "needs_agent": False,
                "confidence": 1.0,
            }

        # Add recovery message if needed
        if recovery_prefix:
            parsed["reply"] = recovery_prefix + parsed.get("reply", "")

        return parsed
    except Exception as e:
        logger.error(f"Gemini error: {e}", exc_info=True)
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
REGULI GLOBALE DE TON & VOCABULAR:

ADRESARE:
- INTERZIS NUMELE: NICIODATĂ nu folosi numele utilizatorului (NU folosi 'Darius', 'Robu' sau orice alt nume).
- Vorbește direct, la persoana a II-a singular ("Ai 3 task-uri", "Uite programul tău azi", "Bună dimineața!").

STIL VOCAL & CONȚINUT:
- Scrie ca și cum vorbești (natural, fluid), nu ca un document corporatist.
- Fără formule de umplutură sau clișee (fără "Sigur!", "Cu drag!", "Desigur!").
- Romglish natural: română ca bază + termeni tehnici în engleză (task, habit, meeting, gym, chess, focus, review).
- TEXT BRIEFING: Detaliat, organizat și COMPLET. MAXIM 500 cuvinte.
- PODCAST/VOCE: MAXIM 150 cuvinte. Fluid, direct la fapte.

FORMATARE:
- Telegram MarkdownV2: bold cu *text*, code cu `text`.
- NU folosi JSON, răspunde direct cu textul mesajului.
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
        logger.error(f"Gemini proactive error: {type(e).__name__} - {e}", exc_info=True)
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
        "Dacă un fragment este neclar, păstrează-l aproape de forma originală sau marchează-l pentru clarificare; NU îl înlocui cu o presupunere (de exemplu nu transforma un nume de magazin într-o întâlnire). "
        "Nu adăuga informații noi. Răspunde DOAR cu textul reformulat, fără explicații. "
        f"Transcriere: {raw}"
    )
    try:
        messages = [{"role": "user", "content": prompt}]
        normalized = await generate_text_response(messages, model=model)

        # Never accept a rewrite that silently drops numeric facts.
        raw_numbers = re.findall(r"\d+(?:[.,]\d+)?", raw)
        normalized_numbers = re.findall(r"\d+(?:[.,]\d+)?", normalized or "")
        if any(number not in normalized_numbers for number in raw_numbers):
            _voice_logger.warning("VOICE NORMALIZE DROPPED DATA — using raw transcript")
            return raw

        _voice_logger.info(
            "VOICE NORMALIZE | original=%r | normalized=%r", raw, normalized
        )
        _voice_logger.info(f"🎙 VOICE NORMALIZE | original: {repr(raw)} → normalized: {repr(normalized)}")
        return normalized
    except Exception as e:
        _voice_logger.warning(
            "VOICE NORMALIZE FAILED (%s) — using raw text: %r", e, raw
        )
        _voice_logger.warning(f"⚠️ VOICE NORMALIZE FAILED ({e}) — using raw: {repr(raw)}")
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


# Backward-compat alias — legacy name used across imports
# TODO: Migrate all callers to `get_llm_response` over time
get_gemini_response = get_llm_response
