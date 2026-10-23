"""Compact navigation and action entry points for Telegram summaries."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo


READ_INTENTS = {
    "today", "tomorrow", "calendar", "tasks", "reminders", "university",
    "news", "money", "balance", "expenses", "workout",
}

MENU_COMMANDS = (
    ("azi", "Ziua mea"),
    ("calendar", "Calendarul pe 7 zile"),
    ("taskuri", "Taskuri pe proiecte"),
    ("remindere", "Reminderele mele"),
    ("facultate", "Programul facultății"),
    ("noutati", "Anunțuri și forumuri"),
    ("bani", "Sold și cheltuieli"),
    ("antrenament", "Antrenamente"),
)

COMMAND_INTENTS = {
    "azi": "today", "maine": "tomorrow", "calendar": "calendar",
    "taskuri": "tasks", "remindere": "reminders", "facultate": "university",
    "noutati": "news", "bani": "money", "antrenament": "workout",
    "sold": "balance", "cheltuieli": "expenses",
}

_LINKS = {
    "today": (("Mâine", "tomorrow"), ("Calendar", "calendar"), ("Remindere", "reminders")),
    "tomorrow": (("Azi", "today"), ("Calendar", "calendar")),
    "calendar": (("Azi", "today"), ("Remindere", "reminders"), ("Facultate", "university")),
    "tasks": (("Azi", "today"), ("Calendar", "calendar")),
    "reminders": (("Calendar", "calendar"), ("Azi", "today")),
    "university": (("Noutăți", "news"), ("Calendar", "calendar")),
    "news": (("Facultate", "university"),),
    "money": (("Sold", "balance"), ("Cheltuieli", "expenses")),
    "balance": (("Bani", "money"), ("Cheltuieli", "expenses")),
    "expenses": (("Bani", "money"), ("Sold", "balance")),
    "workout": (("Azi", "today"),),
}

_ACTION_LABELS = {
    "today": "Acțiuni pentru azi", "tomorrow": "Acțiuni pentru mâine",
    "calendar": "Alege din calendar", "tasks": "Acțiuni taskuri",
    "reminders": "Acțiuni remindere", "university": "Acțiuni facultate",
    "news": "Acțiuni noutăți", "money": "Acțiuni bani",
    "balance": "Acțiuni bani", "expenses": "Acțiuni bani",
    "workout": "Acțiuni antrenament",
}


def navigation_keyboard(intent: str, mini_app_url: str = "") -> InlineKeyboardMarkup | None:
    if intent not in READ_INTENTS:
        return None
    buttons = [InlineKeyboardButton(label, callback_data=f"v2:n:{target}")
               for label, target in _LINKS.get(intent, ())]
    rows = [buttons] if buttons else []
    rows.append([InlineKeyboardButton(_ACTION_LABELS[intent], callback_data=f"v2:a:{intent}")])
    if mini_app_url:
        rows.append([InlineKeyboardButton("Deschide Lora", web_app=WebAppInfo(url=mini_app_url))])
    return InlineKeyboardMarkup(rows) if rows else None
