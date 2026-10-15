"""Local path router for a gradual Mini App cutover."""

import os
from pathlib import Path

from aiohttp import ClientSession, ClientTimeout, web


HOP_HEADERS = frozenset(
    {"connection", "content-length", "host", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers", "transfer-encoding", "upgrade"}
)
PROXY_SESSION: web.AppKey[ClientSession] = web.AppKey("proxy_session", ClientSession)


def create_gateway(
    legacy_url: str = "http://127.0.0.1:8083",
    v2_url: str = "http://127.0.0.1:8092",
    v2_assets: Path | None = None,
) -> web.Application:
    assets = v2_assets or Path(__file__).resolve().parent / "web" / "dist" / "assets"

    async def session_context(app: web.Application):
        app[PROXY_SESSION] = ClientSession(timeout=ClientTimeout(total=60))
        yield
        await app[PROXY_SESSION].close()

    async def route(request: web.Request) -> web.Response:
        path = request.path
        is_v2_page = path == "/v2" or path.startswith("/v2/")
        is_v2_api = path == "/api/v2" or path.startswith("/api/v2/")
        is_v2_asset = (
            path.startswith("/assets/")
            and "/" not in path[len("/assets/"):]
            and (assets / path[len("/assets/"):]).is_file()
        )
        use_v2 = is_v2_page or is_v2_api or is_v2_asset
        upstream_path = path[3:] or "/" if is_v2_page else path
        target = (v2_url if use_v2 else legacy_url).rstrip("/") + upstream_path
        if request.query_string:
            target += "?" + request.query_string

        headers = {key: value for key, value in request.headers.items() if key.lower() not in HOP_HEADERS}
        body = await request.read()
        try:
            async with request.app[PROXY_SESSION].request(
                request.method, target, headers=headers, data=body, allow_redirects=False
            ) as response:
                response_headers = {
                    key: value for key, value in response.headers.items()
                    if key.lower() not in HOP_HEADERS and key.lower() != "content-encoding"
                }
                return web.Response(status=response.status, body=await response.read(), headers=response_headers)
        except Exception:
            return web.json_response({"error": "Serviciul local nu răspunde."}, status=502)

    app = web.Application(client_max_size=10 * 1024 * 1024)
    app.cleanup_ctx.append(session_context)
    app.router.add_route("*", "/{tail:.*}", route)
    return app


def main() -> None:
    port = int(os.getenv("LORA_V2_GATEWAY_PORT", "8093"))
    web.run_app(create_gateway(), host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
