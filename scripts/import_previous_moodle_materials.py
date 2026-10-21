"""Copy older university attachments out of the Obsidian vault without altering it."""

from __future__ import annotations

import argparse
import asyncio
import uuid
from pathlib import Path

from lora_v2.config import Settings
from lora_v2.db import create_pool, migrate
from lora_v2.moodle_library import _digest, _safe_name, icloud_root


OLD_ROOT = Path.home() / "Library/Mobile Documents/iCloud~md~obsidian/Documents/Lora/05 University"


async def import_materials(*, apply: bool, old_root: Path = OLD_ROOT,
                           new_root: Path | None = None) -> dict[str, int]:
    settings = Settings.from_env()
    destination = new_root or icloud_root()
    pool = await create_pool(settings)
    copied = skipped = unindexed = 0
    try:
        await migrate(pool)
        courses = await pool.fetch(
            "SELECT course_url,folder_name FROM moodle_course_sync WHERE owner_id=$1",
            settings.telegram_user_id,
        )
        by_folder = {row["folder_name"].casefold(): row["course_url"] for row in courses}
        for source in sorted(old_root.rglob("*")):
            if not source.is_file() or source.is_symlink() or source.suffix.lower() == ".md" or source.name == ".DS_Store":
                continue
            relative = source.relative_to(old_root)
            if len(relative.parts) < 2:
                skipped += 1
                continue
            folder = _safe_name(relative.parts[0], "Materie")
            course_url = by_folder.get(folder.casefold())
            if not course_url:
                skipped += 1
                continue
            digest = _digest(source)
            existing = await pool.fetchval(
                "SELECT 1 FROM moodle_materials WHERE owner_id=$1 AND course_url=$2 AND sha256=$3 LIMIT 1",
                settings.telegram_user_id, course_url, digest,
            )
            if existing:
                skipped += 1
                continue
            parts = [_safe_name(part, "Material") for part in relative.parts[1:]]
            target = destination / folder / "Materiale păstrate" / Path(*parts)
            if not target.resolve().is_relative_to(destination.resolve()) or target.is_symlink():
                raise ValueError("Unsafe material destination")
            if target.exists() and _digest(target) != digest:
                target = target.with_name(f"{target.stem}-{digest[:10]}{target.suffix}")
            if apply:
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    import shutil
                    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.part")
                    try:
                        shutil.copy2(source, temporary)
                        if _digest(temporary) != digest:
                            raise ValueError("Copied material checksum mismatch")
                        temporary.replace(target)
                    finally:
                        temporary.unlink(missing_ok=True)
                await pool.execute(
                    """INSERT INTO moodle_materials(id,owner_id,course_url,source_url,title,
                    section_title,filename,relative_path,sha256) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                    ON CONFLICT (owner_id,course_url,source_url) DO NOTHING""",
                    uuid.uuid4(), settings.telegram_user_id, course_url,
                    "previous-vault:" + relative.as_posix(), target.name,
                    "Materiale păstrate", target.name, target.relative_to(destination).as_posix(), digest,
                )
            copied += 1
        indexed = {
            row["relative_path"] for row in await pool.fetch(
                "SELECT relative_path FROM moodle_materials WHERE owner_id=$1",
                settings.telegram_user_id,
            )
        }
        for target in sorted(destination.rglob("*")):
            if not target.is_file() or target.is_symlink():
                continue
            relative = target.relative_to(destination).as_posix()
            if relative in indexed or len(target.relative_to(destination).parts) < 2:
                continue
            folder = target.relative_to(destination).parts[0]
            course_url = by_folder.get(folder.casefold())
            if not course_url:
                skipped += 1
                continue
            if apply:
                await pool.execute(
                    """INSERT INTO moodle_materials(id,owner_id,course_url,source_url,title,
                    section_title,filename,relative_path,sha256) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                    ON CONFLICT (owner_id,course_url,source_url) DO NOTHING""",
                    uuid.uuid4(), settings.telegram_user_id, course_url,
                    "retained-local:" + relative, target.name, "Material păstrat",
                    target.name, relative, _digest(target),
                )
            unindexed += 1
        if apply:
            await pool.execute(
                """UPDATE moodle_course_sync c SET material_count=(
                    SELECT count(*) FROM moodle_materials m
                    WHERE m.owner_id=c.owner_id AND m.course_url=c.course_url)
                WHERE c.owner_id=$1""", settings.telegram_user_id,
            )
        return {"copied" if apply else "would_copy": copied,
                "indexed_existing" if apply else "would_index_existing": unindexed,
                "skipped_or_duplicate": skipped}
    finally:
        await pool.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Actually copy files and register them in Lora")
    options = parser.parse_args()
    print(asyncio.run(import_materials(apply=options.apply)))


if __name__ == "__main__":
    main()
