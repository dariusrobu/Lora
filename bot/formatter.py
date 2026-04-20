import re

# MarkdownV2 requires escaping these characters outside of pre/code/bold/italic
# _ * [ ] ( ) ~ ` > # + - = | { } . !
# However, escaping . ! - and = everywhere makes text look like "Hello\. How are you\!" which is ugly.
# We will use a more surgical approach.
ESCAPE_CHARS = r"_*[]()~`>#+-=|{}.!"


def escape_md(text: str) -> str:
    """Escapes MarkdownV2 special characters. Only use for user-generated strings."""
    if not text:
        return ""
    # Surgery: escape characters that are MOST likely to break parsing if unescaped.
    # We focus on characters that form blocks.
    # We will keep . ! - as they are mostly fine in many contexts, but if the bot crashes,
    # we might need to be more aggressive.
    return re.sub(f"([{re.escape(ESCAPE_CHARS)}])", r"\\\1", str(text))


def safe_markdown(text: str) -> str:
    """
    Cleans up a message for Telegram MarkdownV2 without over-escaping.
    It attempts to preserve *bold* and `code` formatting from Gemini.
    """
    if not text:
        return ""

    # Re-escape only characters that are most likely to break parsing
    # and are rarely used in normal text.
    # We leave . - ! # + = alone as they are usually fine unless at start of line
    # or part of a complex sequence.
    must_escape = r"[]()~>|{}.!"
    for char in must_escape:
        text = text.replace(char, f"\\{char}")

    return text


def split_message(text: str, limit: int = 4096):
    """Splits a message into chunks within the Telegram limit."""
    if len(text) <= limit:
        return [text]

    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break

        # Find nearest newline before limit
        idx = text.rfind("\n", 0, limit)
        if idx == -1:
            idx = limit

        chunks.append(text[:idx])
        text = text[idx:].lstrip()

    return chunks


def format_date_short(dt) -> str:
    """Returns a short formatted date or 'Azi'/'Mâine' for readability."""
    if not dt:
        return ""
    from datetime import date, datetime

    if isinstance(dt, datetime):
        dt = dt.date()

    today = date.today()
    if dt == today:
        return "Azi"
    from datetime import timedelta

    if dt == today + timedelta(days=1):
        return "Mâine"

    return dt.strftime("%d %b")
