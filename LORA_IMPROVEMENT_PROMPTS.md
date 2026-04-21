# LORA — Improvement Prompts for AI Coding Agent

> Fiecare secțiune conține un prompt gata de dat agentului de coding.
> Execută-le în ordine. Nu sări peste Faza 1.

---

## FAZA 1 — Stabilizare

### 1.1 — Logging + Error Boundary în Router

```
Adaugă un sistem de logging structurat în `core/router.py`.

Cerințe:
- Importă `logging` și configurează un logger dedicat pentru router
- Wrappează fiecare apel de modul într-un try/except cu cel puțin 3 tipuri de excepții: KeyError (câmp lipsă din intent data), asyncpg.PostgresError (eroare DB), și Exception (fallback general)
- La fiecare execuție reușită, loghează: intent, module, cheile din data (nu valorile sensibile), și timestamp
- La fiecare eroare, loghează: intent, module, tipul erorii, mesajul erorii, și intent_data primit
- Creează o tabelă `execution_log` în DB cu coloanele: id, intent, module, success (bool), error_type, error_message, created_at
- După fiecare execuție (reușită sau nu), inserează un rând în `execution_log`
- Returnează un mesaj user-friendly în română la eroare, niciodată stack trace raw

Fișiere de modificat: `core/router.py`, `db/schema.sql`, `db/queries/` (adaugă `log.py`)
```

---

### 1.2 — State Machine Persistat în DB

```
Migrează `core/state.py` de la stocare în memorie (dict Python) la stocare persistentă în PostgreSQL.

Cerințe:
- Creează tabela `conversation_state` cu coloanele: user_id (PK), state_data (JSONB), step (VARCHAR), updated_at (TIMESTAMP)
- Înlocuiește toate operațiile pe dict-ul in-memory cu funcții async: `save_state(user_id, state_dict)`, `get_state(user_id) -> dict`, `clear_state(user_id)`
- Folosește `ON CONFLICT (user_id) DO UPDATE` pentru upsert
- Adaugă timeout automat: dacă `updated_at` e mai vechi de 10 minute, `get_state` returnează `{}` și șterge rândul
- Adaugă funcția `is_in_flow(user_id) -> bool` care verifică dacă există o stare activă și neexpirată
- Toate funcțiile trebuie să fie async și să folosească conexiunea asyncpg existentă din `db/`

Fișiere de modificat: `core/state.py`, `db/schema.sql`, `db/queries/state.py` (fișier nou)
```

---

### 1.3 — Callback Handlers — Pattern Consistent

```
Refactorizează toți callback handlers din `bot/handler.py` pentru a urma un pattern consistent și corect.

Cerințe:
- Prima linie din orice callback handler trebuie să fie `await query.answer()` — fără excepții
- Creează o funcție utilitară `make_callback_data(action: str, *params) -> str` care serializează datele ca `"action:param1:param2"` și validează că rezultatul e sub 64 bytes (limita Telegram)
- Creează o funcție utilitară `parse_callback_data(data: str) -> tuple[str, list[str]]` care face parsing invers
- Înlocuiește toate `callback_data` hardcodate din cod cu apeluri la `make_callback_data`
- Adaugă un handler generic de fallback pentru callback-uri necunoscute care loghează și răspunde cu mesaj de eroare
- Înregistrează `CallbackQueryHandler` în `main.py` dacă nu există deja

Fișiere de modificat: `bot/handler.py`, `main.py`
```

---

### 1.4 — IntentResponse Schema Îmbunătățită

```
Îmbogățește modelul Pydantic `IntentResponse` din `core/gemini.py` cu descrieri clare și câmpuri noi.

Cerințe:
- Adaugă câmpul `confidence: float` cu `Field(ge=0.0, le=1.0, description="Scorul de certitudine al intent-ului detectat. Sub 0.7 = incert.")`
- Adaugă câmpul `source: str` cu `Field(default='text', pattern='^(text|voice)$')`
- Adaugă câmpul `clarification_needed: bool` cu `Field(default=False, description="True dacă mesajul e ambiguu și necesită clarificare înainte de execuție")`
- Adaugă câmpul `clarification_question: Optional[str]` care conține întrebarea de clarificare dacă `clarification_needed` e True
- Adaugă descrieri `Field(description=...)` pentru toate câmpurile existente: intent, module, data, reply, needs_confirmation
- În `core/router.py`: dacă `confidence < 0.7` sau `clarification_needed == True`, nu executa modulul — trimite în schimb `clarification_question` ca răspuns utilizatorului și salvează intenția parțială în `conversation_state`

Fișiere de modificat: `core/gemini.py`, `core/router.py`
```

---

### 1.5 — System Prompt cu Few-Shot Examples

```
Rescrie system prompt-ul din `core/gemini.py` pentru a include exemple concrete (few-shot prompting) pentru fiecare intent frecvent.

Cerințe:
- Păstrează secțiunile existente de personalitate și capabilități
- Adaugă o secțiune `EXEMPLE DE CLASIFICARE CORECTĂ` cu minimum 2 exemple per intent pentru: add_task, complete_task, finance_log, finance_summary, log_skill, health_log, workout_log, uni_log_attendance, add_goal
- Fiecare exemplu trebuie să arate: mesajul utilizatorului → intent + module + data exactă
- Adaugă instrucțiuni explicite pentru: câmpul `confidence` (când să fie mic), `clarification_needed` (când să fie True), formatul datelor temporale (ISO 8601), și cum să trateze mesajele în română cu greșeli de scriere
- Adaugă o secțiune `REGULI STRICTE` care specifică: reply-ul să fie maxim 2 propoziții, întotdeauna în română, fără filler phrases ("Desigur!", "Cu plăcere!")

Fișiere de modificat: `core/gemini.py`
```

---

### 1.6 — Voice Messages — Normalizare Pre-NLP

```
Adaugă un pas de normalizare a textului transcris din mesaje vocale înainte de analiza intent în `core/gemini.py`.

Cerințe:
- Creează funcția async `normalize_voice_text(raw: str) -> str` care face un apel Gemini separat cu promptul: "Textul următor vine dintr-o transcriere vocală și poate fi informal sau incomplet. Reformulează-l ca o comandă clară păstrând exact intenția originală. Nu adăuga informații noi. Transcriere: {raw}"
- În handler-ul de voice din `bot/handler.py`, apelează `normalize_voice_text` pe textul transcris înainte de `analyze_intent`
- Setează `source='voice'` în `IntentResponse` pentru mesajele vocale
- Dacă normalizarea eșuează, folosește textul original (nu bloca flow-ul)
- Adaugă logging pentru a vedea textul original vs. textul normalizat

Fișiere de modificat: `core/gemini.py`, `bot/handler.py`
```

---

### 1.7 — Migrări DB — Convenție și Completare

```
Stabilește o convenție clară pentru migrările din `db/migrations/` și completează secvența lipsă.

Cerințe:
- Creează fișierul `db/migrations/002_conversation_state.sql` care adaugă tabela `conversation_state` (din task 1.2)
- Creează fișierul `db/migrations/005_execution_log.sql` care adaugă tabela `execution_log` (din task 1.1)
- Adaugă un header standard la fiecare fișier de migrare nou: `-- Migration: NNN_descriere.sql`, `-- Date: YYYY-MM-DD`, `-- Description: ce face migrarea`
- Creează fișierul `db/migrations/README.md` care documentează: convenția de naming (NNN_descriere.sql), cum se rulează o migrare, ordinea obligatorie de execuție
- Actualizează `README.md` principal cu comanda de rulare a noilor migrări

Fișiere de creat: `db/migrations/002_conversation_state.sql`, `db/migrations/005_execution_log.sql`, `db/migrations/README.md`
Fișiere de modificat: `README.md`
```

---

## FAZA 2 — NLP Avansat

### 2.1 — Confidence Threshold + Clarificare Automată

```
Implementează logica de confidence threshold în `core/router.py` bazată pe câmpurile adăugate în Faza 1.4.

Cerințe:
- Dacă `intent_response.confidence < 0.7`: nu executa nicio acțiune, salvează intent_response parțial în `conversation_state` cu step='awaiting_clarification', returnează `intent_response.clarification_question` ca mesaj
- Dacă `intent_response.clarification_needed == True`: același comportament ca mai sus
- Dacă utilizatorul răspunde la o întrebare de clarificare (step='awaiting_clarification' în state): combină răspunsul cu intenția salvată și retrimite la `analyze_intent` cu context îmbogățit
- Adaugă în system prompt instrucțiuni pentru cum să genereze `clarification_question` — scurt, direct, maxim 10 cuvinte

Fișiere de modificat: `core/router.py`, `core/gemini.py`
```

---

### 2.2 — Multi-Intent Parsing

```
Adaugă suport pentru mesaje care conțin mai multe intenții simultane în `core/gemini.py` și `core/router.py`.

Cerințe:
- Modifică `IntentResponse` pentru a suporta un câmp opțional `additional_intents: Optional[list[IntentResponse]]`
- Actualizează system prompt-ul să detecteze când un mesaj conține mai multe acțiuni (ex: "adaugă task și loghează cheltuiala") și să le returneze în `additional_intents`
- În `core/router.py`, după execuția intent-ului principal, iterează `additional_intents` și execută-le secvențial
- Dacă oricare din intenții eșuează, continuă cu celelalte și raportează toate rezultatele la final
- Răspunsul final să fie un sumar al tuturor acțiunilor executate, în română

Fișiere de modificat: `core/gemini.py`, `core/router.py`
```

---

### 2.3 — Intent Correction (Undo/Corectare)

```
Adaugă posibilitatea ca utilizatorul să corecteze ultima acțiune executată fără să reia de la zero.

Cerințe:
- Salvează ultimul `IntentResponse` executat cu succes în `conversation_state` sub cheia `last_intent`
- Detectează în system prompt mesaje de corecție ("nu asta vroiam", "greșit", "anulează", "undo") și returnează intent `correct_last`
- În router, dacă intent == `correct_last`: preia `last_intent` din state, trimite la Gemini un prompt de corecție cu contextul original + mesajul de corecție al utilizatorului
- Adaugă funcție `undo_last_action(intent_response)` în fiecare modul relevant (tasks, finance, health, workout) care face rollback pe ultima inserție (DELETE WHERE id = last_inserted_id)
- Salvează `last_inserted_id` în `conversation_state` după fiecare INSERT reușit

Fișiere de modificat: `core/router.py`, `core/gemini.py`, `modules/tasks.py`, `modules/finance.py`, `modules/health.py`, `modules/workout.py`
```

---

### 2.4 — Context Window — Ultimele N Mesaje

```
Adaugă context conversațional (ultimele mesaje) în fiecare apel la `analyze_intent` din `core/gemini.py`.

Cerințe:
- Creează tabela `message_history` cu coloanele: id, user_id, role (user/assistant), content, created_at
- Salvează fiecare mesaj primit și fiecare răspuns trimis în `message_history`
- Creează funcția `get_recent_history(user_id, limit=8) -> list[dict]` care returnează ultimele N perechi mesaj-răspuns
- În `analyze_intent`, include istoricul în formatul `messages=[..., {"role": "user", "content": msg}]` dacă SDK-ul suportă, sau adaugă-l în system prompt ca secțiune `CONVERSAȚIE RECENTĂ:`
- Păstrează maxim 30 de zile de istoric în DB — adaugă un job de cleanup în `scheduler/jobs.py`

Fișiere de modificat: `core/gemini.py`, `db/schema.sql`, `db/queries/history.py` (fișier nou), `scheduler/jobs.py`
```

---

### 2.5 — Date/Time Intelligence

```
Îmbunătățește rezolvarea expresiilor temporale relative în `core/gemini.py`.

Cerințe:
- Adaugă în system prompt o secțiune `CONTEXT TEMPORAL` care include: data și ora curentă în timezone-ul utilizatorului, ziua săptămânii, și o listă de exemple de rezolvare ("mâine" = data de mâine în ISO 8601, "săptămâna viitoare luni" = data calculată, "în weekend" = sâmbăta următoare)
- Injectează contextul temporal dinamic la fiecare apel `analyze_intent` — nu hardcoda data în prompt
- Creează funcția `build_temporal_context(timezone: str) -> str` în `core/context.py` care generează acest context
- Adaugă validare Pydantic pe câmpurile de dată din modulele relevante: dacă data e în trecut cu mai mult de 1 an sau în viitor cu mai mult de 2 ani, setează `confidence=0.5`

Fișiere de modificat: `core/gemini.py`, `core/context.py`
```

---

### 2.6 — Typo Tolerance

```
Adaugă toleranță la greșeli de scriere în mesajele utilizatorului înainte de analiza NLP.

Cerințe:
- Adaugă în system prompt instrucțiuni explicite: "Utilizatorul poate scrie în română cu diacritice lipsă, greșeli de tastare, sau prescurtări. Interpretează intenția, nu forma exactă."
- Creează o listă de normalizări comune în `core/gemini.py`: fără diacritice → cu diacritice (ex: "cheltuiala" → "cheltuială"), prescurtări frecvente ("azi" = today, "săpt" = săptămâna, "min" = minute)
- Adaugă un pre-processing simplu înainte de `analyze_intent` care aplică normalizările din listă
- Testează cu exemple: "am cheltuit 50 lei pe mancare" (fără diacritice) și "adauga task sa sun la doctor" trebuie să funcționeze corect

Fișiere de modificat: `core/gemini.py`
```

---

## FAZA 3 — Memory & Context

### 3.1 — Long-Term Memory Activă și Automată

```
Transformă `memory_facts` dintr-un sistem pasiv într-unul care extrage automat informații importante din conversații.

Cerințe:
- Adaugă în system prompt instrucțiuni pentru a detecta și returna fapte demne de memorat: preferințe exprimate, informații personale relevante, decizii repetate, pattern-uri de comportament
- Adaugă câmpul opțional `memory_extracts: Optional[list[dict]]` în `IntentResponse` cu structura `{fact: str, category: str, confidence: float}`
- În `core/router.py`, după fiecare execuție reușită, dacă `memory_extracts` nu e gol, salvează automat în `memory_facts` faptele cu `confidence > 0.8`
- Adaugă câmpul `source` în `memory_facts` (manual/auto) și `expires_at` (opțional, pentru fapte temporare)
- Deduplică: înainte de inserție, verifică dacă un fapt similar există deja (comparație pe `category` + primele 50 de caractere din `fact`)

Fișiere de modificat: `core/gemini.py`, `core/router.py`, `db/schema.sql`, `db/queries/memory.py`
```

---

### 3.2 — User Profile Complet și Dinamic

```
Extinde tabela `user_profile` pentru a stoca preferințe și comportamente învățate din interacțiuni.

Cerințe:
- Adaugă coloanele în `user_profile`: `preferred_tone` (VARCHAR: formal/casual/direct), `active_hours_start` (TIME), `active_hours_end` (TIME), `frequent_categories` (JSONB), `language_style` (JSONB pentru preferințe de răspuns)
- Creează funcția `update_profile_from_behavior(user_id)` în `modules/` care rulează săptămânal și actualizează `frequent_categories` bazat pe cele mai folosite categorii din `finances` și `tasks` din ultimele 30 de zile
- Adaugă profilul în contextul fiecărui apel `analyze_intent` prin `build_context()` din `core/context.py`
- Adaugă comanda `/profile` în `bot/handler.py` care afișează profilul curent și permite editarea manuală a `preferred_tone` și `active_hours`

Fișiere de modificat: `db/schema.sql`, `core/context.py`, `bot/handler.py`, `scheduler/jobs.py`
```

---

### 3.3 — Proactive Memory Usage

```
Fă ca Lora să folosească activ memoria în răspunsuri, nu doar să o stocheze.

Cerințe:
- În `build_context()` din `core/context.py`, include primele 5 `memory_facts` relevante pentru subiectul curent (folosește o căutare simplă pe `category` care se potrivește cu `module`-ul detectat)
- Adaugă în system prompt instrucțiuni: "Dacă există fapte relevante în MEMORIA UTILIZATORULUI, menționează-le scurt în răspuns când e cazul. Ex: 'Data trecută ai menționat că...'"
- La adăugarea unui task similar cu unul completat recent (același titlu parțial), adaugă automat în răspuns: "Ai mai avut un task similar pe [data] — a durat [X] zile"
- Creează funcția `find_similar_tasks(title: str, user_id: int) -> list` în `db/queries/tasks.py` care face căutare fuzzy pe titlu (ILIKE '%keyword%')

Fișiere de modificat: `core/context.py`, `core/gemini.py`, `db/queries/tasks.py`, `modules/tasks.py`
```

---

### 3.4 — Semantic Search în Memorie

```
Adaugă căutare semantică în `memory_facts` și `message_history` pentru query-uri de tipul "ce știe Lora despre X".

Cerințe:
- Adaugă intent `memory_search` în router și system prompt cu exemplul: "ce știi despre sănătatea mea" → intent: memory_search, data: {topic: "sănătate"}
- Creează `modules/memory.py` (sau extinde dacă există) cu funcția `search_memory(topic: str, user_id: int)` care caută în `memory_facts` și `message_history` folosind PostgreSQL full-text search (`to_tsvector` + `to_tsquery`)
- Adaugă index GIN pe coloana `fact` din `memory_facts` pentru performanță
- Răspunsul să fie un sumar structurat: "Despre [topic], știu: [lista de fapte relevante]"
- Adaugă și comanda `/memory` care afișează toate `memory_facts` grupate pe categorii

Fișiere de modificat: `modules/memory.py`, `core/router.py`, `db/schema.sql`, `bot/handler.py`
```

---

## FAZA 4 — Modules Profunde

### 4.1 — Tasks: Dependențe, Recurență, și Estimare

```
Extinde modulul `modules/tasks.py` și tabela `tasks` cu funcționalități avansate.

Cerințe:
- Adaugă coloana `depends_on` (INTEGER FK → tasks.id, nullable) în tabela `tasks`
- La completarea unui task, verifică dacă există alte task-uri care depind de el și trimite notificare: "Task-ul X e acum deblocat"
- Adaugă coloana `recurrence` (VARCHAR: none/daily/weekly/monthly, default: none) și `next_due` (TIMESTAMP)
- La completarea unui task recurrent, creează automat instanța următoare cu `next_due` calculat
- Adaugă coloanele `estimated_minutes` (INTEGER) și `started_at` (TIMESTAMP)
- La completarea unui task cu `estimated_minutes` setat, calculează diferența față de `started_at` și salvează în `memory_facts` ca pattern: "Task-ul tip [categorie] a durat [X] minute, estimat [Y] minute"
- Actualizează system prompt cu exemple pentru: "task care depinde de X", "task zilnic", "marchează ca început"

Fișiere de modificat: `modules/tasks.py`, `db/schema.sql`, `db/queries/tasks.py`, `core/gemini.py`
```

---

### 4.2 — Finance: Bugete, Pattern Detection, Previziuni

```
Extinde modulul `modules/finance.py` cu analiză financiară proactivă.

Cerințe:
- Adaugă tabela `finance_budgets` cu coloanele: id, category_id (FK), monthly_limit (DECIMAL), user_id
- La fiecare `finance_log`, verifică dacă suma cheltuielilor din luna curentă pe categoria respectivă depășește 80% din `monthly_limit` — dacă da, adaugă un warning în răspuns
- Creează funcția `detect_spending_patterns(user_id)` care rulează săptămânal și salvează în `memory_facts` pattern-uri de tip: "Cheltuieli medii pe [categorie]: [X] RON/lună"
- Adaugă intent `finance_forecast` care calculează: dacă ritmul de cheltuieli din primele N zile ale lunii continuă, care e totalul estimat la final de lună
- Adaugă intent `finance_compare` care compară luna curentă cu luna anterioară per categorie
- Adaugă comanda `/budget` pentru setarea și vizualizarea bugetelor

Fișiere de modificat: `modules/finance.py`, `db/schema.sql`, `db/queries/finance.py`, `scheduler/jobs.py`, `bot/handler.py`
```

---

### 4.3 — Health & Workout: Streaks, Corelații, Obiective

```
Extinde `modules/health.py` și `modules/workout.py` cu tracking de consistență și corelații.

Cerințe:
- Adaugă coloana `streak_count` (INTEGER) și `last_activity_date` (DATE) în tabela `workouts` (sau o tabelă separată `streaks`)
- La fiecare `workout_log`, calculează și actualizează streak-ul — dacă ziua precedentă are log, incrementează, altfel resetează la 1
- Adaugă în răspunsul la `workout_log` streak-ul curent: "Zi [N] consecutivă 🔥"
- Creează funcția `correlate_health_workout(user_id)` care rulează săptămânal: verifică dacă zilele fără workout coincid cu `health_logs` cu valori negative (mood scăzut, energie scăzută) și salvează corelația în `memory_facts`
- Adaugă tabel `health_goals` cu: goal_type (weight/steps/sleep), target_value, current_value, deadline
- Adaugă intent `health_goal_progress` care afișează progresul față de obiective

Fișiere de modificat: `modules/health.py`, `modules/workout.py`, `db/schema.sql`, `scheduler/jobs.py`
```

---

### 4.4 — Skills & Habits: Decay Detection și Habit Stacking

```
Extinde `modules/skills.py` cu mecanisme de menținere a consistenței.

Cerințe:
- Adaugă coloana `last_logged_at` (TIMESTAMP) și `frequency_target` (VARCHAR: daily/weekly/monthly) în tabela `skills`
- Creează un job în `scheduler/jobs.py` care rulează zilnic la 20:00 și verifică toate skill-urile cu `frequency_target` setat — dacă `last_logged_at` e mai veche decât target, trimite reminder: "Nu ai logat [skill] de [X] zile"
- Adaugă coloana `habit_group` (VARCHAR, nullable) în `skills` pentru habit stacking — skill-uri din același grup sunt afișate împreună la reminder
- La `log_skill`, dacă skill-ul face parte dintr-un `habit_group`, afișează celelalte skill-uri din grup care nu au fost logate azi: "Ai logat [X]. Ai mai logat și [Y], [Z] din același grup?"
- Adaugă intent `view_habit_groups` care afișează grupurile și statusul fiecărui skill din zi

Fișiere de modificat: `modules/skills.py`, `db/schema.sql`, `db/queries/skills.py`, `scheduler/jobs.py`
```

---

### 4.5 — University: Calculator Medie și Alertă Prezențe

```
Extinde `modules/university.py` cu calcule automate și alerte proactive.

Cerințe:
- Adaugă coloana `credit_weight` (INTEGER) în tabela `subjects` pentru calculul mediei ponderate
- Creează funcția `calculate_gpa(user_id) -> float` în `db/queries/university.py` care calculează media ponderată din toate notele din `grades`
- La orice `uni_add_grade`, afișează automat media actualizată: "Notă adăugată. Media ta curentă: [X.XX]"
- Adaugă coloana `max_absences` (INTEGER) în `subjects`
- La orice `uni_log_attendance` cu prezență = absent, verifică dacă numărul de absențe se apropie de limită (>= 80%) și avertizează
- Adaugă job săptămânal care verifică deadline-uri de lucrări/examene din `schedule` și trimite reminder cu 3 zile și 1 zi înainte

Fișiere de modificat: `modules/university.py`, `db/schema.sql`, `db/queries/university.py`, `scheduler/jobs.py`
```

---

## FAZA 5 — Scheduler & Proactivitate

### 5.1 — Morning Briefing Inteligent

```
Rescrie job-ul de morning briefing din `scheduler/jobs.py` pentru a genera un brief prioritizat, nu un dump de date.

Cerințe:
- Structura briefing-ului trebuie să fie: (1) Urgent azi — task-uri cu deadline azi sau depășit, (2) De decis — task-uri blocate sau în așteptare, (3) Focus recomandat — cel mai important task bazat pe prioritate și deadline, (4) Situație financiară — sold estimat și alertă bugete aproape de limită dacă e cazul, (5) Streak-uri active — pentru a motiva continuarea
- Generează textul briefing-ului printr-un apel Gemini care primește datele structurate și le transformă în text natural, concis, în română
- Dacă nu există task-uri urgente sau date relevante pentru o secțiune, omite secțiunea complet
- Adaugă un mesaj de motivație scurt la final generat de Gemini bazat pe contextul zilei
- Elimină secțiunile goale — un briefing fără date relevante trebuie să fie scurt, nu plin de "Nu există..."

Fișiere de modificat: `scheduler/jobs.py`, `core/context.py`
```

---

### 5.2 — EOD Reflection Interactivă

```
Transformă EOD reflection dintr-un reminder pasiv într-o sesiune interactivă scurtă.

Cerințe:
- La ora EOD, trimite un mesaj cu 3 întrebări rapide prezentate ca butoane inline: "Cum a fost ziua? [Productivă] [Medie] [Slabă]"
- După răspuns la prima întrebare, trimite a doua: "Ai finalizat task-urile planificate? [Da, toate] [Parțial] [Nu]"
- Salvează răspunsurile în `health_logs` (câmpul mood/energy existent sau coloane noi)
- La final, generează un sumar de 2-3 rânduri bazat pe activitatea zilei (task-uri completate, cheltuieli logate, workout) și răspunsurile la întrebări
- Dacă utilizatorul nu răspunde în 30 de minute, nu retrimite — marchează reflection ca skipped în DB

Fișiere de modificat: `scheduler/jobs.py`, `bot/handler.py`, `db/schema.sql`
```

---

### 5.3 — Nudges Contextuale

```
Adaugă un sistem de notificări proactive bazate pe context în `scheduler/jobs.py`.

Cerințe:
- Creează un job care rulează la fiecare oră între 10:00 și 20:00 și verifică condițiile de nudge
- Condiții de nudge: (1) task cu deadline mâine și status != completed → alertă seara la 19:00, (2) nicio cheltuială logată în ultimele 48h → "Ai uitat să loghezi cheltuielile?", (3) streak pe cale să se rupă (nu a fost logat workout azi și e ora 18:00+) → reminder, (4) buget categorie depășit → alertă imediată la depășire
- Fiecare nudge trebuie trimis maxim o dată la 24h per condiție — adaugă tabela `sent_nudges` cu: nudge_type, sent_at pentru deduplicare
- Nudge-urile trebuie să fie scurte, max 2 propoziții, fără ton alarmist

Fișiere de modificat: `scheduler/jobs.py`, `db/schema.sql`
```

---

### 5.4 — Weekly Review Automat

```
Adaugă un job de weekly review care rulează duminică seara și generează un raport complet.

Cerințe:
- Colectează din DB pentru săptămâna trecută: număr task-uri completate vs. create, cheltuieli totale per categorie vs. buget, zile de workout, streak-uri, note universitate adăugate, skill-uri logate
- Trimite datele la Gemini cu instrucțiunea de a genera un raport narativ în română, nu o listă de cifre — stilul trebuie să fie ca un review de la un asistent care înțelege contextul
- Raportul trebuie să conțină: ce a mers bine, ce ar putea fi îmbunătățit, și un singur focus recomandat pentru săptămâna următoare
- Salvează raportul în DB (tabelă `weekly_reviews`: week_start, week_end, content, created_at)
- Adaugă comanda `/lastweek` care afișează ultimul weekly review

Fișiere de modificat: `scheduler/jobs.py`, `db/schema.sql`, `bot/handler.py`
```

---

## FAZA 6 — Reliability & Resilience

### 6.1 — Fallback Gemini la Downtime

```
Adaugă handling explicit pentru situațiile în care Gemini API e indisponibil.

Cerințe:
- Wrappează toate apelurile Gemini din `core/gemini.py` în try/except care prinde: `google.api_core.exceptions.ServiceUnavailable`, `google.api_core.exceptions.DeadlineExceeded`, și `Exception` generic
- La eroare de API, returnează un `IntentResponse` cu intent='api_unavailable' și reply='Sunt offline momentan, încearcă din nou în câteva minute. 🔧'
- Adaugă retry logic: 2 retry-uri cu exponential backoff (2s, 4s) înainte de a considera API-ul down
- Loghează fiecare incident de downtime în `execution_log` cu `error_type='api_unavailable'`
- Adaugă o variabilă de stare `_api_available: bool` care e setată la False după 3 eșecuri consecutive și la True după primul succes — afișează un mesaj de revenire când se recuperează

Fișiere de modificat: `core/gemini.py`
```

---

### 6.2 — Retry Logic pentru DB și API Calls

```
Adaugă retry logic cu exponential backoff pentru toate operațiunile de rețea din proiect.

Cerințe:
- Creează un decorator `@with_retry(max_attempts=3, base_delay=1.0)` în `core/utils.py` (fișier nou) care implementează exponential backoff
- Aplică decoratorul pe toate funcțiile din `core/council.py` care fac HTTP calls
- Aplică decoratorul pe funcțiile critice din `db/queries/` care fac INSERT/UPDATE (nu SELECT)
- La epuizarea retry-urilor, loghează eroarea și propagă excepția cu un mesaj descriptiv
- Adaugă timeout explicit (10 secunde) la toate HTTP calls din `core/council.py` dacă nu există deja

Fișiere de creat: `core/utils.py`
Fișiere de modificat: `core/council.py`, `db/queries/tasks.py`, `db/queries/finance.py`
```

---

### 6.3 — Health Check Endpoint

```
Adaugă un endpoint HTTP de health check pentru monitorizarea stării Lora din exterior.

Cerințe:
- Adaugă un server HTTP simplu (aiohttp sau http.server async) în `main.py` care rulează pe portul din ENV (`HEALTH_CHECK_PORT`, default 8080)
- Endpoint `GET /health` returnează JSON: `{status: 'ok', db: 'connected'/'error', gemini: 'available'/'unavailable', uptime_seconds: N, last_message_at: ISO_timestamp}`
- Testează conexiunea DB la fiecare health check cu un query simplu `SELECT 1`
- Testează disponibilitatea Gemini folosind variabila `_api_available` din task 6.1
- Salvează `last_message_at` ca variabilă globală, actualizată la fiecare mesaj primit

Fișiere de modificat: `main.py`
```

---

### 6.4 — Graceful Degradation

```
Asigură că eșecul unui modul nu afectează funcționarea celorlalte.

Cerințe:
- În `core/router.py`, fiecare modul trebuie apelat într-un try/except independent — eșecul modulului `finance` nu trebuie să blocheze modulul `tasks`
- Dacă un modul eșuează, răspunsul trebuie să fie specific: "Nu am putut accesa modulul de finanțe momentan, dar celelalte funcții sunt disponibile"
- Adaugă o funcție `check_module_health() -> dict` care testează disponibilitatea fiecărui modul și returnează statusul
- La startup (`main.py`), rulează `check_module_health()` și loghează orice modul cu probleme

Fișiere de modificat: `core/router.py`, `main.py`
```

---

## FAZA 7 — UX & Interacțiune

### 7.1 — Ton Adaptiv

```
Adaugă detectarea stării emoționale/contextuale a utilizatorului și adaptarea tonului răspunsurilor.

Cerințe:
- Adaugă în system prompt instrucțiuni pentru a detecta tonul mesajului: grăbit (mesaj scurt, fără punctuație), stresat (cuvinte cheie: "urgent", "repede", "nu am timp"), relaxat (mesaj lung, detaliat)
- Adaugă câmpul `detected_tone: Optional[str]` în `IntentResponse` cu valori: 'rushed'/'stressed'/'relaxed'/'neutral'
- În `core/router.py`, setează în `conversation_state` tonul detectat
- Adaugă în system prompt reguli de adaptare: ton 'rushed' → răspuns maxim 1 propoziție, ton 'stressed' → răspuns empatic + acțiune imediată, ton 'relaxed' → poți adăuga context și sugestii
- Respectă și `preferred_tone` din `user_profile` ca override permanent față de detecția dinamică

Fișiere de modificat: `core/gemini.py`, `core/router.py`
```

---

### 7.2 — Răspunsuri Scurte by Default

```
Impune un standard de răspunsuri concise în tot sistemul.

Cerințe:
- Adaugă în system prompt regula: răspunsul standard pentru confirmare de acțiune trebuie să fie maxim 1 propoziție (ex: "Task adăugat ✓" nu "Cu plăcere! Am adăugat task-ul tău în listă cu succes!")
- Definește tipologii de răspuns în system prompt: (1) Confirmare simplă — 1 propoziție, (2) Sumar de date — maxim 5 rânduri, (3) Raport — poate fi lung, (4) Eroare — 1 propoziție + ce să facă utilizatorul
- Adaugă câmpul `response_type: str` în `IntentResponse` cu valorile: 'confirmation'/'summary'/'report'/'error'/'clarification'
- Elimină din system prompt orice fraze de politețe excesivă: "Desigur!", "Cu plăcere!", "Bineînțeles că te ajut!"

Fișiere de modificat: `core/gemini.py`
```

---

### 7.3 — Comenzi Rapide

```
Adaugă comenzi Telegram directe pentru acțiunile cele mai frecvente, fără a trece prin NLP.

Cerințe:
- Adaugă comenzile în `bot/handler.py` și înregistrează-le în `main.py`:
  - `/tasks` — listează task-urile active de azi
  - `/done [titlu sau id]` — marchează rapid un task ca terminat
  - `/add [text]` — adaugă rapid un task fără confirmare
  - `/money [suma] [categorie]` — loghează rapid o cheltuială
  - `/summary` — sumar rapid al zilei (tasks + finanțe + streak)
  - `/week` — weekly review cel mai recent
  - `/memory` — afișează memory_facts grupate pe categorii
- Fiecare comandă trebuie să funcționeze fără apel Gemini — direct la modulul relevant
- Setează comenzile în BotFather via `application.bot.set_my_commands()` la startup

Fișiere de modificat: `bot/handler.py`, `main.py`
```

---

### 7.4 — Formatare Consistentă MarkdownV2

```
Auditează și standardizează toate mesajele trimise de bot pentru a elimina erori de formatare MarkdownV2.

Cerințe:
- Creează funcția `safe_md(text: str) -> str` în `bot/formatter.py` care escapeează corect toate caracterele speciale MarkdownV2: `_ * [ ] ( ) ~ \` > # + - = | { } . !`
- Creează funcții de formatare reutilizabile în `bot/formatter.py`: `bold(text)`, `italic(text)`, `code(text)`, `bullet_list(items: list)`, `numbered_list(items: list)`
- Înlocuiește toate string-urile de răspuns hardcodate din module cu apeluri la aceste funcții
- Adaugă un test simplu la startup care trimite un mesaj de test cu toate elementele de formatare pentru a valida că MarkdownV2 funcționează corect
- Adaugă `parse_mode=ParseMode.MARKDOWN_V2` explicit la fiecare `bot.send_message` dacă nu e deja setat

Fișiere de modificat: `bot/formatter.py`, toate `modules/*.py`
```

---

### 7.5 — Feedback Loop

```
Adaugă posibilitatea ca utilizatorul să marcheze un răspuns ca greșit și să ofere feedback.

Cerințe:
- La fiecare răspuns al bot-ului care a executat o acțiune, adaugă un buton inline discret: "✓ Corect | ✗ Greșit"
- Dacă utilizatorul apasă "✗ Greșit", întreabă scurt: "Ce ar fi trebuit să fac?" și salvează răspunsul în tabela `feedback` cu: intent_used, user_correction, created_at
- Adaugă intent `show_feedback_stats` (accesat via `/feedback` comandă) care afișează ultimele 10 feedback-uri negative
- Adaugă un rezumat al feedback-ului negativ în weekly review — "Acțiuni greșite săptămâna asta: [N]" — pentru a știi ce intenții trebuie îmbunătățite în system prompt

Fișiere de modificat: `bot/handler.py`, `db/schema.sql`, `scheduler/jobs.py`
```

---

## FAZA 8 — Intelligence Layer

### 8.1 — Mirror Weekly — Pattern Recognition

```
Adaugă un job de analiză săptămânală a pattern-urilor cross-module în `scheduler/jobs.py`.

Cerințe:
- Creează funcția `generate_mirror_report(user_id)` care colectează date din ultimele 4 săptămâni din: `tasks`, `finances`, `health_logs`, `workouts`, `skills`
- Trimite datele agregate la Gemini cu promptul: "Analizează aceste date și identifică 3 pattern-uri comportamentale clare. Fii specific și bazează-te pe cifre, nu pe generalități. Formulează în română, direct, fără introduceri."
- Salvează raportul în `weekly_reviews` cu `type='mirror'`
- Trimite raportul utilizatorului duminică seara, separat de weekly review standard, cu titlul "🪞 Reflecție săptămânală"
- Include cel puțin o corelație cross-module: ex. corelație între zile de workout și task-uri completate

Fișiere de modificat: `scheduler/jobs.py`, `db/schema.sql`
```

---

### 8.2 — Corelații Cross-Module

```
Adaugă analiză de corelații automate între module în raportul zilnic și weekly review.

Cerințe:
- Creează funcția `calculate_correlations(user_id, days=30) -> list[dict]` în `core/analytics.py` (fișier nou) care calculează corelații simple:
  - Zile cu workout vs. task-uri completate (mai multe sau mai puține)
  - Cheltuieli vs. mood (dacă există date de mood)
  - Ore de somn (dacă e logat) vs. productivitate (tasks completate)
- Returnează o listă de corelații cu: `{metric_a, metric_b, direction: 'positive'/'negative'/'none', strength: float}`
- Include corelațiile semnificative (strength > 0.3) în weekly review
- Adaugă intent `show_correlations` pentru comanda `/insights` care afișează corelațiile curente

Fișiere de creat: `core/analytics.py`
Fișiere de modificat: `scheduler/jobs.py`, `bot/handler.py`
```

---

### 8.3 — Obiective pe Termen Lung și Aliniere Zilnică

```
Extinde modulul `modules/goals.py` pentru ca Lora să alinieze activitățile zilnice la obiectivele pe termen lung.

Cerințe:
- Adaugă câmpul `time_horizon` (VARCHAR: week/month/quarter/year) în tabela `goals`
- Adaugă câmpul `linked_habits` (JSONB: lista de skill IDs) și `linked_task_keywords` (JSONB: lista de cuvinte cheie) în `goals`
- Creează funcția `check_goal_alignment(user_id)` care verifică zilnic dacă task-urile completate conțin keyword-uri din `linked_task_keywords` ale obiectivelor active
- Includeîn morning briefing o linie de aliniere: "Azi poți avansa spre [obiectiv]: [task recomandat]"
- Adaugă intent `goal_progress` care arată pentru fiecare obiectiv activ: progresul, zile rămase, și ultima activitate aliniată

Fișiere de modificat: `modules/goals.py`, `db/schema.sql`, `db/queries/goals.py`, `scheduler/jobs.py`
```

---

### 8.4 — Suggestions Proactive

```
Adaugă un sistem de sugestii proactive bazate pe absența activității sau pe pattern-uri detectate.

Cerințe:
- Creează funcția `generate_suggestions(user_id) -> list[str]` în `core/analytics.py` care verifică condițiile:
  - Nicio cheltuială logată în 24h → "Ai uitat să loghezi cheltuielile de azi?"
  - Nicio activitate pe un skill cu `frequency_target=daily` → "Nu ai logat [skill] azi"
  - Task cu deadline în 2 zile și status pending → "Ai [task] cu deadline pe [data] — vrei să îl marchezi ca început?"
  - Cheltuieli neobișnuit de mari față de media lunară (>150%) → "Cheltuielile de azi sunt mai mari decât de obicei"
- Rulează `generate_suggestions` la fiecare oră activă și trimite maxim 1 sugestie per oră
- Sugestiile trebuie să fie acționabile — include un buton inline pentru acțiunea sugerată

Fișiere de modificat: `core/analytics.py`, `scheduler/jobs.py`, `bot/handler.py`
```

---

## Note pentru Agent

> - Respectă convenția de cod existentă: async/await peste tot, asyncpg pentru DB, fără ORM
> - Toate textele vizibile pentru utilizator trebuie să fie în română
> - Comentariile în cod rămân în engleză
> - Rulează `ruff check .` și `ruff format .` după fiecare modificare
> - Adaugă migrare SQL pentru orice modificare de schemă
> - Nu modifica fișiere din afara Lora (nu atinge Council sau Rexi)
