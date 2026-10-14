"""CLI read-only pentru Lora Dev."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from lora_dev.provider import generate_dev_plan
from lora_dev.read_only import collect_context


async def _run(request: str, root: Path, log_path: Path | None) -> int:
    context = collect_context(root, request, log_path)
    print("Context colectat read-only. Generez planul…\n")
    try:
        plan = await generate_dev_plan(context)
    except Exception as exc:
        print(f"Nu am putut genera planul: {type(exc).__name__}: {exc}")
        return 1
    print(plan.strip() or "Modelul nu a returnat un plan.")
    print("\nNicio modificare nu a fost aplicată.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Lora Dev — analiză read-only și plan tehnic")
    parser.add_argument("request", nargs="+", help="Problema sau funcționalitatea de analizat")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Rădăcina repository-ului")
    parser.add_argument("--log", type=Path, default=None, help="Fișier log opțional")
    args = parser.parse_args()
    log_path = args.log or (args.root / "logs" / "bot.log")
    return asyncio.run(_run(" ".join(args.request), args.root.resolve(), log_path))


if __name__ == "__main__":
    raise SystemExit(main())
