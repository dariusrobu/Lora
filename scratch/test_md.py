import re


def safe_markdown(text: str) -> str:
    if not text:
        return ""
    must_escape = r"[]()~>#+-=|{}.!"
    for char in must_escape:
        pattern = f"(?<!\\\\){re.escape(char)}"
        text = re.sub(pattern, f"\\{char}", text)
    return text


test_text = "Hello! (World) - [Test] + = | { } . # > ~"
print(f"Original: {test_text}")
print(f"Formatted: {safe_markdown(test_text)}")

test_bold = "This is *bold* and this is ! exclamation."
print(f"Bold Test: {safe_markdown(test_bold)}")
