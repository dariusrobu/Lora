"""
Tests for core/dispatcher.py — dynamic module import, signature inspection,
and module whitelist validation.
"""
import asyncio
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Whitelist / valid modules (must match router.py whitelist)
# Note: 'calendar' is not a standalone module file (handled via calendar_module)
# ---------------------------------------------------------------------------

VALID_MODULES = [
    "tasks", "projects", "notes", "finance", "events", "shopping",
    "goals", "skills", "mood", "insights", "health", "nutrition",
    "workout", "university", "schedule", "reading", "focus",
    "planner", "memory", "weather", "calendar_module",
    "integrations", "travel", "wishlist", "news",
]


def test_dispatcher_importable():
    from core.dispatcher import execute_module_intent  # type: ignore
    assert callable(execute_module_intent)


def test_valid_modules_all_importable():
    """Each module in the whitelist must be importable (modules/ folder present)."""
    import importlib
    failed = []
    for mod_name in VALID_MODULES:
        try:
            importlib.import_module(f"modules.{mod_name}")
        except ImportError as e:
            failed.append(f"{mod_name}: {e}")
    assert not failed, f"Failed to import modules: {failed}"


def test_dispatcher_rejects_unknown_module():
    """Dispatching to an unknown module must return an error tuple, not raise."""
    from core.dispatcher import execute_module_intent  # type: ignore

    pool = MagicMock()
    async def _run():
        # Pass all required positional args (pool, module, intent, data, reply, user_id, bot)
        result = await execute_module_intent(pool, "nonexistent_module", "list_tasks", {}, "", 0, None)
        return result

    result = asyncio.run(_run())
    # Result must be a tuple (reply, keyboard, item_id)
    assert isinstance(result, tuple)
    reply = result[0]
    assert isinstance(reply, str)
