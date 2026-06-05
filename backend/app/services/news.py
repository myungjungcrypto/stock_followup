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

    def relevance(self, stock: Stock, item: TrackingItem, result: dict) -> tuple[float, list[str]]:
        text = self._clean_text(f"{result.get('title', '')} {result.get('summary', '')}").lower()
        matched: list[str] = []
        score = 0.0

        for term in self._stock_terms(stock):
            if term.lower() in text:
                matched.append(term)
                if term == stock.company_name:
                    score = max(score, 0.95)
                elif term == getattr(stock, "stock_code", None):
                    score = max(score, 0.85)
                elif term == stock.ticker:
                    score = max(score, 0.85)
                else:
                    score = max(score, 0.75)

        keyword_matches = []
        for term in self._important_terms(stock, item):
            if term.lower() in text:
                keyword_matches.append(term)

        if keyword_matches:
            matched.extend(keyword_matches)
            keyword_score = min(0.55, 0.25 + 0.08 * len(keyword_matches))
            score = max(score, keyword_score)
            if any(term in matched for term in self._stock_terms(stock)):
                score = min(1.0, score + min(0.1, 0.02 * len(keyword_matches)))

        return round(score, 2), matched[:8]

    def _build_query(self, stock: Stock, item: TrackingItem) -> str:
        pieces = [
            stock.company_name,
            getattr(stock, "stock_code", None),
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

    def _stock_terms(self, stock: Stock) -> list[str]:
        terms = [stock.company_name]
        stock_code = getattr(stock, "stock_code", None)
        if stock_code and stock_code != stock.company_name:
            terms.append(stock_code)
        if stock.ticker and stock.ticker != stock.company_name:
            terms.append(stock.ticker)
        aliases = self._aliases(stock.company_name)
        for alias in aliases:
            if alias not in terms:
                terms.append(alias)
        return [term for term in terms if len(term.strip()) >= 2]

    def _aliases(self, company_name: str) -> list[str]:
        aliases = []
        suffixes = ["테크놀로지", "기술", "화학", "전자", "반도체", "정밀화학", "주식회사", "(주)"]
        for suffix in suffixes:
            if company_name.endswith(suffix):
                alias = company_name[: -len(suffix)].strip()
                if len(alias) >= 3:
                    aliases.append(alias)
        return aliases

    def _important_terms(self, stock: Stock, item: TrackingItem) -> list[str]:
        text = f"{item.label} {item.query}"
        tokens = re.findall(r"[A-Za-z가-힣0-9]{2,}", text)
        stock_terms = {term.lower() for term in self._stock_terms(stock)}
        stopwords = {
            "뉴스",
            "공시",
            "관련",
            "변화",
            "여부",
            "주식",
            "stock",
            "news",
            "and",
            "the",
            "with",
            "for",
        }
        terms = []
        seen = set()
        for token in tokens:
            key = token.lower()
            if key in seen or key in stopwords or key in stock_terms:
                continue
            if token.isdigit():
                continue
            terms.append(token)
            seen.add(key)
        return terms[:10]

    def _parse_date(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
