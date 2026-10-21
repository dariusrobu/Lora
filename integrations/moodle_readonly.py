"""Read-only Moodle course extractor for the MacBook browser session.

The extractor only performs GET/navigation requests. It never submits forms,
marks activities complete, or changes Moodle state. Authentication is kept in
a local Playwright profile; passwords are not read or stored by this module.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs
from urllib.parse import urlencode
from urllib.parse import urljoin
from urllib.parse import urlparse

from lxml import html as lxml_html

from integrations.moodle_files import download_material


@dataclass(frozen=True)
class MoodleItem:
    """A read-only item found inside a Moodle course section."""

    item_type: str
    title: str
    source_url: str
    content: str = ""
    file_name: str | None = None
    file_url: str | None = None
    unread: bool = False
    fingerprint: str = ""


@dataclass(frozen=True)
class MoodleSection:
    """A Moodle course section and its visible items."""

    title: str
    items: list[MoodleItem] = field(default_factory=list)


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _absolute(base_url: str, href: str | None) -> str:
    return urljoin(base_url, href or "")


def _fingerprint(*parts: str) -> str:
    payload = "\x1f".join(_clean(part) for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _format_forum_post(post: Any) -> str:
    """Render one Moodle post as readable Markdown instead of one text line."""
    raw = _clean(post.text_content())
    match = re.match(
        r"^(?P<title>.+?)\s+by\s+(?P<author>.+?)\s+-\s+"
        r"(?P<date>.+?)\s+Number of replies:\s*(?P<replies>\d+)\s+"
        r"(?P<body>.+?)(?:\s+Permalink)?$",
        raw,
        flags=re.IGNORECASE,
    )
    if not match:
        return raw

    body = match.group("body").strip()
    links: list[str] = []
    for anchor in post.xpath(".//a[@href]"):
        href = _absolute("https://econ.elearning.ubbcluj.ro", anchor.get("href"))
        label = _clean(anchor.text_content())
        if label and "permalink" not in label.casefold() and "/user/" not in href:
            links.append(f"[{label}]({href})")
    if links:
        body = f"{body}\n\n**Linkuri:** {' · '.join(dict.fromkeys(links))}"
    return (
        f"**Autor:** {match.group('author').strip()}\n"
        f"**Data:** {match.group('date').strip()}\n"
        f"**Răspunsuri:** {match.group('replies')}\n\n"
        f"**Mesaj:**\n{body}"
    )


_ASSESSMENT_TERMS = (
    "test",
    "teste",
    "examen",
    "examene",
    "quiz",
    "evaluare",
    "evaluarea",
    "colocviu",
    "subiecte",
    "grila",
    "grilă",
)


def is_assessment_content(*values: str) -> bool:
    """Identify assessment content that must never be imported or downloaded."""
    haystack = _clean(" ".join(values)).casefold()
    return any(term in haystack for term in _ASSESSMENT_TERMS)


def _is_material_href(href: str) -> bool:
    parsed = urlparse(href)
    return any(
        marker in parsed.path
        for marker in ("/mod/resource/", "/mod/folder/", "/pluginfile.php/", "/mod/url/")
    )


def parse_forum_html(html: str, page_url: str) -> str:
    """Return visible forum posts as compact Markdown-safe plain text."""
    document = lxml_html.fromstring(html)
    for node in document.xpath("//script | //style | //noscript"):
        node.drop_tree()
    posts = document.xpath(
        "//*[contains(concat(' ', normalize-space(@class), ' '), ' forum-post ')]"
        " | //article[contains(@class, 'post')]"
        " | //*[@data-content='forum-post']"
    )
    if not posts:
        posts = document.xpath("//*[contains(@id, 'post-')]")
    lines: list[str] = []
    seen: set[str] = set()
    for post in posts:
        text = _format_forum_post(post)
        if text and text not in seen:
            seen.add(text)
            lines.append(text)
    if lines:
        return "\n\n".join(lines)
    main = document.xpath("//main | //*[@role='main'] | //div[contains(@class, 'region-main')]")
    return _clean((main[0] if main else document).text_content())


def parse_forum_discussion_links(html: str, page_url: str) -> list[dict[str, str]]:
    """Find discussion pages linked from a Moodle forum index."""
    document = lxml_html.fromstring(html)
    for node in document.xpath("//script | //style | //noscript"):
        node.drop_tree()
    links: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in document.xpath("//a[@href]"):
        href = _absolute(page_url, anchor.get("href"))
        parsed = urlparse(href)
        if parsed.path.endswith("/mod/forum/discuss.php") and parsed.query:
            discussion_id = parse_qs(parsed.query).get("d", [""])[0]
            if not discussion_id:
                continue
            canonical_query = urlencode({"d": discussion_id})
            href = parsed._replace(query=canonical_query, fragment="").geturl()
            title = _clean(anchor.text_content()) or "Discuție Moodle"
            if href not in seen:
                seen.add(href)
                links.append({"title": title, "url": href})
    return links


def parse_course_html(html: str, page_url: str) -> dict[str, Any]:
    """Parse a Moodle course page without executing page actions."""

    document = lxml_html.fromstring(html)
    title_nodes = document.xpath("//h1 | //*[@class='page-header-headings']//h1")
    course_title = _clean(title_nodes[0].text_content()) if title_nodes else ""
    course_id = ""
    match = re.search(r"[?&]id=(\d+)", page_url)
    if match:
        course_id = match.group(1)

    sections: list[MoodleSection] = []
    section_nodes = document.xpath(
        "//li[contains(concat(' ', normalize-space(@class), ' '), ' section ')]"
        " | //*[@data-for='section']"
        " | //*[@class='course-section']"
    )
    if not section_nodes:
        section_nodes = [document]

    seen: set[str] = set()
    for section_node in section_nodes:
        heading_nodes = section_node.xpath(
            ".//*[self::h2 or self::h3 or contains(concat(' ', normalize-space(@class), ' '), ' sectionname ')]"
        )
        section_title = _clean(heading_nodes[0].text_content()) if heading_nodes else "General"
        items: list[MoodleItem] = []
        section_is_assessment = is_assessment_content(section_title)

        activities = section_node.xpath(
            ".//*[contains(concat(' ', normalize-space(@class), ' '), ' activity ') "
            "or contains(concat(' ', normalize-space(@class), ' '), ' modtype_forum ') "
            "or contains(concat(' ', normalize-space(@class), ' '), ' modtype_resource ') "
            "or contains(concat(' ', normalize-space(@class), ' '), ' modtype_url ') "
            "or contains(concat(' ', normalize-space(@class), ' '), ' activity-item ')]"
        )
        for activity in activities:
            links = activity.xpath(".//a[@href]")
            if not links:
                continue
            link = next((candidate for candidate in links if
                         "/mod/" in _absolute(page_url, candidate.get("href"))
                         or _is_material_href(_absolute(page_url, candidate.get("href")))), links[0])
            item_title = _clean(link.text_content())
            href = _absolute(page_url, link.get("href"))
            if not item_title:
                continue
            classes = activity.get("class", "")
            if "forum" in classes:
                item_type = "forum"
            elif "resource" in classes or "folder" in classes or _is_material_href(href) and "/mod/url/" not in href or activity.xpath(".//img[contains(@src, 'pdf')]"):
                item_type = "file"
            elif "url" in classes:
                item_type = "external_link"
            else:
                item_type = "activity"
            content = _clean(activity.text_content())
            if section_is_assessment or is_assessment_content(item_title, content):
                continue
            unread = "unread" in classes or bool(
                activity.xpath(
                    ".//*[contains(concat(' ', normalize-space(@class), ' '), ' unread ') "
                    "or contains(concat(' ', normalize-space(@class), ' '), ' badge ') "
                    "or contains(@class, 'unread')]"
                )
            )
            file_name = item_title if item_type == "file" else None
            item = MoodleItem(
                item_type=item_type,
                title=item_title,
                source_url=href,
                content=content,
                file_name=file_name,
                file_url=href if item_type == "file" else None,
                unread=unread,
                fingerprint=_fingerprint(item_type, item_title, href, content),
            )
            if href not in seen:
                seen.add(href)
                items.append(item)

        # Some Moodle courses place resources directly in the section
        # description instead of wrapping them in an activity node.
        for link in section_node.xpath(".//a[@href]"):
            href = _absolute(page_url, link.get("href"))
            if not _is_material_href(href):
                continue
            item_title = _clean(link.text_content()) or "Material Moodle"
            if section_is_assessment or is_assessment_content(section_title, item_title):
                continue
            item_type = "external_link" if "/mod/url/" in urlparse(href).path else "file"
            item = MoodleItem(
                item_type=item_type,
                title=item_title,
                source_url=href,
                content=item_title,
                file_name=item_title if item_type == "file" else None,
                file_url=href if item_type == "file" else None,
                fingerprint=_fingerprint(item_type, item_title, href),
            )
            if href not in seen:
                seen.add(href)
                items.append(item)

        # Preserve visible section text such as teacher instructions, even if
        # Moodle did not wrap it in an activity node.
        if not items and not section_is_assessment:
            text = _clean(section_node.text_content())
            if text and section_title != text:
                items.append(
                    MoodleItem(
                        item_type="description",
                        title=section_title,
                        source_url=page_url,
                        content=text,
                        fingerprint=_fingerprint("description", section_title, text),
                    )
                )
        if items:
            sections.append(MoodleSection(title=section_title, items=items))

    return {
        "source": "moodle",
        "course": course_title,
        "course_id": course_id,
        "source_url": page_url,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "sections": [
            {"title": section.title, "items": [asdict(item) for item in section.items]}
            for section in sections
        ],
    }


def parse_section_links(html: str, course_url: str) -> list[dict[str, str]]:
    """Moodle's section-summary view hides attachments behind section pages."""
    document = lxml_html.fromstring(html)
    base = urlparse(course_url)
    course_id = parse_qs(base.query).get("id")
    links: list[dict[str, str]] = []
    seen: set[str] = set()
    for section in document.xpath(
        "//*[contains(concat(' ', normalize-space(@class), ' '), ' section-summary ')]"
    ):
        for anchor in section.xpath('.//h2//a[@href] | .//h3//a[@href]'):
            url = _absolute(course_url, anchor.get("href"))
            parsed = urlparse(url)
            query = parse_qs(parsed.query)
            title = _clean(anchor.text_content())
            if (parsed.scheme != base.scheme or parsed.netloc != base.netloc
                    or parsed.path != base.path or query.get("id") != course_id
                    or not query.get("section", [""])[0].isdigit()
                    or is_assessment_content(title) or url in seen):
                continue
            seen.add(url)
            links.append({"title": title, "url": url})
    return links


async def extract_course(
    course_url: str,
    profile_dir: Path,
    output_path: Path,
    *,
    headed: bool = True,
    browser_executable: str | None = None,
    browser_name: str = "firefox",
    username: str | None = None,
    password: str | None = None,
    downloads_dir: Path | None = None,
) -> dict[str, Any]:
    """Extract one course using a persistent, user-authenticated browser profile."""

    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is required for Moodle extraction. Install dependencies "
            "and run `python -m playwright install chromium`."
        ) from exc

    profile_dir.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as playwright:
        browser_type = getattr(playwright, browser_name)
        browser = await browser_type.launch_persistent_context(
            str(profile_dir),
            headless=not headed,
            executable_path=browser_executable or os.getenv("MOODLE_BROWSER_EXECUTABLE"),
        )
        try:
            page = browser.pages[0] if browser.pages else await browser.new_page()
            await page.goto(course_url, wait_until="domcontentloaded")
            if "/login/" in page.url or await page.locator('input[name="password"]').count():
                login_user = username or os.getenv("MOODLE_USERNAME")
                login_password = password or os.getenv("MOODLE_PASSWORD")
                if login_user and login_password:
                    host = urlparse(page.url).hostname
                    allowed_host = os.getenv("MOODLE_HOST", "econ.elearning.ubbcluj.ro")
                    if host != allowed_host:
                        raise RuntimeError("Refuz login-ul: domeniul Moodle nu este permis")
                    await page.locator('input[name="username"]').fill(login_user)
                    await page.locator('input[name="password"]').fill(login_password)
                    await page.locator('button[type="submit"], input[type="submit"]').first.click()
                elif headed:
                    print(
                        "Moodle cere autentificare în profilul Playwright. "
                        "Finalizează login-ul în fereastra Firefox; extractorul așteaptă "
                        "apoi și continuă automat.",
                        flush=True,
                    )
                else:
                    raise RuntimeError("Sesiunea Moodle a expirat; lipsesc credentialele pentru autentificare headless.")
                await page.wait_for_function(
                    "!document.querySelector('input[name=password]')",
                    timeout=30_000,
                )
                await page.goto(course_url, wait_until="domcontentloaded")
            if "/login/" in page.url or await page.locator('input[name="password"]').count():
                raise RuntimeError("Sesiunea Moodle a expirat. Autentifică-te în Firefox.")
            course_html = await page.content()
            result = parse_course_html(course_html, page.url)
            for section_link in parse_section_links(course_html, course_url):
                await page.goto(section_link["url"], wait_until="domcontentloaded")
                if "/login/" in page.url:
                    raise RuntimeError("Sesiunea Moodle a expirat în timpul sincronizării.")
                detail = parse_course_html(await page.content(), page.url)
                selected = [section for section in detail["sections"]
                            if section["title"] == section_link["title"]]
                if selected:
                    result["sections"] = [section for section in result["sections"]
                                          if section["title"] != section_link["title"]]
                    result["sections"].extend(selected)
            for section in result["sections"]:
                for item in section["items"]:
                    if item["item_type"] == "forum":
                        await page.goto(item["source_url"], wait_until="domcontentloaded")
                        forum_html = await page.content()
                        discussion_links = parse_forum_discussion_links(forum_html, page.url)
                        listing_content = parse_forum_html(forum_html, page.url)
                        discussions: list[str] = []
                        for discussion in discussion_links:
                            await page.goto(discussion["url"], wait_until="domcontentloaded")
                            discussion_content = parse_forum_html(await page.content(), page.url)
                            if is_assessment_content(discussion["title"], discussion_content):
                                continue
                            if discussion_content:
                                discussions.append(
                                    f"### {discussion['title']}\n\n"
                                    f"{discussion_content}\n\n"
                                    f"**Sursă discuție:** [{page.url}]({page.url})"
                                )
                        item["content"] = "\n\n".join(discussions) or listing_content
                        item["discussion_urls"] = [discussion["url"] for discussion in discussion_links]
                        item["fingerprint"] = _fingerprint(item["item_type"], item["title"], item["source_url"], item["content"])
                    if downloads_dir and item["item_type"] == "file" and item.get("file_url"):
                        attachments, errors = await download_material(page.request, item["file_url"], downloads_dir)
                        item["attachments"] = attachments
                        item["download_errors"] = errors
                        if attachments:
                            item["downloaded_path"] = attachments[0]["downloaded_path"]
        finally:
            await browser.close()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only Moodle course extractor")
    parser.add_argument("--url", default=os.getenv("MOODLE_COURSE_URL"))
    parser.add_argument("--profile", default=os.getenv("MOODLE_BROWSER_PROFILE", ".moodle-profile"))
    parser.add_argument("--output", default=os.getenv("MOODLE_EXTRACT_OUTPUT", "scratch/moodle/course.json"))
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--downloads", default="scratch/moodle/files")
    parser.add_argument("--browser-executable", default=os.getenv("MOODLE_BROWSER_EXECUTABLE"))
    parser.add_argument("--browser", choices=("firefox", "chromium"), default=os.getenv("MOODLE_BROWSER", "firefox"))
    parser.add_argument("--username-env", default="MOODLE_USERNAME")
    parser.add_argument("--password-env", default="MOODLE_PASSWORD")
    return parser


async def _main() -> None:
    args = _build_parser().parse_args()
    if not args.url:
        raise SystemExit("Provide --url or MOODLE_COURSE_URL")
    result = await extract_course(
        args.url,
        Path(args.profile).expanduser(),
        Path(args.output).expanduser(),
        headed=not args.headless,
        browser_executable=args.browser_executable,
        browser_name=args.browser,
        username=os.getenv(args.username_env),
        password=os.getenv(args.password_env),
        downloads_dir=Path(args.downloads).expanduser(),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(_main())
