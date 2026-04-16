# Prompt: Add Internal API to Lora (PA Bot)

## Context

Lora is an existing Telegram bot (see PA_BOT_OVERVIEW.md). She already runs an `aiohttp` web server on port 8080 with two routes: `/` (health check) and `/calendar/{token}` (WebCal feed). 

Your task is to **add a new internal REST API** to this existing aiohttp server. This API will be called by the Business Council bots to fetch Lora's data. Do NOT modify any existing Lora logic — only add new routes.

---

## Security

All new `/api/*` routes must be protected by a **shared secret header**:

```
X-Internal-Secret: {value of LORA_API_SECRET env var}
```

Add `LORA_API_SECRET` to `core/config.py` validation. Any request without the correct header must return `401 Unauthorized`.

Create a reusable `require_auth(request)` async helper in a new file `api/auth.py`.

---

## New File: `api/routes.py`

Create this file. It must contain all the new route handlers described below. Each handler:
- Calls the relevant existing DB query functions (from `db/queries/`) — do not write raw SQL in routes
- Returns `application/json`
- Handles exceptions with a `500` response and error message

---

## Routes to Implement

### GET `/api/projects`
Returns all projects from the existing `projects` table.

Response:
```json
[
  {
    "id": 1,
    "name": "Project Alpha",
    "description": "...",
    "status": "active",
    "created_at": "2024-01-01T00:00:00"
  }
]
```

### GET `/api/projects/{project_id}`
Returns a single project by ID including related tasks and goals.

Response:
```json
{
  "id": 1,
  "name": "Project Alpha",
  "description": "...",
  "status": "active",
  "tasks": [
    {"id": 1, "title": "...", "priority": "high", "done": false}
  ],
  "goals": [
    {"id": 1, "title": "...", "target_date": "2024-06-01", "progress": 40}
  ]
}
```

### GET `/api/tasks`
Returns all pending (not done) tasks, ordered by priority then due date.

Optional query param: `?project_id=1` to filter by project.

Response:
```json
[
  {
    "id": 1,
    "title": "...",
    "priority": "high",
    "due_date": "2024-02-01",
    "project_id": 1,
    "project_name": "Project Alpha"
  }
]
```

### GET `/api/finances/summary`
Returns a financial summary: total income, total expenses, balance, and top spending categories for the current month.

Response:
```json
{
  "month": "2024-02",
  "total_income": 5000.00,
  "total_expenses": 3200.00,
  "balance": 1800.00,
  "top_categories": [
    {"category": "Food", "amount": 800.00},
    {"category": "Transport", "amount": 400.00}
  ],
  "budget_alerts": [
    {"category": "Entertainment", "limit": 200.00, "spent": 250.00}
  ]
}
```

### GET `/api/context`
Returns a compact text snapshot of the user's current life context — reuse the existing `core/context.py` `build_context_snapshot()` function (or equivalent). This is the most important endpoint: it gives the council bots the same situational awareness Lora has.

Response:
```json
{
  "snapshot": "## Today (Wednesday Feb 14)\n- 3 pending high-priority tasks\n- Budget on track...",
  "generated_at": "2024-02-14T09:00:00"
}
```

### GET `/api/memory`
Returns recent long-term memory facts from the `memory_facts` table.

Optional query param: `?limit=20` (default 20).

Response:
```json
[
  {
    "id": 1,
    "fact": "User is building a SaaS product called Alpha",
    "created_at": "2024-01-15T10:00:00"
  }
]
```

### POST `/api/memory`
Allows the council bots to store a new memory fact in Lora's `memory_facts` table so both Lora and the council share the same long-term memory.

Request body:
```json
{
  "fact": "User decided to postpone Project Alpha launch to Q3"
}
```

Response:
```json
{"id": 42, "fact": "...", "created_at": "..."}
```

---

## Wiring into the Existing Server

In the existing file that sets up the `aiohttp` `Application` (likely `main.py` or wherever aiohttp routes are registered), import and add all routes from `api/routes.py`. Prefix them all with `/api`.

Example pattern:
```python
from api.routes import setup_api_routes
setup_api_routes(app)  # adds all /api/* routes to the existing app
```

---

## Notes

- Do NOT create a new aiohttp server or change the port (8080)
- Do NOT use any ORM — follow Lora's existing pattern of raw `asyncpg` queries
- Reuse the existing DB pool from `db/connection.py`
- The response format must always be valid JSON — use `aiohttp.web.json_response()`
- Add `LORA_API_SECRET` to the `.env.example` file
