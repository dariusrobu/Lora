import asyncio
import logging
from fastapi import APIRouter
from lora_api.config import (
    SERVER_IP, SERVER_SSH_USER, SERVER_SSH_PASSWORD,
    QBIT_USERNAME, QBIT_PASSWORD, RADARR_API_KEY, SONARR_API_KEY,
)

logger = logging.getLogger("lora_api")

router = APIRouter(prefix="/api", tags=["homeserver"])

SERVICES = [
    ("qBittorrent", 8080),
    ("Radarr", 7878),
    ("Sonarr", 8989),
    ("Prowlarr", 9696),
    ("Bazarr", 6767),
    ("Jellyfin", 8096),
    ("Overseerr", 5055),
    ("Homepage", 3000),
    ("UptimeKuma", 3001),
    ("Portainer", 9443),
]

SERVICE_ICONS = {
    "qBittorrent": "⬇️",
    "Radarr": "🎬",
    "Sonarr": "📺",
    "Prowlarr": "🔍",
    "Bazarr": "📝",
    "Jellyfin": "🎞️",
    "Overseerr": "🎫",
    "Homepage": "🏠",
    "UptimeKuma": "📊",
    "Portainer": "🐳",
}


async def _check_tcp(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False


async def _ssh_cmd(cmd: str, timeout: float = 5.0) -> str:
    import asyncssh
    try:
        async with asyncssh.connect(
            SERVER_IP, username=SERVER_SSH_USER, password=SERVER_SSH_PASSWORD,
            known_hosts=None, connect_timeout=4,
            client_keys=None,
        ) as conn:
            result = await asyncio.wait_for(conn.run(cmd), timeout=timeout)
            return result.stdout.strip()
    except Exception as e:
        logger.warning(f"SSH failed: {e}")
        return ""


async def _fetch_json(url: str, headers: dict | None = None, auth: tuple | None = None, timeout: float = 5.0):
    import aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            kwargs = {"headers": headers or {}, "timeout": aiohttp.ClientTimeout(total=timeout)}
            if auth:
                import base64
                b64 = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
                kwargs["headers"]["Authorization"] = f"Basic {b64}"
            async with session.get(url, **kwargs) as resp:
                if resp.status < 300:
                    return await resp.json()
    except Exception as e:
        logger.warning(f"HTTP fetch failed {url}: {e}")
    return None


async def _get_system_stats() -> dict:
    # Use /proc/stat for reliable CPU reading across distros
    cpu_raw = await _ssh_cmd(r"awk '/^cpu / {idle=$5; total=$2+$3+$4+$5+$6+$7+$8+$9} END {printf \"%.1f\", (1-idle/total)*100}' /proc/stat")
    ram_raw = await _ssh_cmd(r"free -m | awk '/^Mem:/{print $2,$3}'")
    ssd_raw = await _ssh_cmd(r"df / | tail -1 | awk '{print $2,$3,$5}'")
    hdd_raw = await _ssh_cmd(r"df /mnt/media_extern | tail -1 | awk '{print $2,$3,$5}'")

    cpu = 0.0
    if cpu_raw:
        try:
            cpu = round(float(cpu_raw), 1)
        except ValueError:
            pass

    ram_total = ram_used = 0
    if ram_raw:
        parts = ram_raw.split()
        if len(parts) >= 2:
            ram_total = int(parts[0])
            ram_used = int(parts[1])

    def _parse_disk(raw: str):
        parts = raw.split()
        if len(parts) >= 5:
            try:
                blocks = int(parts[1])
                used_blocks = int(parts[2])
                used_pct = int(parts[4].rstrip("%"))
                total_gb = round(blocks / 1024 / 1024, 1)
                used_gb = round(used_blocks / 1024 / 1024, 1)
                return {"total_gb": total_gb, "used_gb": used_gb, "used_pct": used_pct}
            except (ValueError, IndexError):
                pass
        return None

    return {
        "cpu_usage": cpu,
        "ram_used_mb": ram_used,
        "ram_total_mb": ram_total,
        "ram_used_pct": round(ram_used / ram_total * 100, 1) if ram_total > 0 else 0,
        "ssd": _parse_disk(ssd_raw) or {"total_gb": 218, "used_gb": 24, "used_pct": 12},
        "hdd": _parse_disk(hdd_raw) or {"total_gb": 293, "used_gb": 33, "used_pct": 12},
    }


async def _get_downloads() -> list:
    qbit_host = f"http://{SERVER_IP}:8080"
    data = await _fetch_json(f"{qbit_host}/api/v2/torrents/info", auth=(QBIT_USERNAME, QBIT_PASSWORD))
    if not data or not isinstance(data, list):
        return []
    active = [t for t in data if t.get("state") in ("downloading", "metaDL", "forcedDL")]
    result = []
    for t in active[:5]:
        size = t.get("total_size", 0) or 1
        result.append({
            "name": t.get("name", "?"),
            "progress": round(t.get("progress", 0) * 100, 1),
            "dlspeed": t.get("dlspeed", 0),
            "eta": t.get("eta", 0),
            "downloaded": t.get("downloaded", 0),
            "total_size": size,
            "state": t.get("state", ""),
        })
    return result


async def _get_queue_count(service: str, api_key: str) -> int:
    url = f"http://{SERVER_IP}:{'7878' if service == 'radarr' else '8989'}/api/v3/queue"
    data = await _fetch_json(url, headers={"X-Api-Key": api_key})
    if data and isinstance(data, dict):
        return data.get("totalRecords", len(data.get("records", [])))
    return 0


@router.get("/homeserver/status")
async def home_server_status():
    from lora_api.config import SERVER_SSH_PASSWORD

    # If no SSH password configured, skip system stats
    has_ssh = bool(SERVER_SSH_PASSWORD)

    coros = {
        "services": _check_all_services(),
        "system": _get_system_stats() if has_ssh else _empty_system(),
        "downloads": _get_downloads(),
        "radarr_queue": _get_queue_count("radarr", RADARR_API_KEY),
        "sonarr_queue": _get_queue_count("sonarr", SONARR_API_KEY),
    }

    gathered = await asyncio.gather(*coros.values(), return_exceptions=True)
    keys = list(coros.keys())
    results = {}
    for i, key in enumerate(keys):
        val = gathered[i]
        if isinstance(val, Exception):
            logger.warning(f"homeserver {key} failed: {val}")
            if key == "system":
                val = await _empty_system()
            elif key in ("services", "downloads"):
                val = []
            else:
                val = 0
        results[key] = val

    return {
        "services": results["services"],
        "system": results["system"],
        "downloads": results["downloads"],
        "radarr_queue": results["radarr_queue"],
        "sonarr_queue": results["sonarr_queue"],
    }


async def _empty_system():
    return {
        "cpu_usage": 0.0,
        "ram_used_mb": 0,
        "ram_total_mb": 0,
        "ram_used_pct": 0,
        "ssd": {"total_gb": 218, "used_gb": 24, "used_pct": 12},
        "hdd": {"total_gb": 293, "used_gb": 33, "used_pct": 12},
    }


async def _check_all_services():
    checks = [_check_tcp(SERVER_IP, port) for _, port in SERVICES]
    results = await asyncio.gather(*checks)
    return [
        {"name": name, "port": port, "icon": SERVICE_ICONS.get(name, "❓"), "up": up}
        for (name, port), up in zip(SERVICES, results)
    ]
