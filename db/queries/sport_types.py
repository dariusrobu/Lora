# db/queries/sport_types.py


async def get_all_sports(pool) -> list[dict]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM sport_types ORDER BY category ASC, id ASC"
        )
    return [dict(r) for r in rows]


async def get_sports_by_category(pool, category: str) -> list[dict]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM sport_types WHERE category = $1 ORDER BY id ASC", category
        )
    return [dict(r) for r in rows]


async def add_sport(
    pool,
    name: str,
    category: str,
    has_distance: bool,
    has_weight: bool,
    has_reps: bool,
    icon: str,
) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO sport_types (name, category, has_distance, has_weight, has_reps, icon)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING *
        """,
            name,
            category,
            has_distance,
            has_weight,
            has_reps,
            icon,
        )
    return dict(row)


async def update_sport(pool, sport_id: int, **kwargs) -> dict:
    if not kwargs:
        raise ValueError("No fields provided to update")

    set_clauses = []
    values = []

    for i, (key, value) in enumerate(kwargs.items(), start=1):
        set_clauses.append(f"{key} = ${i}")
        values.append(value)

    values.append(sport_id)
    query = f"UPDATE sport_types SET {', '.join(set_clauses)} WHERE id = ${len(values)} RETURNING *"

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *values)
    return dict(row) if row else {}


async def get_sport_by_name(pool, name: str) -> dict | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM sport_types WHERE LOWER(name) = LOWER($1)", name
        )
    return dict(row) if row else None


async def delete_sport(pool, sport_id: int) -> bool:
    async with pool.acquire() as conn:
        # Verifica daca are workouts
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM workouts WHERE sport_id = $1", sport_id
        )
        if count > 0:
            return False  # Are referinte, nu putem sterge

        res = await conn.execute("DELETE FROM sport_types WHERE id = $1", sport_id)
        return res == "DELETE 1"
