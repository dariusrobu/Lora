def make_callback_data(action: str, *params) -> str:
    """Serializes action and params into a Telegram callback string."""
    data = action
    if params:
        data += ":" + ":".join(str(p) for p in params)

    if len(data.encode("utf-8")) > 64:
        raise ValueError(f"Callback data too long (max 64 bytes): {data}")
    return data


def parse_callback_data(data: str) -> tuple[str, list]:
    """Parses a callback string into action and params."""
    if not data:
        return "", []

    parts = data.split(":")
    return parts[0], parts[1:]
