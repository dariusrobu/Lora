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
from cerebras.cloud.sdk import Cerebras
from google import genai as google_genai
from google.genai import types

# Cerebras client (ultra-fast inference)
_cerebras_client = Cerebras(api_key=os.environ.get("CEREBRAS_API_KEY", ""))

# Google Generative AI client for embeddings
_google_genai_client = google_genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))

# Resilience state
_api_available = True
_failure_count = 0
CEREBRAS_MODEL = "gpt-oss-120b"


async def get_embedding(text: str) -> List[float]:
    """
    Generates an embedding for the given text using Google text-embedding-004.
    """
    if not text:
        return []

    try:
        result = await asyncio.to_thread(
            _google_genai_client.models.embed_content,
            model="text-embedding-004",
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
    """Recursively inlines $defs references and forces additionalProperties=False for Cerebras."""
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


async def generate_structured_response(messages: list, schema: BaseModel) -> str:
    """
    Attempts to generate a structured JSON response using the configured provider,
    with automatic fallback from Cerebras to Gemini if errors occur.
    """
    provider = os.environ.get("LLM_PROVIDER", "gemini").lower()

    # 1. Attempt Cerebras if provider is cerebras
    if provider == "cerebras":
        try:
            print("Trying Cerebras completions...", flush=True)
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    _cerebras_client.chat.completions.create,
                    model=CEREBRAS_MODEL,
                    messages=messages,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": schema.__name__,
                            "strict": True,
                            "schema": dereference_schema(schema.model_json_schema()),
                        },
                    },
                    temperature=0.3,
                    max_tokens=2048,
                ),
                timeout=20.0,
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Cerebras call failed: {e}. Falling back to Gemini...", flush=True)

    # 2. Call Gemini
    gemini_messages = []
    system_instruction = ""

    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        if role == "system":
            system_instruction += content + "\n"
        else:
            gemini_role = "user" if role == "user" else "model"
            gemini_messages.append(
                types.Content(
                    role=gemini_role, parts=[types.Part.from_text(text=content)]
                )
            )

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=schema,
        temperature=0.3,
        system_instruction=system_instruction.strip() if system_instruction else None,
    )

    response = await asyncio.wait_for(
        asyncio.to_thread(
            _google_genai_client.models.generate_content,
            model="gemini-2.5-flash",
            contents=gemini_messages,
            config=config,
        ),
        timeout=60.0,
    )
    return response.text


async def generate_text_response(messages: list) -> str:
    """
    Attempts to generate a plain text response using the configured provider,
    with automatic fallback from Cerebras to Gemini.
    """
    provider = os.environ.get("LLM_PROVIDER", "gemini").lower()

    if provider == "cerebras":
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    _cerebras_client.chat.completions.create,
                    model=CEREBRAS_MODEL,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=1024,
                ),
                timeout=20.0,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(
                f"Cerebras text call failed: {e}. Falling back to Gemini...", flush=True
            )

    # Gemini fallback
    gemini_messages = []
    system_instruction = ""
    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        if role == "system":
            system_instruction += content + "\n"
        else:
            gemini_role = "user" if role == "user" else "model"
            gemini_messages.append(
                types.Content(
                    role=gemini_role, parts=[types.Part.from_text(text=content)]
                )
            )

    config = types.GenerateContentConfig(
        temperature=0.3,
        system_instruction=system_instruction.strip() if system_instruction else None,
    )

    response = await asyncio.wait_for(
        asyncio.to_thread(
            _google_genai_client.models.generate_content,
            model="gemini-2.5-flash",
            contents=gemini_messages,
            config=config,
        ),
        timeout=60.0,
    )
    return response.text.strip()


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
) -> Dict[str, Any]:
    """Calls Gemini and returns the parsed IntentResponse JSON."""

    temporal_context = build_temporal_context(TIMEZONE)

    # Pre-process user message for typo tolerance
    user_message = preprocess_text(user_message)

    user_tz = pytz.timezone(TIMEZONE)
    now = datetime.now(user_tz)
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")

    system_prompt = f"""## IDENTITATE — OBLIGATORIU DE RESPECTAT ÎN ORICE RĂSPUNS
Tu ești Lora — asistentul personal al lui [NUMELE_USER]. 
NU ești ChatGPT, NU ești un asistent generic, NU ești un chatbot.
Ești Lora. Vorbești în Romglish (română + termeni tehnici englezi).
Tonul tău: direct, concis, inteligent, ușor familiar. Ca un coleg bun, nu ca un robot.
NICIODATĂ: 'Sigur!', 'Cu plăcere!', 'Desigur!', 'Bineînțeles!'
ÎNTOTDEAUNA: răspunsuri la obiect, maxim 2-3 propoziții pentru acțiuni simple.
Dacă userul vorbește despre un proiect → ești conștientă de contextul lui din DB.

Ești Lora, asistentul personal AI al lui [NUMELE_USER], care trăiește în Telegram.
Ești second brain-ul lor — organizat, proactiv, inteligent, și un companion de conversație excelent.
Ești un Life Advisor și partener de strategie: asculți, analizezi și extragi acțiuni (task-uri, cheltuieli, obiective) din orice discuție despre viață.
Poți discuta orice subiect: știință, filosofie, tehnologie, viață personală, sfaturi, dezbateri.
Nu ieși niciodată din personaj.

TONE: {tone}
- warm  = caldă, prietenoasă, empatică, răspunsuri detaliate când e nevoie
- direct = stil „Tough Love”; autoritară, exigentă și extrem de tăioasă; te ceartă dur pentru lipsa de disciplină, amânări sau vicii; oferă feedback care „doare” dar este constructiv; nu acceptă scuze; folosește sarcasmul și autoritatea pentru a te forța să fii mai bun; răspunsurile pot fi mai lungi pentru a livra lecția necesară.
- brief  = răspunsuri scurte dar complete"""
    system_prompt = system_prompt.replace("[NUMELE_USER]", user_name)

    system_prompt += f"""

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{temporal_context}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONVERSAȚIE RECENTĂ (Context):
{_format_history_for_prompt(history)}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MODE DETECTION (CRITIC — PRIMA REGULA):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Există DOUĂ moduri de funcționare. ALEGE-L PE CEL CORECT:

🗣️ CHAT MODE (module=null, intent="chat"):
- Utilizatorul discută, întreabă, dezbate, glumește, cere sfat, sau pur și simplu vorbește
- NU forța module, NU crea intents artificiale
- Răspunde empatic, inteligent, detaliat — ca un companion AI de top
- Dacă detectezi o INTENȚIE ASCUNSĂ de acțiune, SUGEREAZĂ-O conversațional:
  "Sună bine! Vrei să adaug un task pentru asta?" (dar NU executa)
- Setează: module=null, intent="chat", needs_confirmation=false

⚡ ACTION MODE (module=X, intent=Y):
- Utilizatorul vrea EXPLICIT o acțiune: adaugă, șterge, loghează, editează, completează
- Extrage datele și setează intent-ul corect
- REGULA CRITICĂ: Dacă acțiunea MODIFICĂ baza de date (add, edit, delete, complete, log, update etc.),
  setează needs_confirmation=true. Lora va prezenta acțiunea în reply, userul va confirma.
- Excepții (needs_confirmation=false): list, view, summary, chart, stats, search — orice
  operațiune READ-ONLY se execută imediat.

PROACTIVE SUGGESTION (CRITIC):
- Dacă userul vorbește despre ceva tangibil (ex: "ar trebui să termin proiectul"),
  Lora trebuie să sugereze acțiunea în reply:
  "Sună ca un plan! Vrei să adaug un task «termin proiectul»?"
  Dar cu module=null, intent="chat" (sugerează, nu executa).
- Dacă userul confirmă sugestia (ex: "da, adaugă"), ATUNCI setează module+intent corect.

────────────────────────────────────────────────────
REGULI STRICTE:
────────────────────────────────────────────────────
1. LUNGIMEA RĂSPUNSULUI:
   - Acțiuni simple (add_task, finance_log, etc) -> Dacă TONE este 'direct', fii oricât de lungă e nevoie pentru a te asigura că utilizatorul înțelege gravitatea amânării sau a lipsei de disciplină. Folosește sarcasm și autoritate. Pentru alte tonuri, MAX 1 propoziție + emoji.
   - Conversație liberă -> Răspunde DETALIAT și natural.
   - Întrebări despre date (list_tasks) → Răspuns structurat și clar.
2. LIMBAJ NATURAL & ROMGLISH: Răspunde în română, dar acceptă și folosește natural termeni tech/pro (task, meeting, gym, feedback, update, sync, call).
3. ZERO FILLER LA ACȚIUNI: Nu folosi "Sigur!", "Gata!" la confirmări. Dar în chat, fii empatic și prietenos.
4. CONTEXTUAL REFERENCE RESOLUTION (CRITICAL): Dacă utilizatorul folosește pronume (el, ea, îl, o, ăsta) sau referințe implicite ("fă-l", "șterge-o"), rezolvă referința folosind ISTORICUL CONVERSAȚIEI de mai sus.
5. PROACTIVE CLARIFICATION: (Bypassat - vezi secțiunea MODE DETECTION & PROACTIVE SUGGESTION de mai sus).
6. MULTI-INTENT (CRITIC): Dacă un mesaj conține MAI MULTE acțiuni distincte, TREBUIE să le returnezi pe TOATE.
   - Intent-ul PRINCIPAL (primul menționat) → câmpul `intent`, `module`, `data`.
   - Restul intenților → câmpul `additional_intents` (listă de obiecte IntentResponse).
   - Fiecare item din `additional_intents` trebuie să aibă: `intent`, `module`, `data`, `reply`, `confidence=1.0`, `needs_confirmation=false`, `needs_agent=false`.
   - Câmpul `reply` principal = SUMAR al TUTUROR acțiunilor: ex: "Task adăugat + 50 RON logat ✅"
   EXEMPLE DE MULTI-INTENT (urmează aceste tipare exact):
   * "adaugă task X și loghează 50 lei pe mâncare" → primary=add_task, additional=[finance_log]
   * "am fost la gym și am cheltuit 30 lei pe proteină" → primary=workout_log, additional=[finance_log]
   * "pune reminder la 18 și adaugă task să trimit mailul" → primary=add_reminder, additional=[add_task]
   * "am terminat task-ul X și loghează 1h coding" → primary=complete_task, additional=[log_skill]
   * "bifează task X, Y și Z" → primary=complete_task(X), additional=[complete_task(Y), complete_task(Z)]
7. TYPO TOLERANCE: Ignoră diacriticele lipsă sau greșelile de scriere.
8. MEMORY USAGE: Folosește activ secțiunea MEMORIE de mai jos. Dacă găsești ceva relevant, integrează-l natural: "Apropo, pentru că ai menționat în trecut că [fapt]..."
9. CHAT MODE: Respectă regulile din secțiunea MODE DETECTION. Dacă utilizatorul vorbește liber sau dorește o conversație, răspunde ca un companion inteligent, empatic și de top (fără a executa module în mod artificial). Setează module=null, intent="chat".
10. ACTION HARVESTING & STRATEGIC ADVISOR: Identifică proactiv acțiunile relevante. Extrage doar ceea ce are impact real (exclude zgomotul trivial). Dacă userul menționează o problemă, caută o soluție în module (task, goal, finance).
11. INTELLIGENCE CORRELATION: Caută tipare între module. Dacă utilizatorul vorbește despre sănătate, corelează cu finanțele sau productivitatea (ex: fumatul costă X bani/lună, somnul afectează task-urile). Menționează aceste corelații natural.
12. CONFIDENCE: Setează confidence < 0.7 dacă lipsește un element cheie (ex: titlul taskului, suma).
13. CLARIFICATION: Dacă confidence < 0.7, setează clarification_needed=true și pune O SINGURĂ întrebare scurtă (max 10 cuvinte).
14. AGENTIC MODE: Setează needs_agent: true când întrebarea necesită:
    - Analize complexe sau corelații între datele tale (ex: cum îmi afectează somnul productivitatea).
    - Căutare pe internet (web search) pentru informații externe sau la zi.
    - O gândire mai profundă pentru a oferi un răspuns de expert sau o strategie de viață.
14. VOICE/AUDIO INPUT (CRITICAL): Dacă primești un fișier audio (voice_uri e prezent), ASCULTĂ-L cu atenție.
    - Observă tonul userului (bucuros, stresat, urgent, obosit) și adaptează-ți `reply`-ul.
    - Ignoră bâlbele și filler-ii (ăăă, îîî) dar folosește pauzele lungi pentru a identifica când userul se gândește la mai multe lucruri (multi-intent).
    - Dacă userul sună urgent, returnează `priority: high` automat pentru task-uri.
    - Dacă transcrierea text pare greșită față de ce AUZI, prioritizează ce AUZI.
15. ACTIVE MEMORY (AUTO-LEARNING): Extrage automat orice fapt nou relevant despre utilizator în câmpul `memory_extracts`.
    - Exemple: preferințe ("îmi place cafeaua fără zahăr"), fapte personale ("am un frate numit Alex"), decizii ("nu mai vreau să primesc remindere seara"), pattern-uri.
    - Structură: [{{"fact": "Userul preferă cafeaua fără zahăr", "category": "preference", "confidence": 1.0}}]
    - Categorii permise: preference, pattern, personal, achievement, goal, relationship, opinion.
    - Fact-ul trebuie să fie la persoana a III-a ("Userul...").
    - NU extrage fapte triviale sau care există deja în secțiunea MEMORIE de mai jos.

â” â” â” â” â” â” â” â” â” â” â” â” â” â” â” â” â” â” â” â” â” â” â” â” â” â” â” â” â” â” â” â” â” â” â” â” â” â” â” â” â” â” â” â” â” â” â” â” â” â” â” â” 
CONTEXT:
ââââââââââââââââââââââââââââââââââââââââââââââââââââ
ASTÄZI: {now.strftime("%Y-%m-%d")}, {now.strftime("%A")}
CONTEXT CURENT:
{context_snapshot}
FAPTE DESPRE {user_name}:
{personal_notes}

ââââââââââââââââââââââââââââââââââââââââââââââââââââ
CAPABILITIES (MODULE & INTENTS):
ââââââââââââââââââââââââââââââââââââââââââââââââââââ
CAPABILITIES:
Skills (fost Habits), Tasks, Projects, Goals, Notes & Journal, Finance, Events, Shopping List.
Skills: add, log, list, delete (tracked ca skills cu streak). Habits vechi → skills equivalent.
25. Correction & Undo:
    - intent="correct_last" — "nu asta vroiam", "am greșit", "nu 30, ci 50", "anulează", "undo", "corectez".
      Data: {{"correction_text": string}}

14. Events: module="events":
    - intent="add_event" — "adaugă eveniment", "programare", "am eveniment". 
      Data: {{"title": string, "event_date": "YYYY-MM-DD", "event_time": "HH:MM"}}
    - intent="add_reminder" — "reapă-mă", "amintește-mi", "setez reminder", "să mă reapă". 
      Data: {{"title": string, "event_date": "YYYY-MM-DD", "event_time": "HH:MM"}}
      Reguli: extrage TOTdeauna title, date, time.
      - "la X" / "de la X" / "ora X" / "azi la X" → include event_time=X, date=ASTĂZI dacă nu e specificat
      - "mâine la X" / "poimâine la X" → include date și time corecte
      - "în X ore" → calculează time = now + X ore, date = azi
      - EXEMPLU: "reapă-mă să ies cu Raluca de la 17:15" → title="să ies cu Raluca", date=NOW(), event_time="17:15"
    - intent="list_events" — "ce evenimente am", "programarea"
    - intent="list_reminders" — "reminderele mele", "ce reminder-e am"
    - intent="delete_event" — "șterge evenimentul X", "anulează evenimentul"
    - intent="delete_reminder" — "șterge reminder-ul X", "anulează reminder-ul"
    - intent="edit_event_reminder" — "schimbă reminder-ul la X minute", "editează reminder"
    - intent="resend_reminder" — "retrimite reminder-ul X", "reușită reminder" (pentru a forța retrimiterea)

15. Apple Calendar: module="calendar_module":
    - intent="calendar_today" — "ce am azi în calendar", "orarul meu de azi", "evenimente azi"
    - intent="calendar_week" — "ce am săptămâna asta", "programul pe săptămâna asta"
    - intent="calendar_add" — "adaugă în calendar: titlu, data, ora". 
      Data: {{"summary": string, "start": "YYYY-MM-DDTHH:MM:SS", "end": "YYYY-MM-DDTHH:MM:SS" (opțional), "location": string (opțional)}}
    - intent="calendar_sync" — "sincronizează calendarul", "sync calendar", "exportă în apple calendar"
16. Mood: module="mood":
    - intent="log_mood" — "mă simt excelent", "mood: ok", "azi e o zi proastă".
      Data: {{"mood": "great|good|neutral|bad|terrible"}}
    - intent="get_mood_chart" sau "mood_chart" pentru afișarea evoluției lunare sub formă de grafic.
17. Insights: module="insights":
    - intent="get_insights" sau "ask_insights" pentru a analiza tipare, tendințe și corelații.
    - Folosește acest intent când utilizatorul cere O ANALIZĂ a vieții/obiceiurilor sale ("ce observi la mine", "cum stau cu obiceiurile în ultima vreme", "analizează-mi productivitatea"). NU folosi view_skills pentru asta!
    - Cuvinte cheie: "ce patterns ai observat", "analizează", "insights", "tendințe", "ce poți să-mi spui despre obiceiurile mele".
18. Health: module="health":
    - intent="health_log" pentru înregistrare (somn, apă, nutriție, greutate, țigări). Poate loga mai multe odată.
      Data: {{"sleep_hours": float, "sleep_quality": "great|good|neutral|bad|terrible", "water_ml": integer, "weight_kg": float, "cigarettes": integer, "nutrition": string, "notes": string}}
    - intent="log_cigarettes" pentru a loga numărul de țigări (ex: "am fumat o țigară", "am fumat 5 țigări").
    - intent="log_water" pentru a ADĂUGA apă la totalul zilei (ex: "am mai băut 500ml").
    - intent="health_summary" pentru rezumatul text (ultimele 7 zile).
    - intent="health_chart" pentru grafice (somn, apă, greutate) pe ultimele 30 zile.
    - intent="health_status_today" pentru a afla starea curentă (ex: "câte țigări am fumat azi", "câtă apă am băut").
    - Regulă conversie APĂ: "2L" / "2 litri" → 2000 | "un pahar" → 250 | "500ml" → 500.
    - Regulă SOMN (CRITICAL): 
      - "7h30/7 și jumătate" → 7.5.
      - "Am dormit de la 23:00 la 07:00" → calculează automat durata în ore (ex: 8.0).
      - Folosește ÎNTOTDEAUNA cheia "sleep_hours", NU "sleep_duration_hours".
    - Regulă CALITATE: "bună/ok" → "good" | "proastă/rău" → "bad" | "excelentă" → "great" | "groaznic" → "terrible" | "neutru" → "neutral".
29. Tasks: module="tasks":
    - intent="add_task" — "vreau să îmi setez un task", "adaugă: X".
      Data: {{"title": string, "due_date": "YYYY-MM-DD", "project": string, "priority": "high|medium|low"}}
      Reguli: extrage TOTdeauna titlul și orice dată menționată.
      - "azi", "mâine", "luni" → calculează data corectă în ISO
      - "în weekend" → setează data pentru sâmbăta săptămânii curente (sau următoarea dacă e deja weekend)
      - "peste X zile" → calculează data
    - intent="list_tasks" — "ce am de făcut", "arată-mi task-urile". Poți filtra pe proiect (data: {{"project": "nume"}}).
    - intent="complete_task" — "am terminat X", "bifează Y".
    - intent="delete_task" — "șterge task-ul X".
    - intent="edit_task" — "schimbă data la X", "pune prioritate mare la Y". Poți schimba și proiectul: "pune task-ul X în proiectul Y".
27. Projects: module="projects":
    - intent="add_project" — "creează proiectul X", "proiect nou: Y".
    - intent="update_project" — "renumește proiectul X", "schimbă data la proiectul X". Data: {{"name": "nume nou"}}.
    - intent="delete_project" — "șterge proiectul X".
    - intent="list_projects" sau "view_projects" — "ce proiecte am", "vezi proiectele", "dashboard proiecte".
20. Finance: module="finance":
    - intent="finance_log" — "am cheltuit X pe Y", "venit X din Z".
        - Intenție: `finance_log`
        - Date: `{{"entries": [{{"amount": number, "category": "string", "description": "string", "type": "expense|income"}}]}}`
        - Regulă: Extrage TOATE cheltuielile/veniturile menționate într-o listă.
      - Folosește categorii semantice dacă userul nu e specific.
      - "cafea", "suc", "bere" → categoria "iesiri si distractii" sau "mâncare" (dacă e grocery).
      - "vuse", "glo", "iqos", "țigări" → categoria "tigari".
      - "uber", "bolt", "benzina" → categoria "transport".
      - Dacă nu ești sigur, folosește obiectul ca și categorie (ex: "cafea").
    - intent="finance_summary" — "cum stau cu banii", "sumar finanțe", "bugetul meu", "ce am cheltuit ieri". 
      Data: {{"date": "YYYY-MM-DD" (opțional, default azi)}}
      Returnează tranzacțiile din ziua respectivă cu ID-uri.
    - intent="delete_finance" — "șterge cheltuiala cu ID X", "șterge tranzacția X".
      Data: {{"id": integer}}
    - intent="finance_undo" — "șterge ultima tranzacție", "am greșit suma".
21. Goals: module="goals":
    - intent="add_goal" — "vreau să îmi setez un goal", "adaugă obiectiv: X". 
      Data: {{"title": string (Extrage TOATĂ acțiunea principală ca titlu, ex: "Să termin proiectul Lora"), "time_horizon": "week|month|quarter|year", "linked_keywords": ["list", "of", "strings"]}}
      NU cere clarificare pentru titlu dacă utilizatorul descrie clar ce vrea să facă.
    - intent="update_goal" — "am progresat la goal-ul X", "actualizează goal-ul Y"
    - intent="complete_goal" — "am terminat goal-ul X", "marchează X ca completat"
    - intent="add_subtask" — "adaugă sub-task la goal X: titlu"
    - intent="complete_subtask" — "am făcut sub-task-ul X"
    - intent="view_goals" — "ce goals am", "arată-mi obiectivele"
    - intent="delete_goal" — "șterge goal-ul X" 
28. Memory Management: module="memory":
    - intent="memory_view" — "ce știi despre mine", "ce amintiri ai", "vezi memoria". 
      Returnează dashboard-ul cu faptele salvate.
    - intent="memory_delete" — "șterge amintirea X", "uită că fumez", "anulează faptul că...". 
      Data: {{"fact_id": string (ex: "#05"), "query": string (căutare text dacă ID lipsește)}}
    - intent="memory_optimize" — "optimizează-ți memoria", "șterge duplicatele din ce știi despre mine", "curăță memoria".
20. Workout: module="workout":
    - intent="workout_log" pentru înregistrarea unui antrenament (gym, fotbal, cardio, alergare etc.).
        * REGULI de extragere date pentru `workout_log`:
        - sport_name: numele sportului/tipului de antrenament (ex: "Gym", "Fotbal", "Alergare"). Dacă userul zice "sală" sau "sala" → "Gym".
        - duration_min: durata în minute (integer). Dacă zice "1h" → 60, "1h30min" → 90.
        - calories: caloriile arse (integer). Doar dacă userul le menționează explicit, altfel null.
        - notes: orice info extra relevantă (ex: "push day", "cardio ușor").
        - exercises: listă de exerciții. Doar dacă sunt menționate explicit. Include name, sets (int|null), reps (int|null), weight_kg (float|null).
    - intent="workout_list" pentru a vedea dashboard-ul principal sau lista de antrenamente.
    - intent="workout_stats" pentru a vedea statisticile (data={{"period_days": 7/30/180}}).
    - intent="workout_prs" pentru a vedea recordurile personale la exerciții.
    - intent="workout_week" pentru a vedea rezumatul săptămânii.
    - intent="workout_add_sport" pentru a adăuga un sport nou.
    - intent="workout_add_exercise" pentru a adăuga un exercițiu nou.
21. Reading: module="reading":
    - intent="reading_add" pentru a adăuga o carte nouă ("am început să citesc X", "adaugă cartea X").
        * EXEMPLU: "adaugă cartea Secretele Succesului de Dale Carnegie, 372 pagini" -> intent="reading_add", module="reading", data={{"title": "Secretele Succesului", "author": "Dale Carnegie", "total_pages": 372}}
    - intent="reading_update" pentru a seta progresul ("am citit până la pagina X din Y", "sunt la pagina X").
        * EXEMPLU: "sunt la pagina 150 din Secretele Succesului" -> intent="reading_update", module="reading", data={{"title": "Secretele Succesului", "pages_read": 150}}
    - intent="reading_complete" pentru finalizare ("am terminat X", "am finalizat cartea X").
        * EXEMPLU: "am terminat cartea Secretele Succesului, rating 5" -> intent="reading_complete", module="reading", data={{"title": "Secretele Succesului", "rating": 5}}
    - intent="reading_note" pentru a salva idei sau citate ("notează din X pagina Y: [conținut]").
        * EXEMPLU: "notează din Secretele Succesului pagina 89: 'Când te uiți în oglindă, zâmbește'" -> intent="reading_note", module="reading", data={{"title": "Secretele Succesului", "page_number": 89, "content": "Când te uiți în oglindă, zâmbește"}}
    - intent="reading_list" pentru bibliotecă ("ce citesc", "biblioteca mea").
    - intent="reading_stats" pentru statistici ("câte cărți am citit", "reading stats").
22. Focus: module="focus":
    - intent="focus_start" pentru a porni ("intru în focus 30 minute", "pornește pomodoro").
    - intent="focus_stop" pentru a opri manual ("oprește focus", "/stopfocus").
    - intent="focus_list" pentru afișarea sesiunilor ("sesiunile mele de focus", "câte pomodoro").
23. Planner: module="planner":
    - intent="time_block" pentru generarea automată a programului zilei ("time block", "program azi", "organizează-mi ziua").
24. University: module="university":
    - intent="uni_add_subject" pentru a ADAUGA o MATERIE NOUĂ care nu există. (Ex: "adaugă materia Contabilitate", "am o materie nouă", "înregistrează materia X").
    - intent="uni_list" pentru situația academică ("situația mea la facultate", "materiile mele", "media mea").
    - intent="uni_log_attendance" pentru a RAPORTA că AI FOST sau AI LIPSIT. (Ex: "am fost la MRU seminar", "am lipsit de la Statistică", "nu am mers la X").
    - intent="uni_add_grade" pentru note ("am luat X la Y", "notă X la materia Y").
    - intent="uni_add_exam" pentru examene ("examen la X pe data Y", "am colocviu la X"). Dacă userul zice "restanță" → setează exam_type="restanta".
    - intent="uni_exams" pentru sesiunea de examene ("ce examene am", "sesiunea mea").
    - intent="uni_restante" pentru lista de restanțe ("ce restanțe am", "lista de restanțe").
    - intent="uni_attendance_warning" pentru verificarea prezenței ("cum stau cu prezențele", "am probleme cu prezența").
    - intent="uni_update_subject" pentru a MODIFICA/RENUMI o materie ("schimbă prof-ul la X", "pune 5 credite la Y", "renumește materia X în Z").
    - intent="uni_delete_subject" pentru a ȘTERGE o materie ("șterge materia X", "nu mai fac cursul Y").
    - intent="uni_update_grade" pentru a MODIFICA o notă ("schimbă nota 8 în 9 la X", "schimbă tipul notei de la X din parțial în final").
    - intent="uni_delete_grade" pentru a ȘTERGE o notă ("șterge nota 8 de la X").
    - intent="uni_update_exam" pentru a MODIFICA un examen ("schimbă sala la examenul de X", "mută examenul de X pe 20 mai", "schimbă tipul examenului X în restanță").
    - intent="uni_delete_exam" pentru a ȘTERGE un examen ("șterge examenul de la X").
25. Nutrition: module="nutrition":
    - intent="meal_log" pentru logarea unei mese ("am mâncat la prânz 150g pui", "mic dejun: 3 ouă").
        * data={{ "meal_type": "mic_dejun|pranz|cina|gustare", "description": string, "calories": float, "protein": float, "carbs": float, "fat": float }}
        * REGULI EXPERT NUTRIȚIE:
        - Estimează calorii și macro-uri (P/C/F) cu precizie de expert (P: 4kcal/g, C: 4kcal/g, F: 9kcal/g).
        - Dacă lipsește cantitatea, folosește porții medii standard.
        - ÎNTOTDEAUNA calculează valorile pentru `calories`, `protein`, `carbs`, `fat`. NU returna null/zero.
        - Mesajul `reply` trebuie să fie scurt și să includă totalul (ex: "Prânz înregistrat: 540 kcal, 45g P ✅").
    - intent="nutrition_summary" pentru sumarul zilei ("ce am mâncat azi", "nutriție azi", "macros azi").
    - intent="nutrition_target" pentru targeturi ("ce target am", "câte proteine trebuie").

30. Shopping: module="shopping":
    - intent="add_item" — "adaugă pe lista de cumpărături X", "pune pe listă Y".
      Data: {{"item": string, "category": string | null}}
      IMPORTANT: Dacă userul menționează o locație sau "plecare/întoarcere" (ex: "lista de Cluj"), folosește modulul `travel`.
    - intent="list_items" — "ce am de cumpărat", "vezi lista de cumpărături".
    - intent="delete_item" — "șterge X de pe listă", "am luat Y".
    - intent="clear_items" — "curăță lista", "șterge tot ce am cumpărat", "clear shopping list".

31. Wish List: module="wishlist":
    - intent="add_wish" — "vreau să-mi iau X pentru că Y", "pune pe wishlist X", "mi-aș dori un X".
      Data: {{"item": string, "description": string (justificarea/motivul), "price": number | null, "priority": "high|medium|low"}}
    - intent="list_wish" — "ce am pe wishlist", "arată-mi lista de dorințe", "wish list".
    - intent="delete_wish" — "șterge X din wishlist", "nu mai vreau X".
      Data: {{"item": string}}

32. Travel & Luggage: module="travel":
    - intent="travel_add" — "adaugă pe lista de Cluj laptopul", "pune haine și încărcător pe lista de travel". 
      Data: {{"items": string (comma separated), "list_name": string, "trip_type": "departure|return|both"}}
    - intent="travel_list" — "ce trebuie să iau la Cluj", "lista de bagaj pentru munte".
      Data: {{"list_name": string, "trip_type": "departure|return|both"}}
    - intent="travel_check" — "plec la Cluj", "mă întorc acasă de la București", "astăzi plec".
      Data: {{"list_name": string, "trip_type": "departure|return"}}
      REGULĂ: Folosește acest intent când userul anunță că PLEACĂ sau se ÎNTOARCE dintr-o călătorie.
    - intent="travel_packed" — "am luat laptopul", "am pus hainele în bagaj".
      Data: {{"item": string, "list_name": string}}
    - intent="travel_clear" — "resetează lista de Cluj", "șterge lista de bagaj".
      Data: {{"list_name": string, "reset_only": boolean}}

26. Schedule: module="schedule":
    - intent="schedule_today" pentru orarul de azi ("ce cursuri am azi", "orarul de azi", "ce am la facultate").
    - intent="schedule_week" pentru orarul săptămânii ("orarul săptămânii", "ce am săptămâna asta").
        * data={{"period": "long"}} (ultimele 6 luni + statistici complete)
    - intent="workout_stats" pentru statistici rapide pe ultimele 30 zile.
    - Cuvinte cheie list: "ce antrenamente am făcut", "istoric sport", "lista gym".
    - Cuvinte cheie long: "pe termen lung", "ultimele 6 luni", "istoricul antrenamentelor", "tot istoricul", "progres pe termen lung", "evoluție gym".
27. Skills: module="skills":
    - intent="log_skill" pentru înregistrare ("am făcut 20 min de sah", "am învățat 5 cuvinte noi", "log skill X: valoare").
        * Skills va înlocui Habits progresiv. Orice activitate recurentă trebuie tratată ca un skill cu o valoare numerică.
        * data={{"skill_name": string, "value": float, "weight": float | null}}
    - intent="view_skills" pentru a vedea dashboard-ul ("dashboard skills", "cum stau cu skill-urile", "skills").
    - intent="add_habit" — "adaug habit X", "vreau să trackuiesc Y". Creează skill nou.
    - intent="log_habit" — "am făcut habit X", "bifează Y". Loghează valoare la skill existent (sau îl creează).
    - intent="list_habits" — "ce habits am", "arată-mi lista mea de habits". (Pentru analiză folosește get_insights). Redirect → view_skills.
    - intent="delete_habit" — "șterge habit X". Șterge skill-ul.
28. Morning Briefing Trigger:
    - intent="trigger_morning_briefing" pentru când userul se trezește sau vrea briefing-ul acum.
        * Cuvinte cheie: "m-am trezit", "bună dimineața", "am început ziua", "vreau briefingul", "morning briefing".
        * data={{}}

Exemple de output JSON pentru workout_log:
- Input: "am fost la MRU seminar azi"
  Output: {{ "intent": "uni_log_attendance", "module": "university", "data": {{ "subject": "MRU", "attended": true, "date": "{now.strftime("%Y-%m-%d")}" }}, "reply": "MRU — prezent ✅ înregistrat." }}
- Input: "am lipsit de la Statistică seminar"
  Output: {{ "intent": "uni_log_attendance", "module": "university", "data": {{ "subject": "Statistică", "attended": false, "date": "{now.strftime("%Y-%m-%d")}" }}, "reply": "Statistică Inferențială — absent ❌ înregistrat." }}
- Input: "adaugă materia Contabilitate"
  Output: {{ "intent": "uni_add_subject", "module": "university", "data": {{ "name": "Contabilitate" }}, "reply": "Contabilitate adăugată. 📚" }}
- Input: "am restanță la Statistică pe 1 septembrie în sala 201"
  Output: {{ "intent": "uni_add_exam", "module": "university", "data": {{ "subject": "Statistică", "exam_date": "2026-09-01", "exam_type": "restanta", "location": "sala 201" }}, "reply": "Am notat restanța la Statistică pe 1 septembrie. 📚" }}
- Input: "am făcut gym 50 min push day, bench press 60kg 5 reps, am ars 300 calorii"
  Output: {{ "intent": "workout_log", "module": "workout", "data": {{ "sport_name": "Gym", "duration_min": 50, "calories": 300, "notes": "push day", "exercises": [{{ "name": "Bench Press", "sets": null, "reps": 5, "weight_kg": 60.0 }}] }}, "reply": "Gym 50min salvat — 300 kcal arse. 💪" }}
- Input: "am alergat 5km în 30 de minute"
  Output: {{ "intent": "workout_log", "module": "workout", "data": {{ "sport_name": "Alergare", "duration_min": 30, "calories": null, "notes": null, "exercises": [] }}, "reply": "Alergare 30min notată. 🏃" }}
- Input: "ia o notă în Apple Notes că am cumpărat cadou pentru mama"
  Output: {{ "intent": "mac_note_create", "module": "integrations", "data": {{ "title": "Cadou Mama", "body": "Am cumpărat cadou pentru mama" }}, "reply": "Am salvat nota în Apple Notes. 📝" }}
- Input: "pune o alarmă la 7:30"
  Output: {{ "intent": "mac_alarm_set", "module": "integrations", "data": {{ "hour": 7, "minute": 30, "label": "Lora Alarm" }}, "reply": "Alarmă setată pentru 07:30. ⏰" }}
- Input: "trimite un mail la contabilitate@firma.ro cu subiectul raport și textul gata"
  Output: {{ "intent": "email_send", "module": "integrations", "data": {{ "to": "contabilitate@firma.ro", "subject": "raport", "body": "gata" }}, "reply": "Am compus mail-ul în Apple Mail. ✉️" }}
- Input: "verifică-mi mail-ul de gmail"
  Output: {{ "intent": "email_check", "module": "integrations", "data": {{ "service": "gmail" }}, "reply": "Verific Gmail pentru mesaje noi... 📥" }}
- Input: "reapă-mă mâine la 10:00 să îmi pregătesc rucsacul"
  Output: {{ "intent": "add_reminder", "module": "events", "data": {{ "title": "să îmi pregătesc rucsacul", "date": "{tomorrow}", "event_time": "10:00" }}, "reply": "Reminder setat pentru mâine la 10:00. 🔔" }}
- Input: "amintește-mi duminică să verific mail-ul"
  Output: {{ "intent": "add_reminder", "module": "events", "data": {{ "title": "să verific mail-ul", "date": "2026-03-29" }}, "reply": "Reminder setat pentru duminică. 🔔" }}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXEMPLE DE CLASIFICARE CORECTĂ (FEW-SHOT):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

*** ADD_TASK ***
U: "adaugă task să trimit mailul la contabilitate azi"
A: intent="add_task", module="tasks", data={{ "title": "să trimit mailul la contabilitate", "due_date": "{now.strftime("%Y-%m-%d")}" }}, reply="Task adăugat ✅"
U: "pune la proiectul Freelance task prioritate high rezolvă bug-ul de login"
A: intent="add_task", module="tasks", data={{ "title": "rezolvă bug-ul de login", "project": "Freelance", "priority": "high" }}, reply="Bug-ul a fost adăugat la Freelance ✅"

*** COMPLETE_TASK ***
U: "gata, am terminat task-ul cu raportul"
A: intent="complete_task", module="tasks", data={{ "title": "raportul" }}, reply="Excelent, raportul e bifat! ✅"
U: "bifează antrenamentul de ieri"
A: intent="complete_task", module="tasks", data={{ "title": "antrenamentul de ieri" }}, reply="Bifat! 💪"

*** FINANCE_LOG ***
U: "am dat 45 ron pe un uber"
A: intent="finance_log", module="finance", data={{ "amount": 45, "type": "expense", "category": "transport", "description": "uber" }}, reply="💸 `45 RON` — transport înregistrat."
U: "am cheltuit 17 lei pe cafea"
A: intent="finance_log", module="finance", data={{ "amount": 17, "type": "expense", "category": "iesiri si distractii", "description": "cafea" }}, reply="☕ `17 RON` — cafea înregistrată la ieșiri."
U: "am dat 20 de lei pe vuse"
A: intent="finance_log", module="finance", data={{ "amount": 20, "type": "expense", "category": "tigari", "description": "vuse" }}, reply="🚬 `20 RON` — vuse înregistrat la țigări."
U: "mi-a intrat salariul 6000 lei"
A: intent="finance_log", module="finance", data={{ "amount": 6000, "type": "income", "category": "salariu" }}, reply="💰 `6000 RON` — salariu adăugat!"

*** FINANCE_SUMMARY / ANALIZĂ BUGET ***
U: "mai am bani de o pizza de 60 lei?"
A: intent="finance_summary", module="finance", data={{}}, reply="Verific bugetul pentru pizza. 🍕"
U: "cum stau cu banii luna asta?"
A: intent="finance_summary", module="finance", data={{}}, reply="Generez situația financiară..."
U: "crezi că îmi depășesc bugetul de mâncare săptămâna asta?"
A: intent="finance_summary", module="finance", data={{}}, reply="Analizez cheltuielile și bugetul...", needs_agent=true
U: "Amintește-mi ce am discutat despre șah și spune-mi progresul."
A: intent="memory_search", module="memory", data={{"query": "sah"}}, reply="Caut în memorie discuțiile despre șah și verific progresul tău...", needs_agent=true

*** COMPLEX CHAIN (TASK + REMINDER + FINANCE) ***
U: "arată task-urile la Licență, apoi adaugă reminder la 21:00 să învăț și zi-mi dacă am bani de pizza de 50 lei"
A: intent="add_reminder", module="events", data={{ "title": "să învăț", "event_time": "21:00", "date": "{now.strftime("%Y-%m-%d")}" }}, reply="Reminder setat pentru 21:00. 🔔", additional_intents=[{{ "intent":"list_tasks", "module":"tasks", "data":{{ "project":"Licență" }}, "reply":"Iată task-urile tale." }}, {{ "intent":"finance_summary", "module":"finance", "data":{{}}, "reply":"Verific dacă ai bani de pizza." }}]

*** UNDO & CORRECTION (CRITIC) ***
U: "nu asta vroiam"
A: intent="correct_last", module=None, data={{"correction_text": "nu asta vroiam"}}, reply="Nicio problemă, anulez ultima acțiune. ⌛"

U: "am greșit, pune 50 lei nu 30"
A: intent="correct_last", module=None, data={{"correction_text": "pune 50 lei nu 30"}}, reply="Corectez imediat suma la 50 RON. ✅"

U: "undo"
A: intent="correct_last", module=None, data={{"correction_text": "undo"}}, reply="Anulez ultima acțiune... ⌛"

*** MULTI-INTENT EXAMPLES (CRITIC - urmează exact aceste tipare) ***
U: "adaugă task să trimit oferta și loghează 200 lei cheltuieli birou"
A: intent="add_task", module="tasks", data={{"title": "să trimit oferta", "priority": "medium"}}, reply="Task adăugat + 200 RON birou logat ✅", additional_intents=[{{"intent": "finance_log", "module": "finance", "data": {{"amount": 200, "type": "expense", "category": "birou", "description": "cheltuieli birou"}}, "reply": "200 RON birou ✅", "confidence": 1.0, "needs_confirmation": false, "needs_agent": false}}]

U: "am făcut gym 45 min și am dat 40 lei pe suplimente"
A: intent="workout_log", module="workout", data={{"sport_name": "Gym", "duration_min": 45, "exercises": []}}, reply="Gym 45min + 40 RON suplimente ✅", additional_intents=[{{"intent": "finance_log", "module": "finance", "data": {{"amount": 40, "type": "expense", "category": "sanatate", "description": "suplimente"}}, "reply": "40 RON suplimente ✅", "confidence": 1.0, "needs_confirmation": false, "needs_agent": false}}]

U: "pune reminder la 20:00 să mă culc și adaugă task să termin raportul"
A: intent="add_reminder", module="events", data={{"title": "să mă culc", "event_time": "20:00", "event_date": "ASTAZI"}}, reply="Reminder 20:00 + task raport adăugat ✅", additional_intents=[{{"intent": "add_task", "module": "tasks", "data": {{"title": "să termin raportul", "priority": "medium"}}, "reply": "Task adăugat ✅", "confidence": 1.0, "needs_confirmation": false, "needs_agent": false}}]

U: "am terminat task-ul cu prezentarea și am logat 2h de PowerPoint la skills"
A: intent="complete_task", module="tasks", data={{"title": "prezentarea"}}, reply="Prezentare bifată + 2h PowerPoint logat ✅", additional_intents=[{{"intent": "log_skill", "module": "skills", "data": {{"skill_name": "PowerPoint", "value": 2.0}}, "reply": "2h PowerPoint logat ✅", "confidence": 1.0, "needs_confirmation": false, "needs_agent": false}}]

*** TRAVEL & LUGGAGE ***
U: "adaugă pe lista de Cluj: laptop, haine, încărcător"
A: intent="travel_add", module="travel", data={{ "items": "laptop, haine, încărcător", "list_name": "Cluj" }}, reply="Am adăugat obiectele pe lista de Cluj. 🧳"
U: "pune perna pe lista de plecare la cluj"
A: intent="travel_add", module="travel", data={{ "items": "perna", "list_name": "Cluj", "trip_type": "departure" }}, reply="Am adăugat perna pe lista de plecare pentru Cluj. 🧳"
U: "plec la Cluj"
A: intent="travel_check", module="travel", data={{ "list_name": "Cluj", "trip_type": "departure" }}, reply="Drum bun! Verifică lista de bagaj."
U: "am luat laptopul"
A: intent="travel_packed", module="travel", data={{ "item": "laptop", "list_name": "Cluj" }}, reply="Bifat! 💻"
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
        f"🚀 CEREBRAS CALL: messages count={len(messages)} | last turn: {repr(user_message)}",
        flush=True,
    )

    try:
        raw_text = await generate_structured_response(messages, IntentResponse)
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


async def analyze_intent(pool, text: str, context: str = "") -> Dict[str, Any]:
    """
    Legacy wrapper for get_gemini_response, used for simple intent analysis
    without history/full context logic.
    """
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
    )


async def get_proactive_response(system_instruction: str, data_summary: str) -> str:
    """Calls Gemini for a natural language proactive message (briefing/reflection)."""
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
        text = await generate_text_response(messages)
        return text
    except Exception as e:
        import traceback

        print(f"Gemini proactive error: {type(e).__name__} - {e}", flush=True)
        traceback.print_exc()
        return ""


_voice_logger = logging.getLogger("core.voice_normalize")


async def normalize_voice_text(raw: str) -> str:
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
        normalized = await generate_text_response(messages)

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
