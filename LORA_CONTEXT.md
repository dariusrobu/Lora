# 🤖 Lora — Context Complet pentru AI Assistant

> **Citește acest document integral înainte de orice modificare.**
> Reprezintă starea curentă a proiectului + tot ce s-a discutat și implementat.
> Dacă continui o conversație anterioară, pornești de AICI.

---

## Ce este Lora

Lora este un **Telegram bot privat, single-user**, care funcționează ca un second brain personal. Nu e un chatbot generic — are memorie persistentă, înțelege română + Romglish, gestionează multiple domenii de viață și trimite mesaje proactive pe un schedule zilnic.

**Userul:** Robu — student la Cluj-Napoca, activ tehnic, face sport (gym, fotbal), habits: Citit, Duolingo, Șah, Gym. Vorbește în română cu termeni tehnici în engleză (Romglish). Fumează.

---

## Stack Tehnic

| Layer | Tehnologie | Note importante |
|-------|-----------|----------------|
| Language | Python 3.11+ | Type hints obligatorii |
| Telegram | python-telegram-bot==22.6 | Async, long polling |
| LLM | google-genai (latest) | Model: gemini-2.5-flash |
| Database | Neon (serverless PostgreSQL) | Cloud-hosted |
| DB driver | asyncpg | Raw SQL — NICIUN ORM |
| Scheduler | apscheduler==3.10.4 | AsyncIOScheduler |
| TTS | edge-tts | Voce: ro-RO-AlinaNeural |
| Charts | matplotlib | Mood chart + Health chart + Habit heatmap PNG |
| Hosting | Railway | Deploy via GitHub push, numReplicas=1 |

> ⚠️ SDK-ul este `from google import genai` — NU `google-generativeai` (legacy).

---

## Environment Variables (.env)

```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_USER_ID=
GEMINI_API_KEY=
DATABASE_URL=              # postgres://...?sslmode=require
TIMEZONE=Europe/Bucharest
MORNING_BRIEFING_TIME=08:00
EOD_REFLECTION_TIME=21:00
HABIT_REMINDER_TIME=18:00
WEEKLY_REVIEW_DAY=sunday
JOURNAL_NIGHT_TIME=22:00
OPENWEATHER_API_KEY=       # opțional
```

---

## Structura Directorului (stare curentă)

```
lora/
├── main.py
├── requirements.txt
├── railway.json              # numReplicas=1, restartPolicyType=ON_FAILURE
│
├── bot/
│   ├── handler.py            # ★ routing, security, voice/text/callback
│   │                         # Comenzi: /reload, /podcast, /start, /journal,
│   │                         #   /plan, /weeklyreview, /monthlyreview,
│   │                         #   /habitstreaks, /timeblock, /focus, /stopfocus
│   │                         # State-uri: awaiting_journal_response,
│   │                         #   awaiting_day_plan_input, in_focus_session,
│   │                         #   awaiting_focus_result
│   ├── keyboards.py
│   ├── formatter.py          # escape_md(), safe_markdown(), split_message()
│   ├── onboarding.py
│   ├── tts.py                # voce ro-RO-AlinaNeural, strip emoji+URL+MarkdownV2
│   └── voice.py
│
├── core/
│   ├── gemini.py             # ★ ton direct+concis, toate intents înregistrate
│   ├── config.py
│   ├── context.py            # goals active în build_context()
│   ├── router.py             # toate modulele înregistrate
│   └── state.py
│
├── modules/
│   ├── tasks.py              # list grupat pe proiecte, fără ID
│   ├── habits.py             # ★ generate_habit_heatmap() adăugat
│   ├── projects.py
│   ├── notes.py
│   ├── finance.py            # alertă 80% + alertă depășire + generate_forecast()
│   ├── events.py
│   ├── shopping.py
│   ├── weather.py
│   ├── news.py               # NU mai e inclus în podcast
│   ├── goals.py              # goal tracking cu sub-tasks + progress bar
│   ├── mood.py               # mood chart PNG + list_mood
│   ├── health.py             # ★ NOU: somn, apă, nutriție, greutate + chart PNG
│   ├── workout.py            # ★ NOU: gym/fotbal/cardio + exerciții + stats
│   ├── reading.py            # ★ NOU: bibliotecă personală + progress + note
│   ├── focus.py              # ★ NOU: pomodoro/focus sessions + timer
│   ├── planner.py            # ★ NOU: time blocking automat (/timeblock)
│   └── insights.py           # ★ NOU: proactive insights + generate_insights()
│
├── scheduler/
│   └── jobs.py               # ★ joburi active:
│                             #   send_morning_briefing (cu time block integrat)
│                             #   send_eod_reflection (ton fix)
│                             #   send_journal_night
│                             #   send_weekly_review (cu health correlations)
│                             #   send_monthly_review (prima zi a lunii 20:00)
│                             #   send_weekly_finance_summary (luni dimineață)
│                             #   send_habit_reminder (ton fix, direct)
│                             #   missed_habit_nudge
│                             #   check_event_reminders
│                             #   check_budget_forecast (joi 09:00)
│                             #   check_proactive_insights (zilnic 09:30)
│                             #   reset_budget_alerts (1 ale lunii)
│
└── db/
    ├── connection.py
    ├── schema.sql
    └── queries/
        ├── tasks.py
        ├── habits.py          # get_habit_history_365(), get_monthly_habit_stats()
        ├── projects.py
        ├── notes.py           # get_mood_history(), get_weekly_journals(),
        │                      #   get_monthly_mood_distribution()
        ├── finance.py         # get_weekly_expenses, get_monthly_total_by_category,
        │                      #   get_budget_usage, get_budget_forecast(),
        │                      #   get_monthly_comparison()
        ├── events.py
        ├── shopping.py
        ├── profile.py
        ├── goals.py
        ├── journal.py
        ├── day_plans.py
        ├── health.py          # ★ NOU: get_health_log(), get_health_history(),
        │                      #   get_monthly_health_avg()
        ├── workout.py         # ★ NOU: log_workout(), get_recent_workouts(),
        │                      #   get_long_term_stats(), get_workout_stats()
        ├── reading.py         # ★ NOU: add_book(), update_progress(),
        │                      #   complete_book(), add_book_note()
        └── focus.py           # ★ NOU: start_session(), complete_session(),
                               #   get_weekly_focus_stats()
```

---

## Tabele DB — Stare Curentă Completă

### Coloane noi în user_profile
```sql
last_journal_date DATE
last_weekly_review_date DATE
last_finance_summary_date DATE
last_plan_date DATE
last_monthly_review_date DATE
```

### Tabele complete
```sql
-- Journal
CREATE TABLE journal_entries (
    id SERIAL PRIMARY KEY,
    entry_date DATE NOT NULL UNIQUE,
    reflection_text TEXT,
    mood VARCHAR(20),
    tomorrow_focus TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Day Plans
CREATE TABLE day_plans (
    id SERIAL PRIMARY KEY,
    plan_date DATE NOT NULL UNIQUE,
    user_input TEXT,
    itinerary TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Goals
CREATE TABLE goals (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    deadline DATE,
    progress INTEGER DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE goal_tasks (
    id SERIAL PRIMARY KEY,
    goal_id INTEGER REFERENCES goals(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    is_completed BOOLEAN DEFAULT FALSE,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Budget
ALTER TABLE budget_limits ADD COLUMN IF NOT EXISTS alerted_80 BOOLEAN DEFAULT FALSE;
ALTER TABLE budget_limits ADD COLUMN IF NOT EXISTS alerted_100 BOOLEAN DEFAULT FALSE;

-- Health
CREATE TABLE health_logs (
    id SERIAL PRIMARY KEY,
    log_date DATE NOT NULL DEFAULT CURRENT_DATE,
    sleep_hours NUMERIC(4,2),
    sleep_quality VARCHAR(20),
    water_ml INTEGER,
    nutrition VARCHAR(20),   -- great/good/neutral/bad/terrible
    weight_kg NUMERIC(5,2),
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE UNIQUE INDEX ON health_logs(log_date);

-- Workouts
CREATE TABLE workouts (
    id SERIAL PRIMARY KEY,
    workout_date DATE NOT NULL DEFAULT CURRENT_DATE,
    type VARCHAR(50),
    duration_min INTEGER,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE workout_exercises (
    id SERIAL PRIMARY KEY,
    workout_id INTEGER REFERENCES workouts(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    sets INTEGER,
    reps INTEGER,
    weight_kg NUMERIC(5,2),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Books
CREATE TABLE books (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    author TEXT,
    total_pages INTEGER,
    pages_read INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'reading',
    rating INTEGER CHECK (rating BETWEEN 1 AND 5),
    started_at DATE DEFAULT CURRENT_DATE,
    finished_at DATE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE book_notes (
    id SERIAL PRIMARY KEY,
    book_id INTEGER REFERENCES books(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    page_number INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Focus Sessions
CREATE TABLE focus_sessions (
    id SERIAL PRIMARY KEY,
    session_date DATE NOT NULL DEFAULT CURRENT_DATE,
    duration_min INTEGER NOT NULL,
    task_description TEXT,
    completed BOOLEAN DEFAULT FALSE,
    interrupted_at INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Insight Log
CREATE TABLE insight_log (
    id SERIAL PRIMARY KEY,
    insight_type TEXT NOT NULL,
    sent_at TIMESTAMP DEFAULT NOW()
);
```

---

## Profil Utilizator (configurat)

```
Nume: Robu
Locație: Cluj-Napoca
Ocupație: Student
Tone: direct
Personal notes: Student la Cluj-Napoca. Facultate + freelancing + proiecte 
personale (Lora, DevD, Classlly). Face gym de 3-4 ori pe săptămână și fotbal 
ocazional. Habits zilnice: Citit, Duolingo, Șah, Gym. Goals 2026: termin anul 
universitar, cresc venitul din freelancing, masă musculară, găsesc un job ca 
developer. Fumează — buget țigări 550 RON/lună. Ton preferat: direct, fără filler.
```

---

## Habits Configurate

| Habit | Frecvență |
|-------|-----------|
| Citit | daily |
| Duolingo | daily |
| Șah | daily |
| Gym | daily |

---

## Bugete Configurate

| Categorie | Buget lunar (RON) |
|-----------|------------------|
| Mâncare | 400 |
| Ieșiri | 500 |
| Shopping | 150 |
| Abonamente | 75 |
| Sănătate | 150 |
| Țigări | 550 |

---

## Goals Active

| Goal | Deadline | Progress |
|------|----------|---------|
| Termin anul universitar | — | 0% |
| Cresc venitul din freelancing | — | 0% |
| Masă musculară | — | 0% |
| Îmi găsesc un job | — | 0% |

---

## Proiecte Active

Lora, Freelancing, Facultate, DevD, Classlly, Sesiune

---

## State Machine — Stări Active

| State | Când e setat | Comportament |
|-------|-------------|--------------|
| `awaiting_confirmation` | Delete/bulk action | Yes → execută, No → anulează |
| `awaiting_edit_field` | "editează X" fără câmp | Next msg → Gemini extrage câmpul |
| `awaiting_journal_response` | După send_journal_night() | Gemini extrage reflection_text, mood, tomorrow_focus → journal_entries → clear_state() |
| `awaiting_day_plan_input` | La finalul morning briefing | Userul descrie ziua → itinerar pe ore → day_plans → clear_state() |
| `in_focus_session` | La /focus N | Timer activ — la final trimite notificare |
| `awaiting_focus_result` | După timer focus | Userul descrie ce a făcut → salvat în focus_sessions → clear_state() |

---

## Comenzi Telegram

| Comandă | Ce face |
|---------|---------|
| `/reload` | Hard restart (os.execl) |
| `/podcast` | Forțează morning briefing |
| `/start` | Onboarding |
| `/journal` | Declanșează manual journal night |
| `/plan` | Cere itinerar nou (input de la user) |
| `/weeklyreview` | Forțează weekly review manual |
| `/monthlyreview` | Forțează monthly review manual |
| `/habitstreaks` | Generează heatmap PNG habits (365 zile) |
| `/timeblock` | Generează time block automat din tasks+events+health |
| `/focus N` | Pornește sesiune focus de N minute (default 25) |
| `/stopfocus` | Întrerupe sesiunea de focus activă |

---

## Ton și Personalitate (reguli în core/gemini.py)

**INTERZIS:**
- Filler phrases: "Sigur!", "Cu plăcere!", "Bineînțeles!", "Am înregistrat", "Am notat că"
- Superlative: "super", "fascinant", "minunat", "amazing"
- Emoji excesive (max 2 per mesaj), emoji 💖
- Romglish excesiv: "vibes", "the game plan", "all clear", "catch up", "wins", "achievements"
- Sugestii nesolicitate despre ce să facă userul seara

**OBLIGATORIU:**
- MAX 1 propoziție pentru acțiuni simple (add_task, log_habit, add_note)
- Liste curate fără fraze introductive pentru list_tasks/habits/events
- Romglish autentic: task/habit/meeting/gym/chess rămân în engleză, restul în română
- Proactivitate directă: menționează probleme fără să ceară permisiunea
- EOD și journal: ton mai cald, reflectiv, dar tot fără hype

---

## Intents Înregistrate (core/gemini.py + core/router.py)

### Tasks
`add_task`, `list_tasks`, `complete_task`, `delete_task`, `edit_task`

### Habits
`add_habit`, `list_habits`, `log_habit`, `delete_habit`, `habit_heatmap`

### Goals
`add_goal`, `list_goals`, `update_goal`, `add_goal_task`, `complete_goal_task`

### Finance
`log_expense`, `log_income`, `list_finance`, `set_budget`, `budget_forecast`

### Health
`health_log`, `health_summary`, `health_chart`, `health_insights`

### Workout
`workout_log`, `workout_list`, `workout_stats`

### Reading
`reading_add`, `reading_update`, `reading_complete`, `reading_note`, `reading_list`, `reading_stats`

### Focus
`focus_start`, `focus_stop`, `focus_list`

### Mood
`get_mood_chart`, `mood_chart`

### Insights
`get_insights`, `ask_insights`

### Time Blocking
`time_block`

### Altele
`add_note`, `list_notes`, `add_project`, `list_projects`, `archive_project`,
`add_event`, `list_events`, `add_item` (shopping), `list_items`, `get_weather`, `fetch_news`

---

## Scheduler — Joburi Active

| Job | Trigger | Note |
|-----|---------|------|
| `send_morning_briefing` | Zilnic 08:00 | Include time block integrat |
| `send_habit_reminder` | Zilnic 18:00 | Ton direct, max 2 propoziții |
| `send_eod_reflection` | Zilnic 21:00 | Max 100 cuvinte + TTS |
| `send_journal_night` | Zilnic 22:00 | 3 întrebări reflecție + TTS |
| `send_weekly_review` | Duminică 21:00 | Include health correlations |
| `send_monthly_review` | 1 ale lunii 20:00 | Max 200 cuvinte + TTS |
| `send_weekly_finance_summary` | Luni dimineață | Breakdown per categorie |
| `check_budget_forecast` | Joi 09:00 | Doar dacă >85% din buget proiectat |
| `check_proactive_insights` | Zilnic 09:30 | Max 2 insights, anti-spam 5 zile |
| `reset_budget_alerts` | 1 ale lunii 00:00 | Resetează alerted_80/100 |
| `missed_habit_nudge` | Zilnic 09:00 | Loghează 'missed' pentru ieri |
| `check_event_reminders` | La 15 minute | Remindere evenimente |

---

## Podcast — Specificații

**TTS:** voce `ro-RO-AlinaNeural`, strip emoji+URL+MarkdownV2, pauze naturale

**Structura morning briefing (text):**
```
━━━━━━━━━━━━━━━
☀️ Bună dimineața, Robu!
_joi, 19 martie_
━━━━━━━━━━━━━━━

🌤 Vremea
📋 Tasks de azi
📅 Evenimente
🔁 Habits pending
🗓 Time Block (generat automat)
💡 Focus
```

**Reguli podcast vocal:**
- 200-250 cuvinte, 90-120 secunde
- Exclusiv română (permis: task, habit, meeting, gym, chess)
- Fără Romglish excesiv, fără știri

---

## EOD Reflection — Structura

```
[Ce ai făcut — 2-3 prop.]
[O singură întrebare de reflecție]
Seară liniștită. 🌙
```
Maxim 100 cuvinte. Trimite și voice TTS.

---

## Journal Night — Flow

1. Job automat la 22:00 sau `/journal` manual
2. Lora trimite 3 întrebări de reflecție (text + voice)
3. State: `awaiting_journal_response`
4. Gemini extrage: reflection_text, mood, tomorrow_focus
5. Salvat în journal_entries
6. clear_state()
7. `last_journal_date` se setează LA TRIMITEREA PROMPT-ULUI

---

## Weekly Review — Structura

```
📊 Săptămâna [început] — [sfârșit]

✅ Tasks: X completate din Y
🔁 Habits: [top 3 cu streak]
💰 Cheltuieli: [total + categoria principală]
📈 Highlight: [Gemini]
🔍 Pattern observat: [health correlations dacă semnificative]
```
Maxim 200 cuvinte. Trimite și voice TTS.

---

## Monthly Review — Structura

```
📊 Review lunar — [luna] [anul]
━━━━━━━━━━━━━━━━━

✅ Tasks: X completate din Y create (Z%)
🔁 Habits: [top 2 consistente] / [cel mai ratat]
🎯 Goals: [care a avansat] / [care e blocat]
💰 Finance: [total] RON — [vs luna trecută]
😴 Health: somn mediu Xh · apă XL · greutate [trend]
😊 Mood: [dominant] — [distribuție scurtă]

🔍 Pattern: [observații concrete]
💡 Luna viitoare: [1 lucru specific]
```
Maxim 200 cuvinte. Trimite și voice TTS.

---

## Health Tracking

**Metrici:** somn (ore + calitate), apă (ml), nutriție (scale), greutate (kg)
**Input:** natural language → Gemini extrage valorile
**Chart:** PNG matplotlib, 3 subploturi (somn/apă/greutate), 30 zile
**Trigger chart:** "grafic health", "grafic somn", "cum am dormit"

---

## Workout Tracker

**Tipuri:** gym, fotbal, cardio, alergare, alt
**Input:** "am făcut gym 1h: bench 4×8 80kg, squat 3×10 100kg"
**View scurt:** ultimele 7 zile
**View lung:** ultimele 6 luni cu stats complete (sesiuni, volum, top exerciții, trend lunar)

---

## Reading Tracker

**Flow:** add → update progress → complete (cu rating 1-5) → note
**Format listă:**
```
📚 În curs
• Atomic Habits — 85/320 pag (27%) ████░░░░░░

✅ Terminate (2026)
• Deep Work — ⭐⭐⭐⭐⭐
```

---

## Proactive Insights

**Reguli verificate zilnic:**
- Somn < 6.5h 3 nopți consecutive
- Goal fără progres 14+ zile
- Habit streak rupt după 7+ zile
- Apă < 1L 3 zile la rând
- Tasks overdue >= 5

**Anti-spam:** același insight nu se repetă în 5 zile, max 2 per zi

---

## Budget Forecasting

**Logică:** medie zilnică × zile rămase → proiecție până la sfârșitul lunii
**Alertă proactivă:** joi 09:00, doar dacă proiecție >85% din buget
**Trigger manual:** "forecast buget", "cât mai pot cheltui"

---

## Habit Heatmap

- Grid GitHub-style, 52 săptămâni × N habits
- Culori: `#161b22` (empty) → `#39d353` (done)
- Streak curent afișat per habit
- Minim 1 zi de date
- Trigger: `/habitstreaks` sau "streak vizual"

---

## Time Blocking

- Generează automat din tasks + events + habits + health data
- Dacă somn < 6.5h → evită task-uri grele dimineața
- Dacă somn >= 8h → task-uri grele dimineața
- Format: `HH:MM — HH:MM · activitate`
- Maxim 8 blocuri, include pauze
- Trigger: `/timeblock`, "time block", "organizează-mi ziua"

---

## Focus Sessions (Pomodoro)

- `/focus N` → pornește timer N minute (default 25)
- La final → notificare → "Ce ai făcut?" → salvat în DB
- `/stopfocus` → întrerupe sesiunea
- Vizibil în weekly review (total ore focus)

---

## Finance — Alerte Budget

- 80-99%: `💡 Ai folosit 85% din bugetul de Mâncare (340/400 RON)`
- 100%+: `⚠️ Ai depășit bugetul de Mâncare (420/400 RON). +20 RON peste limită`
- Rezumat săptămânal: luni dimineață (job SEPARAT)
- Forecast: joi 09:00 (proactiv)

---

## Reguli Arhitectură — OBLIGATORII

1. Type hints pe toate funcțiile
2. Raw SQL asyncpg — `$1, $2` placeholders, NICIODATĂ string interpolation
3. Niciun ORM — toate queries în `db/queries/*.py`
4. Formatare EXCLUSIV prin `bot/formatter.py` — niciodată escape manual MarkdownV2
5. Modulele returnează `(str, InlineKeyboardMarkup | None)` — niciodată Telegram calls direct
6. `clear_state()` după orice flow stateful
7. Idempotență — toate job-urile verifică `last_*_date` înainte de acțiune
8. try/except în fiecare handler și job, cu mesaj friendly la user
9. `ruff check .` înainte de orice commit
10. `railway.json` cu `numReplicas: 1` — OBLIGATORIU pentru long polling

---

## Quirks & Gotchas

- SDK: `from google import genai` — NU `google-generativeai`
- `escape_md()` pentru text de la user, `safe_markdown()` pentru text de la Gemini
- `reply` în IntentResponse JSON: RAW MarkdownV2, fără backslash escaping
- Onboarding bypass-ează complet Gemini
- `conversation_state` are EXACT un rând cu `state_key='current'`
- `/reload` = `os.execl` hard restart — drops in-flight requests
- TTS salvează `.mp3` (Telegram acceptă și mp3 la send_voice)
- `last_journal_date` se setează la TRIMITERE, nu după răspuns user
- News (`modules/news.py`) există dar NU mai e în podcast — doar la cerere explicită
- Exercițiile din workout vin ca JSON strings din DB — parsează cu `json.loads()` înainte de `.get()`
- Conflicte Railway: `deleteWebhook` + restart manual dacă apar două instanțe

---

## Deploy

```bash
git add -A
git commit -m "descriere"
git push  # Railway auto-deploy
```
Verificare: `/start` în Telegram → `adaugă task: test`

---

## Taskuri Completate

| Task | Status |
|------|--------|
| Îmbunătățire podcast | ✅ |
| Morning Briefing + itinerar | ✅ |
| Journal Night | ✅ |
| Ton Lora (direct + concis) | ✅ |
| Podcast doar în română | ✅ |
| Știri eliminate din podcast | ✅ |
| EOD fix ton + limbă | ✅ |
| Tasks list grupat pe proiecte | ✅ |
| Goal Tracking | ✅ |
| Budget alertă 80% + depășire | ✅ |
| Rezumat săptămânal finance | ✅ |
| Mood Chart PNG | ✅ |
| Weekly Review automat | ✅ |
| Health Monitor (somn/apă/nutriție/greutate) | ✅ |
| Health Chart PNG | ✅ |
| Health correlations în weekly review | ✅ |
| Monthly Review | ✅ |
| Habit Streaks Heatmap PNG | ✅ |
| Workout Tracker (gym/fotbal/cardio) | ✅ |
| Budget Forecasting | ✅ |
| Proactive Insights (zilnic 09:30) | ✅ |
| Reading Tracker | ✅ |
| Pomodoro / Focus Sessions | ✅ (de testat) |
| Time Blocking (/timeblock) | ✅ |
| Habit reminder ton fix | ✅ |
| Reset complet DB + reconfigurare profil | ✅ |

## Taskuri În Așteptare

| Task | Note |
|------|------|
| Spaced Repetition | Complex — SM-2 algorithm, pe viitor |
| Apple Health Bridge (Shortcuts) | iOS automation, pe viitor |
| Companion app iOS (Xcode) | Pe viitor |

---

## Decizii Luate (să nu le rediscuți)

- **Orar facultate** — userul are orar alternant A/B, dar preferă să îi spună Lorei vocal dimineața. Zero setup în Lora.
- **Integrare API facultate** — app iOS nativă (Swift), fără API REST. Nu se integrează.
- **News în podcast** — eliminat complet. News există în bot doar la cerere explicită.
- **Grafic mood** — matplotlib gratuit, PNG în Telegram. Nu necesită servicii externe.
- **Calorii** — înlocuite cu câmp `nutrition` (scale great/good/neutral/bad/terrible). Mai simplu, mai util.
- **CMF Watch 1** — fără API public. Datele health se introduc manual în Lora.
- **Goals fără deadline** — userul preferă goals fără termen limită fix.
- **Habits în română** — Citit, Duolingo, Șah, Gym (nu reading/chess).
- **Railway numReplicas=1** — OBLIGATORIU pentru long polling Telegram. Zero downtime deploys = OFF.

---

*Generat: 2026-03-22 | Versiune Lora: v4.0*
