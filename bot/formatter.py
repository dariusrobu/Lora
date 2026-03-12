import re

# MarkdownV2 requires escaping these characters
# _ * [ ] ( ) ~ ` > # + - = | { } . !
ESCAPE_CHARS = r'_*[]()~`>#+-=|{}.!'

def escape_md(text: str) -> str:
    """Escapes MarkdownV2 special characters."""
    if not text:
        return ""
    # We must use a regex that finds any of the characters in ESCAPE_CHARS
    # and prefixes them with a backslash.
    return re.sub(f'([{re.escape(ESCAPE_CHARS)}])', r'\\\1', str(text))

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
        idx = text.rfind('\n', 0, limit)
        if idx == -1:
            idx = limit
            
        chunks.append(text[:idx])
        text = text[idx:].lstrip()
        
    return chunks
