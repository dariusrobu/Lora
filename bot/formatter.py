import re
from datetime import date, datetime

# MarkdownV2 requires escaping these characters outside of pre/code/bold/italic
# _ * [ ] ( ) ~ ` > # + - = | { } . !
ESCAPE_CHARS = r"_*[]()~`>#+-=|{}.!"


def escape_md(text: str) -> str:
    """Escapes all MarkdownV2 special characters."""
    if not text:
        return ""
    # We use a set of characters that strictly must be escaped in MarkdownV2
    return re.sub(f"([{re.escape(ESCAPE_CHARS)}])", r"\\\1", str(text))


def safe_markdown(text: str) -> str:
    """
    Cleans up a message for Telegram MarkdownV2 without over-escaping.
    It attempts to preserve *bold* and `code` formatting from Gemini.
    """
    if not text:
        return ""

    # Characters that MUST be escaped in MarkdownV2 (excluding *, `, _ for formatting)
    # Note: hyphen '-' is critical and often missed.
    must_escape = r"[]()~>#+-=|{}.!"

    # We use regex to avoid double-escaping if a backslash is already there
    for char in must_escape:
        # Match char NOT preceded by a backslash
        pattern = f"(?<!\\\\){re.escape(char)}"
        text = re.sub(pattern, f"\\{char}", text)

    return text


def split_message(text: str, limit: int = 4000):
    """Splits a message into chunks within the Telegram limit (default 4096, but we use 4000 for safety)."""
    if not text:
        return [""]
    if len(text) <= limit:
        return [text]

    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break

        # Find nearest newline before limit to split cleanly
        idx = text.rfind("\n", 0, limit)
        if idx <= 0:
            # If no newline, find nearest space
            idx = text.rfind(" ", 0, limit)
            if idx <= 0:
                idx = limit

        chunks.append(text[:idx].strip())
        text = text[idx:].lstrip()

    return chunks


def format_date_ro(dt: date | datetime) -> str:
    """Returns a Romanian-friendly date string."""
    if isinstance(dt, datetime):
        dt = dt.date()

    today = date.today()
    if dt == today:
        return "Azi"
    from datetime import timedelta

    if dt == today + timedelta(days=1):
        return "Mâine"

    return dt.strftime("%d %b")


def format_date_short(dt: date | datetime) -> str:
    """Alias for format_date_ro."""
    return format_date_ro(dt)
