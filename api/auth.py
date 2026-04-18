from aiohttp import web
from core.config import LORA_API_SECRET


def require_auth(func):
    async def wrapper(request):
        secret = request.headers.get("X-Internal-Secret")
        if not secret or secret != LORA_API_SECRET:
            return web.json_response({"error": "Unauthorized"}, status=401)
        return await func(request)

    return wrapper
