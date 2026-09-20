"""Local agent tool metadata.

The current Ollama agent uses its own JSON prompt, but this lightweight schema
is retained for dashboard and future local-tool integrations.  It intentionally
does not import any cloud SDK.
"""

from typing import Any


def get_lora_tools() -> list[dict[str, Any]]:
    """Return locally executable tool descriptions."""
    return [
        {
            "name": "add_task",
            "description": "Adaugă un task nou în lista de activități.",
            "required": ["title"],
        },
        {
            "name": "finance_log",
            "description": "Înregistrează o cheltuială sau un venit.",
            "required": ["amount", "type", "category"],
        },
        {
            "name": "log_skill",
            "description": "Înregistrează progresul pentru un skill sau un obicei.",
            "required": ["skill_name", "value"],
        },
        {
            "name": "health_log",
            "description": "Înregistrează date despre sănătate.",
            "required": [],
        },
    ]
