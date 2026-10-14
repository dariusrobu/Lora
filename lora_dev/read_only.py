"""Analiză read-only pentru Lora Dev.

Acest modul nu scrie fișiere și nu execută comenzi shell arbitrare. Colectează
doar context minim pentru a genera un plan tehnic verificabil.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DevContext:
    request: str
    git_status: str
    recent_log: str
    relevant_files: tuple[str, ...]
    recent_errors: str
    file_excerpts: str = ""


def _safe_git(root: Path, *args: str) -> str:
    """Rulează doar subcomenzi Git read-only și limitează rezultatul."""
    allowed = {"status", "log", "diff"}
    if not args or args[0] not in allowed:
        return ""
    result = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, timeout=10, check=False
    )
    return (result.stdout or result.stderr)[:12000]


def collect_context(root: Path, request: str, log_path: Path | None = None) -> DevContext:
    """Colectează context fără să modifice repository-ul sau logurile."""
    patterns = ("*.py", "*.tsx", "*.ts", "*.sql")
    files: list[str] = []
    for pattern in patterns:
        files.extend(str(path.relative_to(root)) for path in root.glob(pattern))
        files.extend(
            str(path.relative_to(root))
            for path in root.glob(f"**/{pattern}")
            if not any(part in {".git", ".venv", ".gemini", "node_modules", "dist"} for part in path.parts)
        )
    unique_files = tuple(sorted(set(files))[:300])
    excerpts: list[str] = []
    preferred = (
        "lora_api/routers/finance.py",
        "lora_api/schemas.py",
        "db/queries/finance.py",
        "dashboard/src/pages/Finance.tsx",
        "dashboard/src/api/queries/finance.ts",
    )
    for relative in preferred:
        path = root / relative
        if path.is_file():
            excerpts.append(f"FILE: {relative}\n{path.read_text(errors='replace')[:3000]}")
    keywords = tuple(word.lower() for word in request.split() if len(word) > 3)
    for relative in unique_files:
        if keywords and not any(word in relative.lower() for word in keywords):
            continue
        path = root / relative
        if path.is_file() and path.stat().st_size < 200_000:
            excerpts.append(f"FILE: {relative}\n{path.read_text(errors='replace')[:2500]}")
        if len(excerpts) >= 8:
            break
    if len(excerpts) < 3:
        for relative in unique_files:
            if any(token in relative.lower() for token in ("finance", "router", "api")):
                path = root / relative
                if path.is_file() and path.stat().st_size < 200_000:
                    excerpts.append(f"FILE: {relative}\n{path.read_text(errors='replace')[:2500]}")
                if len(excerpts) >= 8:
                    break
    errors = ""
    if log_path and log_path.exists():
        lines = log_path.read_text(errors="replace").splitlines()
        matches = [line for line in lines[-5000:] if any(word in line.lower() for word in ("error", "exception", "traceback", "failed"))]
        errors = "\n".join(matches[-40:])[:5000]
    return DevContext(request.strip(), _safe_git(root, "status", "--short"), _safe_git(root, "log", "-5", "--oneline"), unique_files, errors, "\n\n".join(excerpts))


def render_plan_input(context: DevContext) -> str:
    """Construiește input determinist pentru modelul care va genera planul."""
    files = "\n".join(f"- {item}" for item in context.relevant_files)
    return f"REQUEST:\n{context.request}\n\nGIT STATUS:\n{context.git_status[:3000]}\n\nRECENT COMMITS:\n{context.recent_log[:2000]}\n\nRECENT ERRORS:\n{context.recent_errors}\n\nREPOSITORY FILES:\n{files}\n\nSOURCE EXCERPTS:\n{context.file_excerpts[:16000]}\n"
