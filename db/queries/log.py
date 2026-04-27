from typing import Optional
import asyncpg


async def log_execution(
    pool: asyncpg.Pool,
    intent: Optional[str],
    module: Optional[str],
    success: bool,
    error_type: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    """
    Inserts a row into execution_log after each execution.
    """
    query = """
        INSERT INTO execution_log (intent, module, success, error_type, error_message)
        VALUES ($1, $2, $3, $4, $5)
    """
    try:
        await pool.execute(query, intent, module, success, error_type, error_message)
    except Exception as e:
        # Failsafe so that logging itself doesn't crash the router
        print(f"Failed to write to execution_log: {e}")
