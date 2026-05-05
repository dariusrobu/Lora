import httpx
from typing import List, Dict, Any

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


async def get_nearby_places(
    lat: float, lon: float, radius: int = 500, category: str = "shop"
) -> List[Dict[str, Any]]:
    """
    Fetches nearby places from OpenStreetMap using Overpass API.
    Categories: shop, amenity, leisure, etc.
    """
    # Overpass QL query
    # [out:json];node(around:radius, lat, lon)[category];out;
    query = f"""
    [out:json];
    (
      node(around:{radius}, {lat}, {lon})["shop"];
      node(around:{radius}, {lat}, {lon})["amenity"~"pharmacy|bank|atm|cafe|restaurant|hospital"];
    );
    out body;
    """

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                OVERPASS_URL, data={"data": query}, timeout=15.0
            )
            if response.status_code == 200:
                data = response.json()
                elements = data.get("elements", [])

                results = []
                for el in elements:
                    tags = el.get("tags", {})
                    results.append(
                        {
                            "id": el.get("id"),
                            "name": tags.get("name")
                            or tags.get("brand")
                            or "Locație necunoscută",
                            "type": tags.get("shop") or tags.get("amenity"),
                            "lat": el.get("lat"),
                            "lon": el.get("lon"),
                            "address": tags.get("addr:street", "")
                            + " "
                            + tags.get("addr:housenumber", ""),
                        }
                    )
                return results
            else:
                print(f"Overpass API error: {response.status_code}")
                return []
    except Exception as e:
        print(f"Overpass exception: {e}")
        return []


async def is_near_shop(
    lat: float, lon: float, shop_name: str, radius: int = 300
) -> bool:
    """Checks if a specific shop/brand is nearby."""
    places = await get_nearby_places(lat, lon, radius)
    shop_name_lower = shop_name.lower()
    for p in places:
        if shop_name_lower in p["name"].lower():
            return True
    return False
