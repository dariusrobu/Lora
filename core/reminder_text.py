"""Conservative normalization of explicit Romanian reminder requests."""

import re


def normalize_reminder_text(message: str) -> str:
    """Keep content intact while recognizing interrupted 'îmi aduci aminte'."""
    text = re.sub(
        r"\b(\d{1,2})[șş](\d{2})\b",
        lambda match: f"{match[1]}:{match[2]}"
        if int(match[1]) < 24 and int(match[2]) < 60 else match[0],
        message, flags=re.IGNORECASE,
    )
    match = re.fullmatch(
        r"\s*(?:(?:vreau\s+)?s[ăa]\s+)?[îi]mi\s+aduci\s+"
        r"(?:(.*?)\s+)?aminte\s+s[ăa]\s+(.+)",
        text, flags=re.IGNORECASE | re.DOTALL,
    )
    if match:
        when = (match[1] or "").strip()
        return f"Adu-mi aminte {when} să {match[2]}".replace("  ", " ")
    return text
