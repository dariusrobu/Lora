"""Download actual Moodle attachments using the authenticated browser context.

Only same-origin resource/folder/file GETs are allowed. HTML is resolved as a
wrapper, never saved as a PDF or document. No Moodle activity is completed.
"""

from __future__ import annotations

import hashlib
import mimetypes
import re
from email.message import Message
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, unquote, urlencode, urljoin, urlparse

from lxml import html as lxml_html

MAX_FILE_BYTES = 60 * 1024 * 1024


def allowed_material_url(url: str, origin: str) -> bool:
    parsed, base = urlparse(url), urlparse(origin)
    return (
        parsed.scheme == base.scheme == "https"
        and parsed.netloc == base.netloc
        and not parsed.username
        and any(part in parsed.path for part in (
            "/pluginfile.php/", "/mod/resource/view.php", "/mod/folder/view.php",
        ))
    )


def attachment_links(html: str, page_url: str) -> list[str]:
    """Resolve download links and embedded files, not unrelated navigation."""
    document = lxml_html.fromstring(html)
    links = document.xpath('//a/@href | //object/@data | //iframe/@src | //embed/@src')
    return list(dict.fromkeys(
        urljoin(page_url, href) for href in links
        if allowed_material_url(urljoin(page_url, href), page_url)
        and "/pluginfile.php/" in urlparse(urljoin(page_url, href)).path
    ))


def attachment_filename(headers: dict[str, str], url: str, body: bytes) -> str:
    message = Message()
    message["Content-Disposition"] = headers.get("content-disposition", "")
    name = message.get_filename() or unquote(urlparse(url).path.rsplit("/", 1)[-1])
    try:
        name = name.encode("latin1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    name = re.sub(r'[\x00-\x1f\x7f-\x9f/:*?"<>|\\]', "-", name).strip(" .")[:180]
    if not name or name.lower().endswith((".php", ".html", ".htm")):
        name = "Material"
    if not Path(name).suffix:
        mime = headers.get("content-type", "").split(";", 1)[0].strip()
        extension = mimetypes.guess_extension(mime) or ""
        for signature, suffix in ((b"%PDF-", ".pdf"), (b"Rar!", ".rar"),
                                  (b"PK\x03\x04", ".zip"), (b"7z\xbc\xaf\x27\x1c", ".7z")):
            if body.startswith(signature):
                extension = suffix
                break
        name += extension or ".bin"
    return name


async def download_material(
    request: Any, url: str, directory: Path,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Resolve resource/folder wrappers and return verified local attachments.

    Redirects are handled explicitly so browser cookies are never forwarded to
    unrelated hosts. Stable URL directories avoid collisions between materials.
    """
    pending = [(url, 0)]
    seen: set[str] = set()
    attachments: list[dict[str, Any]] = []
    errors: list[str] = []
    while pending and len(seen) < 80:
        target, depth = pending.pop(0)
        parsed = urlparse(target)
        identity = parsed._replace(query=urlencode([
            (key, value) for key, value in parse_qsl(parsed.query)
            if key != "forcedownload"
        ]), fragment="").geturl()
        if identity in seen:
            continue
        seen.add(identity)
        if depth > 6 or not allowed_material_url(target, url):
            errors.append("Destinație de descărcare nepermisă.")
            continue
        response = None
        try:
            response = await request.get(target, max_redirects=0, timeout=30_000)
            headers = {key.lower(): value for key, value in response.headers.items()}
            if response.status in (301, 302, 303, 307, 308):
                pending.append((urljoin(target, headers.get("location", "")), depth + 1))
                continue
            if not response.ok:
                errors.append(f"Descărcare refuzată (HTTP {response.status}).")
                continue
            if int(headers.get("content-length", "0")) > MAX_FILE_BYTES:
                errors.append("Fișierul depășește limita de 60 MB.")
                continue
            body = await response.body()
            if not body or len(body) > MAX_FILE_BYTES:
                errors.append("Fișier gol sau prea mare.")
                continue
            html_body = body.lstrip()[:200].lower()
            if "html" in headers.get("content-type", "") or html_body.startswith(
                (b"<!doctype html", b"<html", b"<head", b"<body")
            ):
                links = attachment_links(body.decode("utf-8", errors="replace"), target)
                if not links:
                    errors.append("Pagina nu conține un fișier accesibil; verifică autentificarea Moodle.")
                pending.extend((link, depth + 1) for link in links)
                continue
            filename = attachment_filename(headers, target, body)
            destination = directory / hashlib.sha256(target.encode()).hexdigest()[:16] / filename
            destination.parent.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256(body).hexdigest()
            if destination.is_symlink() or not destination.resolve().is_relative_to(directory.resolve()):
                raise ValueError("Unsafe attachment destination")
            if not destination.exists() or hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
                temporary = destination.with_suffix(destination.suffix + ".part")
                if temporary.is_symlink():
                    raise ValueError("Unsafe temporary destination")
                temporary.write_bytes(body)
                temporary.replace(destination)
            attachments.append({
                "name": filename, "url": target, "downloaded_path": str(destination),
                "sha256": digest, "size": len(body),
            })
        except Exception:
            # Never include raw HTTP exceptions: they may contain credentials.
            errors.append("Nu am putut descărca acest material.")
        finally:
            if response is not None:
                await response.dispose()
    if pending:
        errors.append("Prea multe fișiere; restul nu au fost descărcate.")
    return attachments, list(dict.fromkeys(errors))
