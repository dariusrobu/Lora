from typing import List, Dict, Any
from datetime import date

async def log_meal(pool, meal_date: date, meal_type: str, total_macros: Dict[str, float], description: str, items: List[Dict[str, Any]]):
    """Logs a meal and its individual items."""
    async with pool.acquire() as conn:
        async with conn.transaction():
            # 1. Insert meal
            meal_id = await conn.fetchval(
                """
                INSERT INTO meals (meal_date, meal_type, total_calories, total_protein, total_carbs, total_fat, description)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                meal_date, meal_type, 
                total_macros.get("calories", 0),
                total_macros.get("protein", 0),
                total_macros.get("carbs", 0),
                total_macros.get("fat", 0),
                description
            )
            
            # 2. Insert items
            for item in items:
                await conn.execute(
                    """
                    INSERT INTO meal_items (meal_id, food_name, quantity_g, calories, protein, carbs, fat)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    meal_id, item["name"], item.get("quantity_g"),
                    item.get("calories", 0), item.get("protein", 0),
                    item.get("carbs", 0), item.get("fat", 0)
                )
            return meal_id

async def get_daily_totals(pool, log_date: date) -> Dict[str, float]:
    """Gets total macros for a specific date."""
    query = """
        SELECT 
            COALESCE(SUM(total_calories), 0) as calories,
            COALESCE(SUM(total_protein), 0) as protein,
            COALESCE(SUM(total_carbs), 0) as carbs,
            COALESCE(SUM(total_fat), 0) as fat
        FROM meals
        WHERE meal_date = $1
    """
    row = await pool.fetchrow(query, log_date)
    return dict(row)

async def get_nutrition_targets(pool) -> Dict[str, int]:
    """Gets nutrition targets (defaults to row 1)."""
    row = await pool.fetchrow("SELECT calories, protein_g, carbs_g, fat_g FROM nutrition_targets WHERE id = 1")
    if not row:
        return {"calories": 2000, "protein_g": 150, "carbs_g": 200, "fat_g": 70}
    return dict(row)

async def update_nutrition_targets(pool, targets: Dict[str, int]):
    """Updates nutrition targets for row 1."""
    await pool.execute(
        """
        INSERT INTO nutrition_targets (id, calories, protein_g, carbs_g, fat_g)
        VALUES (1, $1, $2, $3, $4)
        ON CONFLICT (id) DO UPDATE SET
            calories = EXCLUDED.calories,
            protein_g = EXCLUDED.protein_g,
            carbs_g = EXCLUDED.carbs_g,
            fat_g = EXCLUDED.fat_g,
            updated_at = NOW()
        """,
        targets.get("calories", 2000),
        targets.get("protein_g", 150),
        targets.get("carbs_g", 200),
        targets.get("fat_g", 70)
    )

async def get_recent_meals(pool, limit: int = 5) -> List[Dict[str, Any]]:
    """Gets most recent meals."""
    rows = await pool.fetch(
        "SELECT id, meal_date, meal_type, total_calories, description FROM meals ORDER BY created_at DESC LIMIT $1",
        limit
    )
    return [dict(r) for r in rows]
