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
        
        # Row might exist but all relevant fields be null
        if row['state_type'] is None:
            return None
            
        return dict(row)

async def set_state(pool, state_type: str, module: Optional[str], action: Optional[str], item_id: Optional[int], extra: Optional[Dict[str, Any]] = None):
    """Sets the current multi-turn state."""
    extra_json = json.dumps(extra) if extra else None
    
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE conversation_state 
            SET state_type = $1, module = $2, action = $3, item_id = $4, extra = $5, created_at = NOW()
            WHERE state_key = 'current'
            """,
            state_type, module, action, item_id, extra_json
        )

async def clear_state(pool):
    """Resets the state to null/idle."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE conversation_state 
            SET state_type = NULL, module = NULL, action = NULL, item_id = NULL, extra = NULL
            WHERE state_key = 'current'
            """
        )
