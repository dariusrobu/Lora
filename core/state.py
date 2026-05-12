import json
from typing import Optional, Dict, Any


async def get_state(pool) -> Optional[Dict[str, Any]]:
    """Retrieves the current multi-turn state."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM conversation_state WHERE state_key = 'current'"
        )
        if not row:
            return None

        data = dict(row)
        
        # Row might exist but all relevant fields be null
        # Use .get() to avoid KeyErrors if columns are missing in the DB
        state_type = data.get("state_type")
        last_intent = data.get("last_intent")
        
        if state_type is None and last_intent is None:
            return None
        
        # Parse JSON fields
        for field in ["extra", "last_intent"]:
            if data.get(field) and isinstance(data[field], str):
                try:
                    data[field] = json.loads(data[field])
                except json.JSONDecodeError:
                    pass
        return data


async def set_state(
    pool,
    state_type: str,
    module: Optional[str],
    action: Optional[str],
    item_id: Optional[int],
    extra: Optional[Dict[str, Any]] = None,
):
    """Sets the current multi-turn state."""
    print(
        f"🔄 set_state called: state_type='{state_type}', module='{module}', action='{action}', item_id={item_id}",
        flush=True,
    )
    extra_json = json.dumps(extra) if extra else None

    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE conversation_state 
            SET state_type = $1, module = $2, action = $3, item_id = $4, extra = $5, created_at = NOW()
            WHERE state_key = 'current'
            """,
            state_type,
            module,
            action,
            item_id,
            extra_json,
        )


class CustomEncoder(json.JSONEncoder):
    """Handles non-serializable objects like datetime."""
    def default(self, obj):
        from datetime import datetime, date, time
        if isinstance(obj, (datetime, date, time)):
            return obj.isoformat()
        return super().default(obj)


async def save_last_action(pool, intent_response: Dict[str, Any], item_id: Optional[int] = None):
    """Saves the last executed action for potential undo/correction."""
    module = intent_response.get("module")
    
    try:
        # Store full intent response as JSON
        intent_json = json.dumps(intent_response, cls=CustomEncoder)
        
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE conversation_state 
                SET last_intent = $1, last_inserted_id = $2, last_module = $3
                WHERE state_key = 'current'
                """,
                intent_json,
                item_id,
                module
            )
    except Exception as e:
        print(f"⚠️ Failed to save_last_action: {e}")


async def clear_state(pool):
    """Resets the state to null/idle (preserving last action for undo)."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE conversation_state 
            SET state_type = NULL, module = NULL, action = NULL, item_id = NULL, extra = NULL
            WHERE state_key = 'current'
            """
        )
