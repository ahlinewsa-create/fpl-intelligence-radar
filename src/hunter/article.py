"""Bounded, source-authorized full-text article extraction.

Inspired by Horizon's optional full-text + feed-fallback approach.
Never follow an RSS article link to an arbitrary host.
"""
from __future__ import annotations

import ipaddress
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
import httpx

MAX_BYTES = 1_200_000
MAX_TEXT_CHARS = 14_000


def allowed_url(url: str, allowed_hosts: list[str]) -> bool:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not host or parsed.username or parsed.password:
        return False
    try:
        port = parsed.port
    except ValueError:
        return False
    if port not in (None, 443) or host == "localhost":
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return any(host == domain.lower().rstrip(".") for domain in allowed_hosts)


def article_image(html: str, page_url: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    for key in ("og:image", "twitter:image"):
        meta = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
        value = str(meta.get("content", "")) if meta else ""
        if value:
            candidate = urljoin(page_url, value)
            parsed = urlsplit(candidate)
            if parsed.scheme == "https" and parsed.hostname and not parsed.username:
                return candidate[:900]
    return None


def article_text(html: str) -> str:
    import trafilatura

    text = trafilatura.extract(
        html, favor_precision=True, include_comments=False,
        include_tables=True,
    )
    if text and len(text.strip()) >= 100:
        return text[:MAX_TEXT_CHARS]
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style", "noscript", "nav", "footer", "header"]):
        node.decompose()
    primary = soup.select_one("article") or soup.select_one("main")
    if primary:
        return primary.get_text(" ", strip=True)[:MAX_TEXT_CHARS]
    return ""


def fetch_article(client: httpx.Client, url: str, allowed_hosts: list[str]) -> dict:
    """Fail closed with explicit status; caller must fall back to feed text."""
    if not allowed_url(url, allowed_hosts):
        return {"status": "not_allowed", "text": "", "image_url": None}
    current = url
    try:
        for _ in range(3):
            with client.stream(
                "GET", current,
                headers={"Accept": "text/html,application/xhtml+xml"},
                follow_redirects=False,
                timeout=15.0,
            ) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get("location", "")
                    target = urljoin(current, location)
                    if not allowed_url(target, allowed_hosts):
                        return {"status": "redirect_not_allowed", "text": "", "image_url": None}
                    current = target
                    continue
                response.raise_for_status()
                if "html" not in response.headers.get("content-type", "").lower():
                    return {"status": "not_html", "text": "", "image_url": None}
                if int(response.headers.get("content-length", "0") or "0") > MAX_BYTES:
                    return {"status": "too_large", "text": "", "image_url": None}
                chunks = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_BYTES:
                        return {"status": "too_large", "text": "", "image_url": None}
                    chunks.append(chunk)
                html = b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")
            extracted = article_text(html)
            return {
                "status": "full_text" if extracted else "no_article_text",
                "text": extracted, "image_url": article_image(html, current),
            }
        return {"status": "too_many_redirects", "text": "", "image_url": None}
    except (httpx.HTTPError, ValueError, TypeError, UnicodeError, ImportError):
        return {"status": "failed", "text": "", "image_url": None}
