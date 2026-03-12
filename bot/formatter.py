import re

ESCAPE_CHARS = r'\_*[]()~`>#+-=|{}.!'

def escape_md(text: str) -> str:
    """Escapes MarkdownV2 special characters."""
    if not text:
        return ""
    return re.sub(f'([{re.escape(ESCAPE_CHARS)}])', r'\\\1', str(text))
