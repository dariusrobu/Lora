import math
from typing import Optional, Dict, Any, List
import httpx
from bot.formatter import escape_md

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates distance between two coordinates in meters using Haversine formula."""
    R = 6371000  # Radius of the Earth in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

async def find_nearby_shops(lat: float, lon: float, radius: int = 300) -> List[str]:
    """Finds nearby supermarkets/shops using Overpass API."""
    # Overpass QL query for shops within radius
    query = f"""
    [out:json][timeout:25];
    (
      node["shop"~"supermarket|convenience|bakery"](around:{radius},{lat},{lon});
      way["shop"~"supermarket|convenience|bakery"](around:{radius},{lat},{lon});
    );
    out body;
    """
    url = "https://overpass-api.de/api/interpreter"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data={"data": query}, timeout=10.0)
            if response.status_code == 200:
                elements = response.json().get("elements", [])
                shops = [e.get("tags", {}).get("name", "Un magazin") for e in elements]
                return list(set(shops)) # Unique names
            return []
    except Exception as e:
        print(f"Error finding shops: {e}")
        return []

async def process_geofencing(pool, user_id: int, current_lat: float, current_lon: float, application):
    """Detects home transitions and shop proximity."""
    from db.queries.profile import get_user_profile, update_user_profile
    from db.queries.shopping import list_items
    from scheduler.jobs import send_morning_briefing
    
    profile = await get_user_profile(pool, user_id)
    if not profile:
        return

    home_lat = profile.get("home_latitude")
    home_lon = profile.get("home_longitude")
    was_at_home = profile.get("is_at_home", True)
    
    # 1. Handle Home Transitions
    if home_lat and home_lon:
        dist_from_home = calculate_distance(current_lat, current_lon, float(home_lat), float(home_lon))
        
        # LEAVING HOME (Transition from <200m to >200m)
        if was_at_home and dist_from_home > 200:
            await update_user_profile(pool, user_id, is_at_home=False)
            print(f"🏠 TRANSITION: User {user_id} left home.")
            
            # Send 'Leaving Home' nudge
            msg = "👋 *Ai plecat de acasă?*\n\nNu uita să verifici dacă ai stins luminile și ai luat tot ce ai nevoie! Drum bun! 🚗✨"
            await application.bot.send_message(chat_id=user_id, text=msg, parse_mode="MarkdownV2")
            
            # Optionally trigger a quick summary
            # await send_morning_briefing(application, pool, force=True)

        # COMING HOME (Transition from >500m to <200m)
        elif not was_at_home and dist_from_home < 200:
            await update_user_profile(pool, user_id, is_at_home=True)
            print(f"🏠 TRANSITION: User {user_id} arrived home.")
            
            msg = "🏠 *Bine ai revenit acasă\\!*\n\nSper că ai avut o zi productivă\\. Vrei să facem un scurt rezumat al progresului tău de azi? ☕"
            await application.bot.send_message(chat_id=user_id, text=msg, parse_mode="MarkdownV2")

    # 2. Handle Shop Proximity
    # We only check for shops if user is NOT at home and moving
    if not was_at_home:
        nearby_shops = await find_nearby_shops(current_lat, current_lon)
        if nearby_shops:
            # Check shopping list
            from db.queries.shopping import list_shopping_items
            shopping_items = await list_shopping_items(pool, include_bought=False)
            
            if shopping_items:
                shop_names = ", ".join(nearby_shops[:2])
                items_str = ", ".join([i["item"] for i in shopping_items[:5]])
                msg = f"🛒 *Ești lângă {shop_names}\\!*\n\nNu uita să iei: *{items_str}*\\. 📝"
                
                # Check if we already nudged recently for shopping (to avoid spam)
                # For simplicity, we just print for now, or we could add a cooldown
                await application.bot.send_message(chat_id=user_id, text=msg, parse_mode="MarkdownV2")
                print(f"🛒 SHOP NUDGE sent for: {shop_names}")

    # 3. Auto-set Home if not set and user is stationary for a long time?
    # (Optional future improvement)
    if not home_lat or not home_lon:
        # If user has been at this location for a while, we could suggest it as Home
        pass
