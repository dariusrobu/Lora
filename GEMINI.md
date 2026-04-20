# Lora System Prompt Reference

> This document contains the system prompt and intent schema used by Lora's Gemini integration.

---

## System Prompt Overview

The system prompt in `core/gemini.py` defines:
- Lora's personality (Romglish, warm but direct)
- Supported intents and their data schemas
- Tone modes: warm, direct, brief
- Special instructions for data extraction
- Module-specific capabilities

---

## Key Intents

### Tasks (`module="tasks"`)
- `add_task` — Add new task with optional project, priority, due date
- `list_tasks` — List tasks, optionally filtered by project
- `complete_task` — Mark task as done
- `edit_task` — Edit task title, priority, due date, project
- `delete_task` — Delete a task

### Projects (`module="projects"`)
- `add_project` — Create project with name, description, deadline, priority, category
- `list_projects` — List all projects with task counts
- `view_project` — View project details with tasks and notes
- `update_project` — Update project metadata
- `update_progress` — Set progress percentage (auto-calculated from tasks)
- `archive_project` — Archive a project
- `delete_project` — Delete a project

### Finance (`module="finance"`)
- `finance_log` — Log expense or income
- `finance_summary` — Show dashboard
- `finance_chart` — Show spending trend
- `list_categories` — List expense categories
- `add_category` — Add custom category
- `delete_category` — Remove category
- `set_budget` — Set budget limit for category

### Skills (`module="skills"`)
- `log_skill` — Log skill progress (e.g., "am făcut 20 min sah")
- `view_skills` — Show skills dashboard
- `add_habit` — Create new habit
- `log_habit` — Mark habit done
- `list_habits` — List habits
- `delete_habit` — Remove habit

### University (`module="university"`)
- `uni_add_subject` — Add new subject
- `uni_list` — Show academic status
- `uni_log_attendance` — Log presence/absence
- `uni_add_grade` — Add grade
- `uni_add_exam` — Add exam
- `uni_exams` — List upcoming exams
- `uni_attendance_warning` — Check attendance

### Health (`module="health"`)
- `health_log` — Log sleep, water, weight
- `log_water` — Add water intake
- `health_summary` — Show health stats
- `health_chart` — Show trends

### Workout (`module="workout"`)
- `workout_log` — Log workout with exercises
- `workout_list` — List workouts
- `workout_stats` — Show statistics
- `workout_prs` — Show personal records
- `workout_add_sport` — Add new sport
- `workout_add_exercise` — Add new exercise

### Other Modules
- `notes` — Notes and journaling
- `events` — Calendar events and reminders
- `shopping` — Shopping list
- `goals` — Goal tracking with sub-tasks
- `focus` — Focus sessions (Pomodoro)
- `planner` — Time blocking
- `mood` — Mood tracking
- `insights` — AI-powered pattern analysis
- `memory` — Long-term memory facts
- `weather` — Weather info
- `news` — Tech news

---

## Council Integration Intents

When connected to the Business Council system:

- **Task completion** triggers feedback loop asking difficulty (1-10)
- **Morning briefing** includes executive summary from Council
- **Jargon translation** available for Council bot messages

---

## Response Schema

```json
{
  "intent": "add_task",
  "module": "tasks",
  "data": {
    "title": "string",
    "priority": "high|medium|low",
    "due_date": "YYYY-MM-DD",
    "project": "string"
  },
  "reply": "Lora's response in MarkdownV2",
  "needs_confirmation": false,
  "needs_agent": false
}
```

---

## Tone Guidelines

| Tone | Description |
|------|-------------|
| `warm` | Friendly, supportive, slightly longer |
| `direct` | Concise, actionable, minimal fluff |
| `brief` | Shortest possible responses |

---

## Data Extraction Rules

### Tasks
- title = text after separator (:) or full message
- project = value after "proiectul" or "project"
- priority = high/medium/low

### Finance
- Extract amount and category from keywords
- Default: category="altele" if unclear
- Type: expense (default) or income

### Dates
- "mâine" = tomorrow
- "poimâine" = day after tomorrow
- ISO format: YYYY-MM-DD

---

*For full system prompt, see `core/gemini.py`*