"""Local, authenticated bridge from n8n to the read-only Moodle extractor."""

from __future__ import annotations

import hmac
import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from datetime import datetime
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from integrations.moodle_readonly import extract_course

load_dotenv(Path(__file__).resolve().parents[1] / "n8n/.env.bridge")


class MoodleExtractRequest(BaseModel):
    """Runtime-only credentials and target; nothing is persisted."""

    course_url: str = Field(pattern=r"^https://econ\.elearning\.ubbcluj\.ro/moodle/course/view\.php\?id=\d+$")
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class MoodleExtractManyRequest(BaseModel):
    """Read-only batch request; credentials are used only for this run."""

    course_urls: list[str] = Field(default_factory=list, max_length=20)
    dashboard_url: str | None = None
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


def _subject_folder(course: str) -> str:
    value = course.lower()
    mapping = (
        ("analiz", "Analiză financiară"),
        ("bazele", "Bazele econometriei"),
        ("jurnalism", "Jurnalism economic"),
        ("macroeconomie", "Macroeconomie aprofundată"),
        ("politici comerciale", "Politici comerciale"),
        ("marketing", "Marketing în comerț"),
    )
    for needle, folder in mapping:
        if needle in value:
            return folder
    return re.sub(r"_(?:SPE3\+FB3\+)?EG3_26-27$", "", course).strip()


def _safe_component(value: str, fallback: str = "General") -> str:
    """Convert Moodle labels into safe, readable folder/file names."""
    cleaned = re.sub(r"[/:*?\"<>|\\]", "-", value).strip().strip(".")
    return cleaned or fallback


def _moodle_bucket(section_title: str) -> str:
    """Map a Moodle section to the user's subject-level organization."""
    title = str(section_title or "General")
    match = re.search(r"(?:c|s|week|săptămâna|saptamana)\s*[- ]*([0-9]+)", title.casefold())
    if match:
        return f"Săptămâna {int(match.group(1))}"
    return "Pregătire intermediară"


def _ensure_week_subfolders(week: Path, root: Path) -> None:
    """Create the requested course/seminar folders in a numbered week."""
    if not re.fullmatch(r"Săptămâna [1-9][0-9]*", week.name):
        return
    for name in ("Curs", "Seminar"):
        directory = week / name
        if directory.is_symlink() or not directory.resolve().is_relative_to(root.resolve()):
            raise ValueError("Refuz scrierea în afara materiilor")
        directory.mkdir(parents=True, exist_ok=True)


def _local_material_lines(item: dict[str, Any]) -> list[str]:
    return list(dict.fromkeys(
        f"- {attachment['vault_link']}" for attachment in item.get("attachments", [])
        if attachment.get("vault_link")
    ))


def _markdown(course: dict[str, Any], stem: str) -> str:
    """Render a non-duplicating index for the course Moodle folder."""
    title = course.get("course", "Moodle")
    lines = [
        f"# Moodle — {title}",
        "",
        "Sincronizare read-only din Moodle.",
        "",
        f"- [Anunțuri](Anunțuri/{stem}.md)",
        "- Forumuri și anunțuri: folderul `Anunțuri/`",
        "- Materiale: folderele `Săptămâna N/`",
        "- Materiale fără săptămână: folderul `Pregătire intermediară/`",
        "- Evaluări: folderul `Examen/` (nu este populat automat)",
        "",
        f"[Curs Moodle]({course.get('source_url', '')})",
        f"\nUltima extragere: {course.get('extracted_at', '')}",
    ]
    return "\n".join(lines) + "\n"


def _group_markdown(course: dict[str, Any], item_types: set[str]) -> str:
    lines = [f"# {course.get('course', 'Moodle')}", ""]
    for section in course.get("sections", []):
        selected = [item for item in section.get("items", []) if item.get("item_type") in item_types]
        if not selected:
            continue
        lines.extend([f"## {section.get('title', 'General')}", ""])
        for item in selected:
            lines.extend([
                f"### {item.get('title', 'Material')}",
                "",
                item.get("content", "").strip(),
            ])
            lines.extend(_local_material_lines(item))
            if item.get("file_url"):
                lines.append(f"[Deschide fișierul]({item['file_url']})")
            if item.get("source_url") and not item.get("discussion_urls"):
                lines.append(f"Sursă: {item['source_url']}")
            lines.append("")
    return "\n".join(lines)


def _section_material_markdown(course: dict[str, Any], section: dict[str, Any]) -> str:
    """Render one Moodle section as a focused material index."""
    lines = [
        f"# {course.get('course', 'Moodle')}",
        "",
        f"## {section.get('title', 'General')}",
        "",
    ]
    for item in section.get("items", []):
        if item.get("item_type") not in {"file", "resource", "external_link", "activity", "description"}:
            continue
        lines.extend([f"### {item.get('title', 'Material')}", ""])
        if item.get("content"):
            lines.extend([item["content"].strip(), ""])
        for attachment in item.get("attachments", []):
            if attachment.get("vault_link"):
                lines.append(f"- {attachment['vault_link']}")
        if item.get("download_errors"):
            lines.append("**Descărcare incompletă:** " + " ".join(item["download_errors"]))
        if item.get("item_type") == "description":
            lines.append("_Instrucțiuni Moodle; această secțiune nu conține un atașament direct._")
        if item.get("file_url"):
            lines.append(f"[Deschide în Moodle]({item['file_url']})")
        elif item.get("source_url"):
            lines.append(f"[Deschide în Moodle]({item['source_url']})")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _is_announcement(item: dict[str, Any], section_title: str) -> bool:
    """Recognize Moodle's announcement forum without including assessments."""
    haystack = " ".join(
        (
            str(item.get("title", "")),
            str(item.get("content", "")),
            section_title,
        )
    ).casefold()
    return section_title.strip().casefold() == "general" or any(
        term in haystack for term in ("anunț", "anunt", "announcement", "news and announcements")
    )


def _announcement_markdown(course: dict[str, Any]) -> str:
    """Render announcements as individual, readable messages."""
    filtered = {
        **course,
        "sections": [
            {
                **section,
                "items": [
                    item
                    for item in section.get("items", [])
                    if item.get("item_type") == "forum"
                    and _is_announcement(item, str(section.get("title", "General")))
                ],
            }
            for section in course.get("sections", [])
        ],
    }
    lines = [f"# Anunțuri — {course.get('course', 'Moodle')}", ""]
    for section in filtered["sections"]:
        for item in section.get("items", []):
            parts = re.split(r"(?=^### )", item.get("content", "").strip(), flags=re.MULTILINE)
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                first, _, body = part.partition("\n")
                lines.extend([f"## {first.removeprefix('### ').strip()}", "", body.strip(), "", "---", ""])
    return _ordered_announcements("\n".join(lines).rstrip("-\n") + "\n")


def _ordered_announcements(text: str) -> str:
    """Deduplicate complete posts and sort by publication time, newest first."""
    parts = re.split(r"(?=^## )", text, flags=re.MULTILINE)
    posts: dict[str, tuple[datetime, str]] = {}
    for part in parts[1:]:
        part = part.strip().rstrip("-\n").strip()
        source = re.search(r"discuss\.php\?d=(\d+)", part)
        key = source.group(1) if source else part
        date = re.search(r"\*\*Data:\*\*\s*([^\n]+)", part)
        stamp = datetime.min
        if date:
            for fmt in ("%A, %d %B %Y, %I:%M %p", "%A, %d %B %Y, %H:%M", "%Y-%m-%dT%H:%M:%S"):
                try:
                    stamp = datetime.strptime(date.group(1).strip().rstrip("\\"), fmt)
                    break
                except ValueError:
                    continue
        if key not in posts:
            posts[key] = (stamp, part)
    return parts[0].rstrip() + "\n\n" + "\n\n---\n\n".join(
        part for _, part in sorted(posts.values(), key=lambda entry: entry[0], reverse=True)
    ) + "\n"


def _forum_markdown(course: dict[str, Any]) -> str:
    """Render non-announcement forum discussions in a dedicated note."""
    filtered = {
        **course,
        "sections": [
            {
                **section,
                "items": [
                    item
                    for item in section.get("items", [])
                    if item.get("item_type") == "forum"
                    and not _is_announcement(item, str(section.get("title", "General")))
                ],
            }
            for section in course.get("sections", [])
        ],
    }
    return _group_markdown(filtered, {"forum"})


def _course_fingerprint(course: dict[str, Any]) -> str:
    payload = {
        "filter_version": 5,
        "course": course.get("course"),
        "source_url": course.get("source_url"),
        "sections": [
            {
                "title": section.get("title"),
                "items": [
                    {
                        "title": item.get("title"),
                        "source_url": item.get("source_url"),
                        "content": item.get("content", ""),
                        "fingerprint": item.get("fingerprint", ""),
                        "files": [attachment.get("sha256") for attachment in item.get("attachments", [])],
                    }
                    for item in section.get("items", [])
                ],
            }
            for section in course.get("sections", [])
        ],
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _write_generated(path: Path, content: str, *, replace_legacy: bool = False) -> None:
    """Refresh managed content while retaining all manually added text."""
    start, end = "<!-- LORA:MOODLE:START -->", "<!-- LORA:MOODLE:END -->"
    block = f"{start}\n{content.rstrip()}\n{end}\n"
    if path.is_symlink():
        raise ValueError("Refuz scrierea printr-un symlink")
    previous = path.read_text(encoding="utf-8") if path.exists() else ""
    if replace_legacy and previous:
        updated = block
    elif start in previous and end in previous:
        before, rest = previous.split(start, 1)
        _, after = rest.split(end, 1)
        updated = before + block.rstrip() + after
    elif previous and not replace_legacy:
        # Older versions did not delimit generated notes. Keep them intact.
        updated = block + "\n" + previous
    elif previous:
        # The Moodle index is fully generated. Remove the legacy unstructured
        # export so current and future syncs cannot accumulate duplicates.
        updated = block
    else:
        updated = block
    if previous != updated:
        path.write_text(updated, encoding="utf-8")


def _copy_materials(course: dict[str, Any], root: Path, moodle_dir: Path) -> None:
    """Copy attachments into Obsidian and attach vault-relative local links."""
    downloads_root = Path(os.getenv("MOODLE_BRIDGE_OUTPUT_DIR", "scratch/moodle")).resolve()
    for section in course.get("sections", []):
        for item in section.get("items", []):
            for attachment in item.get("attachments", []):
                source = Path(attachment["downloaded_path"])
                if not source.is_file() or not source.resolve().is_relative_to(downloads_root):
                    continue
                filename = _safe_component(source.name, "Material.bin")
                target = moodle_dir / _moodle_bucket(section.get("title", "General")) / "Files" / filename
                if not target.resolve().is_relative_to(root.resolve()):
                    raise ValueError("Refuz scrierea în afara materiilor")
                target.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256(source.read_bytes()).hexdigest()
                if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                    # Never overwrite user edits or another attachment of the same name.
                    target = target.with_name(f"{target.stem}-{digest[:10]}{target.suffix}")
                if target.is_symlink() or not target.resolve().is_relative_to(root.resolve()):
                    raise ValueError("Refuz scrierea printr-un symlink")
                if not target.exists():
                    temporary = target.with_suffix(target.suffix + ".part")
                    if temporary.is_symlink():
                        raise ValueError("Unsafe temporary attachment")
                    shutil.copy2(source, temporary)
                    temporary.replace(target)
                relative = target.relative_to(root.parent).as_posix()
                attachment["vault_link"] = f"[[{relative}|{target.name}]]"


def _save_to_vault(course: dict[str, Any], *, changed: bool = True) -> str:
    root = Path(os.getenv(
        "MOODLE_OBSIDIAN_ROOT",
        "/Users/robu/Library/Mobile Documents/iCloud~md~obsidian/Documents/Lora/05 University",
    ))
    title = str(course.get("course", "Moodle"))
    folder = _safe_component(_subject_folder(title))
    safe_name = _safe_component(title).replace(" ", "-")
    subject_root = root / folder
    destination = subject_root / "Moodle.md"
    if not destination.resolve().is_relative_to(root.resolve()):
        raise ValueError("Refuz scrierea în afara materiilor")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stem = safe_name
    _copy_materials(course, root, destination.parent)
    # The index is generated metadata, so normalize it on every sync even
    # when the course fingerprint is unchanged. This also removes legacy
    # unstructured exports left by older bridge versions.
    _write_generated(destination, _markdown(course, stem), replace_legacy=True)
    announcements_dir = subject_root / "Anunțuri"
    materials_dir = subject_root / "Pregătire intermediară"
    for directory in (announcements_dir, materials_dir, subject_root / "Examen"):
        if not directory.resolve().is_relative_to(root.resolve()):
            raise ValueError("Refuz scrierea în afara materiilor")
    announcements_dir.mkdir(parents=True, exist_ok=True)
    materials_dir.mkdir(parents=True, exist_ok=True)
    _write_generated(announcements_dir / f"{stem}.md", _announcement_markdown(course))
    _write_generated(announcements_dir / f"{stem} - Forumuri.md", _forum_markdown(course))
    for section in course.get("sections", []):
        bucket = subject_root / _moodle_bucket(section.get("title", "General"))
        bucket.mkdir(parents=True, exist_ok=True)
        _ensure_week_subfolders(bucket, root)
        section_items = section.get("items", [])
        material_items = [
            item for item in section_items
            if item.get("item_type") in {"file", "resource", "external_link", "activity", "description"}
        ]
        if material_items:
            _write_generated(bucket / f"{_safe_component(section.get('title', 'General'))}.md", _section_material_markdown(course, section))
    for section in course.get("sections", []):
        section_items = section.get("items", [])
        section_title = str(section.get("title", "General"))
        material_items = [
            item for item in section_items
            if item.get("item_type") in {"file", "resource", "external_link", "activity", "description"}
        ]
        if material_items:
            section_slug = _safe_component(section_title)
            section_path = subject_root / _moodle_bucket(section_title) / f"{section_slug}.md"
            if not section_path.resolve().is_relative_to(root.resolve()):
                raise ValueError("Refuz scrierea printr-un symlink")
            _write_generated(section_path, _section_material_markdown(course, section))
    return str(destination)


app = FastAPI(title="Lora Moodle Read-only Bridge", docs_url=None, redoc_url=None)


def _authorized(token: str | None) -> bool:
    expected = os.getenv("MOODLE_BRIDGE_TOKEN", "")
    return bool(expected and token and hmac.compare_digest(token, expected))


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "moodle-readonly-bridge"}


@app.post("/extract")
async def extract(
    request: MoodleExtractRequest,
    x_lora_bridge_token: str | None = Header(default=None),
) -> dict[str, Any]:
    if not _authorized(x_lora_bridge_token):
        raise HTTPException(status_code=401, detail="Unauthorized")

    output_path = Path(os.getenv("MOODLE_BRIDGE_OUTPUT", "scratch/moodle/latest.json"))
    course = await extract_course(
        request.course_url,
        Path(os.getenv("MOODLE_BROWSER_PROFILE", ".moodle-firefox-profile-2")),
        output_path,
        headed=True,
        browser_name="firefox",
        username=request.username,
        password=request.password,
        downloads_dir=output_path.parent / "files" / "single",
    )
    course["saved_file"] = _save_to_vault(course)
    return course


@app.post("/extract-many")
async def extract_many(
    request: MoodleExtractManyRequest,
    x_lora_bridge_token: str | None = Header(default=None),
) -> dict[str, Any]:
    """Extract several enrolled courses without performing any Moodle write."""
    if not _authorized(x_lora_bridge_token):
        raise HTTPException(status_code=401, detail="Unauthorized")
    course_urls = list(dict.fromkeys(request.course_urls))
    if not course_urls and request.dashboard_url:
        course_urls = await _discover_course_urls(request.dashboard_url, request.username, request.password)
    if not course_urls:
        raise HTTPException(status_code=422, detail="No course URLs found")
    if any(
        not re.fullmatch(
            r"https://econ\.elearning\.ubbcluj\.ro/moodle/course/view\.php\?id=\d+",
            url,
        )
        for url in course_urls
    ):
        raise HTTPException(status_code=422, detail="Invalid course URL")

    profile = Path(os.getenv("MOODLE_BROWSER_PROFILE", ".moodle-firefox-profile-2"))
    output_dir = Path(os.getenv("MOODLE_BRIDGE_OUTPUT_DIR", "scratch/moodle"))
    results: list[dict[str, Any]] = []
    for index, course_url in enumerate(course_urls, start=1):
        results.append(
            await extract_course(
                course_url,
                profile,
                output_dir / f"course-{index}.json",
                headed=True,
                browser_name="firefox",
                username=request.username,
                password=request.password,
                downloads_dir=output_dir / "files" / str(index),
            )
        )
    state_path = output_dir / "sync-state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    except (OSError, json.JSONDecodeError):
        state = {}
    saved: list[str] = []
    sync: list[dict[str, Any]] = []
    next_state: dict[str, str] = {}
    for course in results:
        key = str(course.get("source_url") or course.get("course_id") or course.get("course"))
        fingerprint = _course_fingerprint(course)
        changed = state.get(key) != fingerprint
        saved.append(_save_to_vault(course, changed=changed))
        next_state[key] = fingerprint
        sync.append({"course": course.get("course"), "status": "updated" if changed else "unchanged", "new_or_changed": changed})
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(next_state, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"courses": results, "saved_files": saved, "sync": sync, "count": len(results)}


async def _discover_course_urls(dashboard_url: str, username: str, password: str) -> list[str]:
    """Discover enrolled course links from the authenticated dashboard."""
    from playwright.async_api import async_playwright

    profile = Path(os.getenv("MOODLE_BROWSER_PROFILE", ".moodle-firefox-profile-2"))
    async with async_playwright() as playwright:
        browser = await playwright.firefox.launch_persistent_context(str(profile), headless=False)
        try:
            page = browser.pages[0] if browser.pages else await browser.new_page()
            await page.goto(dashboard_url, wait_until="domcontentloaded")
            if "/login/" in page.url:
                await page.locator('input[name="username"]').fill(username)
                await page.locator('input[name="password"]').fill(password)
                await page.locator('button[type="submit"], input[type="submit"]').first.click()
                await page.wait_for_function("!window.location.pathname.includes('/login/')", timeout=300_000)
            links = await page.locator('a[href*="/moodle/course/view.php?id="]').evaluate_all(
                "els => els.map(e => e.href)"
            )
            return sorted({url.split("#", 1)[0] for url in links})
        finally:
            await browser.close()
