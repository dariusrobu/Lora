import asyncio
import os
from db.connection import get_pool
from modules.travel import handle_travel_intent


async def test_travel():
    pool = await get_pool()

    print("--- Testing travel_add ---")
    res, _ = await handle_travel_intent(
        pool, "travel_add", {"items": "laptop, haine, apa", "list_name": "Cluj"}
    )
    print(f"Reply: {res}")

    print("\n--- Testing travel_list ---")
    res, _ = await handle_travel_intent(pool, "travel_list", {"list_name": "Cluj"})
    print(f"Reply:\n{res}")

    print("\n--- Testing travel_packed ---")
    res, _ = await handle_travel_intent(
        pool, "travel_packed", {"item": "laptop", "list_name": "Cluj"}
    )
    print(f"Reply: {res}")

    print("\n--- Testing travel_check (Leaving) ---")
    res, _ = await handle_travel_intent(
        pool, "travel_check", {"list_name": "Cluj", "trip_type": "departure"}
    )
    print(f"Reply:\n{res}")

    print("\n--- Cleaning up ---")
    res, _ = await handle_travel_intent(
        pool, "travel_clear", {"list_name": "Cluj", "reset_only": False}
    )
    print(f"Reply: {res}")


if __name__ == "__main__":
    # Ensure DATABASE_URL is set for the script
    if "DATABASE_URL" not in os.environ:
        os.environ["DATABASE_URL"] = "postgresql://localhost/lora"
    asyncio.run(test_travel())
