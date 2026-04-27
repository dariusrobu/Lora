import re

def safe_markdown(text: str) -> str:
    if not text:
        return ""
    must_escape = r"[]()~>#+-=|{}.!_"
    for char in must_escape:
        pattern = f"(?<!\\\\){re.escape(char)}"
        text = re.sub(pattern, f"\\{char}", text)
    return text

text = """📊 *Health — ultimele 7 zile*

😴 *Somn:* medie 8.0h · Good
💧 *Apă:* medie 2000ml · max 3000ml
⚖️ *Greutate:* 75.5kg (trend: →)
🍎 *Nutriție Azi:* 1500/2000 kcal (75%) · 100g P"""

print(safe_markdown(text))
