import asyncio
import os
import platform
import re
import subprocess
import time
import uuid
from typing import Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from lora_api.auth import get_current_user
from lora_api.database import get_pool
from lora_api.config import TELEGRAM_USER_ID

router = APIRouter(prefix="/api/llm", tags=["llm"])

KNOWN_MODELS: Dict[str, dict] = {
    "llama3.2:1b": {"size_gb": 0.8, "ram_min_gb": 4, "vram_min_gb": 0, "use_case": "Rapid, bazice", "description": "Meta Llama 3.2 1B"},
    "llama3.2:3b": {"size_gb": 2.0, "ram_min_gb": 8, "vram_min_gb": 0, "use_case": "Default, general", "description": "Meta Llama 3.2 3B"},
    "llama3.1:8b": {"size_gb": 4.7, "ram_min_gb": 16, "vram_min_gb": 8, "use_case": "General, echilibrat", "description": "Meta Llama 3.1 8B"},
    "llama3.1:70b": {"size_gb": 40, "ram_min_gb": 64, "vram_min_gb": 48, "use_case": "Avansat", "description": "Meta Llama 3.1 70B"},
    "mistral:7b": {"size_gb": 4.1, "ram_min_gb": 16, "vram_min_gb": 8, "use_case": "General, rapid", "description": "Mistral 7B"},
    "mixtral:8x7b": {"size_gb": 26, "ram_min_gb": 48, "vram_min_gb": 32, "use_case": "Avansat MoE", "description": "Mixtral 8x7B"},
    "qwen2.5:3b": {"size_gb": 1.9, "ram_min_gb": 8, "vram_min_gb": 0, "use_case": "Multilingv u\u0219or", "description": "Qwen 2.5 3B"},
    "qwen2.5:7b": {"size_gb": 4.3, "ram_min_gb": 16, "vram_min_gb": 8, "use_case": "Multilingv", "description": "Qwen 2.5 7B"},
    "qwen2.5:14b": {"size_gb": 8.5, "ram_min_gb": 24, "vram_min_gb": 16, "use_case": "Multilingv avansat", "description": "Qwen 2.5 14B"},
    "qwen2.5:72b": {"size_gb": 41, "ram_min_gb": 64, "vram_min_gb": 48, "use_case": "Multilingv expert", "description": "Qwen 2.5 72B"},
    "phi3:3.8b": {"size_gb": 2.3, "ram_min_gb": 8, "vram_min_gb": 0, "use_case": "Cod, reasoning", "description": "Phi-3 3.8B Mini"},
    "phi3:14b": {"size_gb": 7.8, "ram_min_gb": 24, "vram_min_gb": 16, "use_case": "Cod avansat", "description": "Phi-3 14B Medium"},
    "deepseek-r1:7b": {"size_gb": 4.5, "ram_min_gb": 16, "vram_min_gb": 8, "use_case": "Reasoning", "description": "DeepSeek R1 7B"},
    "deepseek-r1:14b": {"size_gb": 9.0, "ram_min_gb": 24, "vram_min_gb": 16, "use_case": "Reasoning avansat", "description": "DeepSeek R1 14B"},
    "deepseek-r1:32b": {"size_gb": 20, "ram_min_gb": 48, "vram_min_gb": 24, "use_case": "Reasoning expert", "description": "DeepSeek R1 32B"},
    "gemma2:2b": {"size_gb": 1.5, "ram_min_gb": 6, "vram_min_gb": 0, "use_case": "Rapid, u\u0219or", "description": "Google Gemma 2 2B"},
    "gemma2:9b": {"size_gb": 5.3, "ram_min_gb": 16, "vram_min_gb": 8, "use_case": "General", "description": "Google Gemma 2 9B"},
    "codegemma:2b": {"size_gb": 1.4, "ram_min_gb": 6, "vram_min_gb": 0, "use_case": "Cod u\u0219or", "description": "CodeGemma 2B"},
    "codellama:7b": {"size_gb": 3.8, "ram_min_gb": 16, "vram_min_gb": 8, "use_case": "Cod", "description": "Code Llama 7B"},
    "codellama:34b": {"size_gb": 19, "ram_min_gb": 48, "vram_min_gb": 24, "use_case": "Cod avansat", "description": "Code Llama 34B"},
    "llava:7b": {"size_gb": 4.5, "ram_min_gb": 16, "vram_min_gb": 8, "use_case": "Vision", "description": "LLaVA 7B"},
    "llava:13b": {"size_gb": 7.9, "ram_min_gb": 24, "vram_min_gb": 16, "use_case": "Vision avansat", "description": "LLaVA 13B"},
    "nomic-embed-text:v1.5": {"size_gb": 0.3, "ram_min_gb": 2, "vram_min_gb": 0, "use_case": "Embeddings", "description": "Nomic Embed Text v1.5"},
    "mxbai-embed-large:v1": {"size_gb": 0.7, "ram_min_gb": 4, "vram_min_gb": 0, "use_case": "Embeddings", "description": "mxbai Embed Large v1"},
    "llama3.2-vision:11b": {"size_gb": 7.1, "ram_min_gb": 24, "vram_min_gb": 16, "use_case": "Vision", "description": "Llama 3.2 Vision 11B"},
    "llama3.2-vision:90b": {"size_gb": 55, "ram_min_gb": 96, "vram_min_gb": 64, "use_case": "Vision expert", "description": "Llama 3.2 Vision 90B"},
}

TIER_ORDER = {"recommended": 0, "ok": 1, "minimum": 2, "insufficient": 3}


def _get_ram_gb() -> float:
    try:
        if platform.system() == "Darwin":
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], timeout=5).decode().strip()
            return round(int(out) / (1024 ** 3), 1)
        elif platform.system() == "Linux":
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        return round(int(line.split()[1]) / 1024 / 1024, 1)
    except Exception:
        pass
    return 0


def _get_vram_gb() -> float:
    # Apple Silicon: unified memory — GPU shares system RAM
    if platform.system() == "Darwin":
        try:
            machine = subprocess.check_output(["sysctl", "-n", "hw.machine"], timeout=5).decode().strip()
            if machine == "arm64":
                ram_gb = _get_ram_gb()
                if ram_gb > 0:
                    return round(ram_gb * 0.75, 1)
        except Exception:
            pass
    try:
        out = subprocess.check_output(
            ["system_profiler", "SPDisplaysDataType"],
            timeout=5, stderr=subprocess.DEVNULL,
        ).decode()
        m = re.search(r'VRAM.*?:\s*(\d+(?:\.\d+)?)\s*(GB|MB)', out)
        if m:
            val = float(m.group(1))
            if m.group(2) == "MB":
                val /= 1024
            return round(val, 1)
    except Exception:
        pass
    return 0


def _compute_tier(ram_gb: float, ram_min: float, vram_gb: float, vram_min: float) -> tuple:
    if ram_gb <= 0:
        return ("insufficient", False)
    if ram_gb >= ram_min * 2.5:
        tier = "recommended"
    elif ram_gb >= ram_min * 1.5:
        tier = "ok"
    elif ram_gb >= ram_min * 1.1:
        tier = "minimum"
    else:
        tier = "insufficient"

    gpu_ready = False
    if vram_min > 0 and vram_gb >= vram_min:
        gpu_ready = True
        if tier == "minimum":
            tier = "ok"
        elif tier == "insufficient":
            tier = "minimum"

    return (tier, gpu_ready)


_pull_tasks: Dict[str, dict] = {}


@router.get("/system-specs")
async def get_system_specs(user=Depends(get_current_user)):
    ram_gb = _get_ram_gb()
    vram_gb = _get_vram_gb()
    cpu_cores = os.cpu_count() or 0
    return {"total_ram_gb": ram_gb, "total_vram_gb": vram_gb, "cpu_cores": cpu_cores}


@router.get("/models")
async def get_models(
    ram_gb: float = Query(0, description="RAM in GB for tier computation"),
    vram_gb: float = Query(0, description="VRAM in GB for GPU readiness"),
    user=Depends(get_current_user),
):
    import db.queries.profile as q

    pool = await get_pool()
    profile = await q.get_user_profile(pool, TELEGRAM_USER_ID)
    host = (profile or {}).get("llm_host", "http://localhost:11434")
    current_model = (profile or {}).get("llm_model", "")

    installed = set()
    unknown_installed = []
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{host.rstrip('/')}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                for m in data.get("models", []):
                    name = m.get("name", "")
                    known = False
                    for kn in KNOWN_MODELS:
                        if name.startswith(kn):
                            installed.add(kn)
                            known = True
                            break
                    if not known:
                        size_gb = round(m.get("size", 0) / (1024 ** 3), 2)
                        unknown_installed.append({
                            "name": name,
                            "size_gb": size_gb,
                            "ram_min_gb": round(size_gb * 1.5, 1),
                            "vram_min_gb": round(size_gb * 0.8, 1),
                            "use_case": "Necunoscut",
                            "description": "Instalat, necunoscut în catalog",
                            "installed": True,
                            "from_ollama_only": True,
                        })
    except Exception:
        pass

    result = []
    for name, info in KNOWN_MODELS.items():
        entry = {
            "name": name,
            "size_gb": info["size_gb"],
            "ram_min_gb": info["ram_min_gb"],
            "vram_min_gb": info["vram_min_gb"],
            "use_case": info["use_case"],
            "description": info["description"],
            "installed": name in installed,
            "from_ollama_only": False,
            "current": name == current_model,
        }
        if ram_gb > 0:
            tier, gpu_ready = _compute_tier(ram_gb, info["ram_min_gb"], vram_gb, info["vram_min_gb"])
            entry["tier"] = tier
            entry["gpu_ready"] = gpu_ready
        result.append(entry)

    for uk in unknown_installed:
        if ram_gb > 0:
            tier, gpu_ready = _compute_tier(ram_gb, uk["ram_min_gb"], vram_gb, uk["vram_min_gb"])
            uk["tier"] = tier
            uk["gpu_ready"] = gpu_ready
        uk["current"] = uk["name"] == current_model
        result.append(uk)

    result.sort(key=lambda x: (TIER_ORDER.get(x.get("tier", "insufficient"), 3), x["name"]))

    return {"models": result, "host": host}


class PullRequest(BaseModel):
    model: str
    host: Optional[str] = None


@router.post("/pull")
async def pull_model(body: PullRequest, user=Depends(get_current_user)):
    task_id = str(uuid.uuid4())
    host = body.host or "http://localhost:11434"

    async def _run_pull(tid: str, model: str):
        try:
            proc = await asyncio.create_subprocess_exec(
                "ollama", "pull", model,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            output_lines = []
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                text = line.decode(errors="replace").rstrip("\n\r")
                output_lines.append(text)
                _pull_tasks[tid] = {"status": "running", "output": "\n".join(output_lines[-20:]), "model": model}
            await proc.wait()
            full = "\n".join(output_lines)
            if proc.returncode == 0:
                _pull_tasks[tid] = {"status": "completed", "output": full, "model": model}
            else:
                _pull_tasks[tid] = {"status": "failed", "output": full, "model": model, "error": f"Exit code {proc.returncode}"}
        except FileNotFoundError:
            _pull_tasks[tid] = {"status": "failed", "output": "Comanda `ollama` nu a fost găsită. Instalează Ollama mai întâi.", "model": model, "error": "ollama not found"}
        except Exception as e:
            _pull_tasks[tid] = {"status": "failed", "output": str(e), "model": model, "error": str(e)}

    _pull_tasks[task_id] = {"status": "starting", "output": "", "model": body.model}
    asyncio.create_task(_run_pull(task_id, body.model))
    return {"task_id": task_id}


@router.get("/pull/{task_id}")
async def get_pull_status(task_id: str, user=Depends(get_current_user)):
    task = _pull_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task_id": task_id, **task}


@router.get("/status")
async def get_ollama_status(user=Depends(get_current_user)):
    import db.queries.profile as q
    pool = await get_pool()
    profile = await q.get_user_profile(pool, TELEGRAM_USER_ID)
    host = (profile or {}).get("llm_host", "http://localhost:11434")

    running = False
    version = ""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(f"{host.rstrip('/')}/api/tags")
            if resp.status_code == 200:
                running = True
    except Exception:
        pass

    try:
        ver = subprocess.check_output(["ollama", "--version"], timeout=5, stderr=subprocess.DEVNULL).decode().strip()
        version = ver
    except Exception:
        version = ""

    autostart = False
    autostart_available = False
    if platform.system() == "Darwin":
        plist_path = os.path.expanduser("~/Library/LaunchAgents/com.ollama.ollama.plist")
        autostart_available = os.path.exists(plist_path)
        try:
            proc = await asyncio.create_subprocess_exec(
                "launchctl", "list", "com.ollama.ollama",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            autostart = proc.returncode == 0
        except Exception:
            pass

    ollama_installed = bool(version) or running
    return {
        "running": running,
        "version": version,
        "autostart": autostart,
        "autostart_available": autostart_available,
        "ollama_installed": ollama_installed,
    }


@router.post("/serve/start")
async def start_ollama(user=Depends(get_current_user)):
    if platform.system() == "Darwin":
        try:
            proc = await asyncio.create_subprocess_exec(
                "open", "-a", "Ollama",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            return {"ok": True, "message": "Ollama app pornită. Serverul pornește în câteva secunde."}
        except FileNotFoundError:
            pass

    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return {"ok": True, "message": "Ollama server pornit în fundal."}
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Ollama nu este instalat. Instalează de la https://ollama.com")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/serve/stop")
async def stop_ollama(user=Depends(get_current_user)):
    try:
        proc = await asyncio.create_subprocess_exec(
            "pkill", "-f", "ollama",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        return {"ok": True, "message": "Procesele Ollama au fost oprite."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class AutostartRequest(BaseModel):
    enabled: bool


@router.post("/serve/autostart")
async def toggle_autostart(body: AutostartRequest, user=Depends(get_current_user)):
    if platform.system() != "Darwin":
        raise HTTPException(status_code=400, detail="Auto-start este suportat doar pe macOS")

    plist_path = os.path.expanduser("~/Library/LaunchAgents/com.ollama.ollama.plist")
    if not os.path.exists(plist_path):
        raise HTTPException(status_code=400, detail="Plist-ul Ollama nu există. Reinstalează Ollama.")

    try:
        cmd = ["launchctl", "load" if body.enabled else "unload", "-w", plist_path]
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        await proc.wait()
        return {"ok": True, "enabled": body.enabled}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
