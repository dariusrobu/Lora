from datetime import datetime, timezone
from email.utils import format_datetime
from typing import Any

import httpx
import pytest

from modules import news


@pytest.mark.parametrize(
    ("category", "expected_category"),
    [("romania", "politica"), ("business", "economie"), ("tech", "tech")],
)
async def test_dashboard_categories_follow_rss_redirects(
    monkeypatch: pytest.MonkeyPatch, category: str, expected_category: str
) -> None:
    """Category feeds redirect before returning RSS; they must not appear empty."""
    published = format_datetime(datetime.now(timezone.utc))
    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0"><channel><title>Știri</title><item>
    <title>Articol recent - Sursa</title>
    <link>https://example.com/article</link><pubDate>{published}</pubDate>
    </item></channel></rss>"""
    requested_paths: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        if request.url.path == "/rss/resolved":
            return httpx.Response(200, text=rss, headers={"Content-Type": "application/rss+xml"})
        return httpx.Response(302, headers={"Location": "/rss/resolved"})

    real_client = httpx.AsyncClient

    def mock_client(**kwargs: Any) -> httpx.AsyncClient:
        return real_client(transport=httpx.MockTransport(respond), **kwargs)

    monkeypatch.setattr(news.httpx, "AsyncClient", mock_client)
    articles = await news.fetch_news_articles(category=category, limit=4)

    assert requested_paths[-1] == "/rss/resolved"
    assert len(articles) == 1
    assert articles[0]["category"] == expected_category
    assert articles[0]["title"] == "Articol recent"
    assert articles[0]["source"] == "Sursa"
