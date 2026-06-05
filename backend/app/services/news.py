from datetime import datetime
from email.utils import parsedate_to_datetime
from html import unescape
import re
from urllib.parse import quote_plus

import feedparser
import httpx

from app.config import get_settings
from app.models import Stock, TrackingItem


class NewsService:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def search(self, stock: Stock, item: TrackingItem) -> list[dict]:
        query = self._build_query(stock, item)
        locale = self._locale(stock.market)
        url = (
            "https://news.google.com/rss/search"
            f"?q={quote_plus(query)}"
            f"&hl={locale['hl']}&gl={locale['gl']}&ceid={locale['ceid']}"
        )
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
        parsed = feedparser.parse(response.text)
        results = []
        for entry in parsed.entries[: self.settings.news_max_items_per_tracking_item]:
            published_at = self._parse_date(entry.get("published"))
            results.append(
                {
                    "title": self._clean_text(entry.get("title", "")),
                    "summary": self._clean_text(entry.get("summary", "")),
                    "url": entry.get("link"),
                    "source": f"google_news_rss_{locale['gl'].lower()}",
                    "published_at": published_at,
                    "raw_payload": {
                        "id": entry.get("id"),
                        "source": entry.get("source", {}),
                        "query": query,
                    },
                }
            )
        return [result for result in results if result["title"]]

    def _build_query(self, stock: Stock, item: TrackingItem) -> str:
        pieces = [
            stock.company_name,
            "" if stock.ticker == stock.company_name else stock.ticker,
            item.query,
        ]
        if not item.query:
            pieces.append(item.label)
        words = []
        seen = set()
        for piece in pieces:
            for word in str(piece or "").replace("/", " ").split():
                normalized = word.strip()
                key = normalized.lower()
                if normalized and key not in seen:
                    words.append(normalized)
                    seen.add(key)
        return " ".join(words[:12])

    def _locale(self, market: str) -> dict[str, str]:
        normalized = market.strip().lower()
        if normalized in {"kr", "korea", "kospi", "kosdaq", "한국", "대한민국"}:
            return {"hl": "ko", "gl": "KR", "ceid": "KR:ko"}
        if normalized in {"jp", "japan", "일본"}:
            return {"hl": "ja", "gl": "JP", "ceid": "JP:ja"}
        return {"hl": "en-US", "gl": "US", "ceid": "US:en"}

    def _clean_text(self, value: str) -> str:
        without_tags = re.sub(r"<[^>]+>", " ", value or "")
        return " ".join(unescape(without_tags).split())

    def _parse_date(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
