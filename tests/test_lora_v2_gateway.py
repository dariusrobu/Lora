"""The gradual cutover must not redirect legacy traffic to v2."""

from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from lora_v2.gateway import create_gateway


@pytest.mark.asyncio
async def test_gateway_routes_only_v2_paths(tmp_path: Path) -> None:
    async def legacy_handler(request: web.Request) -> web.Response:
        return web.Response(text=f"legacy:{request.path_qs}")

    async def v2_handler(request: web.Request) -> web.Response:
        if request.path == "/api/v2/captures/photo":
            return web.Response(text=f"v2-photo:{len(await request.read())}")
        return web.Response(text=f"v2:{request.path_qs}")

    legacy_app = web.Application()
    legacy_app.router.add_route("*", "/{tail:.*}", legacy_handler)
    v2_app = web.Application(client_max_size=10 * 1024 * 1024)
    v2_app.router.add_route("*", "/{tail:.*}", v2_handler)
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "v2-hash.js").write_text("", encoding="utf-8")

    async with TestServer(legacy_app) as legacy, TestServer(v2_app) as v2:
        gateway = create_gateway(str(legacy.make_url("/")), str(v2.make_url("/")), assets)
        async with TestClient(TestServer(gateway)) as client:
            expected = {
                "/": "legacy:/",
                "/api/tasks": "legacy:/api/tasks",
                "/assets/legacy-hash.js": "legacy:/assets/legacy-hash.js",
                "/v2": "v2:/",
                "/v2/calendar?month=10": "v2:/calendar?month=10",
                "/api/v2/today": "v2:/api/v2/today",
                "/assets/v2-hash.js": "v2:/assets/v2-hash.js",
            }
            for path, result in expected.items():
                async with client.get(path) as response:
                    assert response.status == 200
                    assert await response.text() == result
            photo = b"a" * (2 * 1024 * 1024)
            async with client.post("/api/v2/captures/photo", data=photo) as response:
                assert response.status == 200
                assert await response.text() == f"v2-photo:{len(photo)}"


@pytest.mark.asyncio
async def test_full_cutover_routes_root_and_rejects_legacy_writes(tmp_path: Path) -> None:
    async def handler(request: web.Request) -> web.Response:
        return web.Response(text='v2:' + request.path)
    app = web.Application()
    app.router.add_route('*', '/{tail:.*}', handler)
    async with TestServer(app) as v2:
        gateway = create_gateway('http://127.0.0.1:1', str(v2.make_url('/')), tmp_path, full_v2=True)
        async with TestClient(TestServer(gateway)) as client:
            for path in ('/', '/v2'):
                response = await client.get(path)
                assert response.status == 200
                assert await response.text() == 'v2:/'
            response = await client.post('/api/tasks', json={'title': 'Must not write legacy'})
            assert response.status == 410
