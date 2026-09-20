"""
Unit tests for modules/news.py — RSS parsing, 24h filter, relative time, and intent handling.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
import pytest

from modules.news import (
    _format_relative_time,
    fetch_news_digest,
    handle_news_intent,
)


def test_format_relative_time():
    now = datetime.now(timezone.utc)
    assert _format_relative_time(None) == "recent"
    assert "min" in _format_relative_time(now - timedelta(minutes=25))
    assert "ore" in _format_relative_time(now - timedelta(hours=3))
    assert _format_relative_time(now - timedelta(hours=30)) == "ieri"


@pytest.mark.asyncio
async def test_fetch_news_digest_mocked():
    sample_rss = b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>Google News</title>
        <item>
          <title>Guvernul a anuntat noile masuri fiscale - Economedia.ro</title>
          <pubDate>""" + datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT").encode() + b"""</pubDate>
        </item>
        <item>
          <title>Stire veche de acum 3 zile - ProTV</title>
          <pubDate>""" + (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%a, %d %b %Y %H:%M:%S GMT").encode() + b"""</pubDate>
        </item>
      </channel>
    </rss>"""

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_resp.content = sample_rss
        mock_resp.raise_for_status = lambda: None
        mock_get.return_value = mock_resp

        # Test Politica
        digest_pol = await fetch_news_digest("politica")
        assert "Politică" in digest_pol
        assert "Guvernul a anuntat noile masuri fiscale" in digest_pol
        assert "Stire veche" not in digest_pol  # filtered out by 24h cutoff

        # Test Economie
        digest_eco = await fetch_news_digest("economie")
        assert "Economie" in digest_eco

        # Test All
        digest_all = await fetch_news_digest("all")
        assert "Sinteza Știrilor din Ultimele 24h" in digest_all


@pytest.mark.asyncio
async def test_handle_news_intent():
    with patch("modules.news.fetch_news_digest", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = "News content"

        reply, markup, item_id = await handle_news_intent(
            pool=None, intent="get_news", data={"topic": "politica"}
        )
        assert reply == "News content"
        assert markup is None
        assert item_id is None
        mock_fetch.assert_called_once_with(topic="politica", limit=3)
