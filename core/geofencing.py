import math
from typing import List
import httpx


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates distance between two coordinates in meters using Haversine formula."""
    R = 6371000  # Radius of the Earth in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
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
                return list(set(shops))  # Unique names
            return []
    except Exception as e:
        print(f"Error finding shops: {e}")
        return []


async def process_geofencing(
    pool, user_id: int, current_lat: float, current_lon: float, application
):
    """Detects transitions for ALL saved locations and shop proximity."""
    from db.queries.profile import get_user_profile, update_user_profile
    from db.queries.locations import list_saved_locations
    from db.queries.shopping import list_shopping_items

    profile = await get_user_profile(pool, user_id)
    if not profile:
        return

    last_loc_name = profile.get("current_location_name")
    saved_locs = await list_saved_locations(pool, user_id)

    # 1. Check all saved locations for Entry/Exit
    found_loc = None
    for loc in saved_locs:
        dist = calculate_distance(
            current_lat, current_lon, float(loc["latitude"]), float(loc["longitude"])
        )
        if dist <= loc["radius_meters"]:
            found_loc = loc
            break

    # EXIT TRANSITION
    if last_loc_name and (not found_loc or found_loc["name"] != last_loc_name):
        print(f"📍 EXIT: User {user_id} left {last_loc_name}")
        await update_user_profile(
            pool,
            user_id,
            current_location_name=None,
            is_at_home=(
                False
                if last_loc_name.lower() in ["acasă", "acasa", "chirie"]
                else profile.get("is_at_home")
            ),
        )

        # Specific Exit logic
        if last_loc_name.lower() in ["acasă", "acasa", "chirie"]:
            msg = f"👋 *Ai plecat de la {last_loc_name}*\\!\n\nSă ai o zi excelentă și nu uita să verifici dacă ai luat tot ce ai nevoie\\! 🚀"
            await application.bot.send_message(
                chat_id=user_id, text=msg, parse_mode="MarkdownV2"
            )
        elif last_loc_name.lower() in ["sală", "sala", "gym"]:
            msg = "💪 *Antrenament terminat?*\n\nNu uita să loghezi progresul în Lora dacă nu ai făcut-o deja\\! 🏋️‍♂️"
            await application.bot.send_message(
                chat_id=user_id, text=msg, parse_mode="MarkdownV2"
            )

    # ENTRY TRANSITION
    if found_loc and found_loc["name"] != last_loc_name:
        loc_name = found_loc["name"]
        print(f"📍 ENTRY: User {user_id} arrived at {loc_name}")
        await update_user_profile(
            pool,
            user_id,
            current_location_name=loc_name,
            is_at_home=(
                True
                if loc_name.lower() in ["acasă", "acasa", "chirie"]
                else profile.get("is_at_home")
            ),
        )

        # Specific Entry logic
        if loc_name.lower() in ["acasă", "acasa", "chirie"]:
            msg = f"🏠 *Bine ai revenit la {loc_name}\\!*\n\nVrei să facem un scurt rezumat al zilei? ☕"
            await application.bot.send_message(
                chat_id=user_id, text=msg, parse_mode="MarkdownV2"
            )
        elif loc_name.lower() in ["sală", "sala", "gym"]:
            msg = "🏋️‍♂️ *Ești la sală\\!* \n\nSpor la treabă\\! Vrei să pornim un cronometru de focus sau să logăm exercițiile? 🔥"
            await application.bot.send_message(
                chat_id=user_id, text=msg, parse_mode="MarkdownV2"
            )
        elif loc_name.lower() in ["facultate", "uni", "universitate"]:
            msg = "🎓 *Ai ajuns la facultate\\!* \n\nNu uita să bifezi prezența la cursuri dacă este cazul\\. Succes\\! 📚"
            await application.bot.send_message(
                chat_id=user_id, text=msg, parse_mode="MarkdownV2"
            )
        else:
            msg = f"📍 *Ai ajuns la {loc_name}\\!*"
            await application.bot.send_message(
                chat_id=user_id, text=msg, parse_mode="MarkdownV2"
            )

    # 2. Handle Shop Proximity (only if NOT at a saved location)
    if not found_loc:
        nearby_shops = await find_nearby_shops(current_lat, current_lon)
        if nearby_shops:
            shopping_items = await list_shopping_items(pool, include_bought=False)
            if shopping_items:
                shop_names = ", ".join(nearby_shops[:2])
                items_str = ", ".join([i["item"] for i in shopping_items[:5]])
                msg = f"🛒 *Ești lângă {shop_names}\\!*\n\nNu uita să iei: *{items_str}*\\. 📝"
                await application.bot.send_message(
                    chat_id=user_id, text=msg, parse_mode="MarkdownV2"
                )

    # 3. Auto-set Home if not set and user is stationary for a long time?
    # (Optional future improvement)
    if not home_lat or not home_lon:
        # If user has been at this location for a while, we could suggest it as Home
        pass
