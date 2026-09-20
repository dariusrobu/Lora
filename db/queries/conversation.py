from typing import Any, Dict


async def get_summary(pool, user_id: int) -> str:
    async with pool.acquire() as conn:
        value = await conn.fetchval(
            "SELECT summary FROM conversation_summary WHERE user_id = $1", user_id
        )
    return value or ""


async def save_summary(pool, user_id: int, summary: str) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO conversation_summary (user_id, summary, updated_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT (user_id) DO UPDATE
            SET summary = EXCLUDED.summary, updated_at = NOW()
            """,
            user_id,
            summary[:6000],
        )


async def summarize_if_needed(pool, user_id: int, history: list[Dict[str, Any]]) -> None:
    """Keep a compact local summary once the raw window becomes long."""
    if len(history) < 16:
        return
    from core.gemini import generate_text_response

    transcript = "\n".join(
        f"{'Utilizator' if item['role'] == 'user' else 'Lora'}: {item['content']}"
        for item in history[-20:]
    )
    prompt = (
        "Rezuma conversația de mai jos în română, în maximum 120 de cuvinte. "
        "Păstrează doar obiectivele, deciziile, preferințele și întrebările rămase. "
        "Nu include parole, tokenuri, sume exacte sau date medicale sensibile. "
        "Răspunde doar cu rezumatul.\n\n" + transcript
    )
    try:
        summary = await generate_text_response([{"role": "user", "content": prompt}])
        if summary.strip():
            await save_summary(pool, user_id, summary.strip())
    except Exception:
        return
