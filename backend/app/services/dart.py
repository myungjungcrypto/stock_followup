from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from io import BytesIO
from zipfile import BadZipFile, ZipFile
import xml.etree.ElementTree as ET

import httpx

from app.config import get_settings
from app.models import Stock


DART_CORP_CODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"
DART_DISCLOSURE_LIST_URL = "https://opendart.fss.or.kr/api/list.json"
DART_DISCLOSURE_VIEW_URL = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"
KOREAN_MARKETS = {"kr", "korea", "kospi", "kosdaq", "konex", "한국", "대한민국"}


@dataclass
class DartDisclosureResult:
    events: list[dict]
    status: str | None = None
    corp_code: str | None = None


class DartService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._corp_codes: list[dict] | None = None

    async def search_disclosures(self, stock: Stock) -> DartDisclosureResult:
        if not self._should_scan(stock):
            return DartDisclosureResult(events=[], status=None)
        if not self.settings.dart_api_key:
            return DartDisclosureResult(events=[], status="DART_API_KEY 미설정")

        try:
            corp_code = stock.dart_corp_code or await self.resolve_corp_code(stock)
            if not corp_code:
                return DartDisclosureResult(
                    events=[],
                    status="DART corp_code를 찾지 못했습니다. 종목코드 또는 DART corp_code를 확인하세요.",
                )
            payload = await self._fetch_disclosures(corp_code)
        except (httpx.HTTPError, ValueError, BadZipFile) as exc:
            return DartDisclosureResult(events=[], status=f"DART 조회 실패: {exc}")

        status = str(payload.get("status", ""))
        message = str(payload.get("message", ""))
        if status == "013":
            return DartDisclosureResult(events=[], status="DART 신규 공시 없음", corp_code=corp_code)
        if status != "000":
            return DartDisclosureResult(events=[], status=f"DART 오류 {status}: {message}", corp_code=corp_code)

        disclosures = payload.get("list") or []
        events = [self._to_event(disclosure) for disclosure in disclosures]
        return DartDisclosureResult(events=[event for event in events if event["title"]], corp_code=corp_code)

    async def resolve_corp_code(self, stock: Stock) -> str | None:
        corp_codes = await self._fetch_corp_codes()
        return self._find_corp_code(corp_codes, stock)

    async def _fetch_corp_codes(self) -> list[dict]:
        if self._corp_codes is not None:
            return self._corp_codes
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(DART_CORP_CODE_URL, params={"crtfc_key": self.settings.dart_api_key})
            response.raise_for_status()
        self._corp_codes = self._parse_corp_code_zip(response.content)
        return self._corp_codes

    async def _fetch_disclosures(self, corp_code: str) -> dict:
        end = datetime.now(timezone.utc).date()
        begin = end - timedelta(days=self.settings.dart_lookback_days)
        params = {
            "crtfc_key": self.settings.dart_api_key,
            "corp_code": corp_code,
            "bgn_de": begin.strftime("%Y%m%d"),
            "end_de": end.strftime("%Y%m%d"),
            "sort": "date",
            "sort_mth": "desc",
            "page_no": "1",
            "page_count": str(self.settings.dart_max_disclosures_per_scan),
        }
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            response = await client.get(DART_DISCLOSURE_LIST_URL, params=params)
            response.raise_for_status()
        return response.json()

    def _parse_corp_code_zip(self, content: bytes) -> list[dict]:
        try:
            archive = ZipFile(BytesIO(content))
        except BadZipFile as exc:
            raise ValueError("기업고유번호 응답을 ZIP으로 읽지 못했습니다.") from exc

        xml_names = [name for name in archive.namelist() if name.lower().endswith(".xml")]
        if not xml_names:
            raise ValueError("기업고유번호 ZIP 안에 XML 파일이 없습니다.")
        root = ET.fromstring(archive.read(xml_names[0]))
        codes: list[dict] = []
        for node in root.findall("list"):
            codes.append(
                {
                    "corp_code": self._node_text(node, "corp_code"),
                    "corp_name": self._node_text(node, "corp_name"),
                    "corp_eng_name": self._node_text(node, "corp_eng_name"),
                    "stock_code": self._node_text(node, "stock_code"),
                    "modify_date": self._node_text(node, "modify_date"),
                }
            )
        return codes

    def _find_corp_code(self, corp_codes: list[dict], stock: Stock) -> str | None:
        target_code = self._normalize_code(stock.stock_code or stock.ticker)
        target_name = self._normalize_name(stock.company_name)

        if target_code:
            for row in corp_codes:
                if self._normalize_code(row.get("stock_code")) == target_code:
                    return row.get("corp_code") or None

        if target_name:
            for row in corp_codes:
                if self._normalize_name(row.get("corp_name")) == target_name:
                    return row.get("corp_code") or None
        return None

    def _to_event(self, disclosure: dict) -> dict:
        report_name = str(disclosure.get("report_nm") or "").strip()
        corp_name = str(disclosure.get("corp_name") or "").strip()
        receipt_no = str(disclosure.get("rcept_no") or "").strip()
        filing_date = self._parse_filing_date(str(disclosure.get("rcept_dt") or ""))
        submitter = str(disclosure.get("flr_nm") or "").strip()
        note = str(disclosure.get("rm") or "").strip()
        pieces = [corp_name, disclosure.get("rcept_dt"), submitter]
        if note:
            pieces.append(f"비고 {note}")
        return {
            "title": f"[DART] {report_name}",
            "summary": " · ".join(str(piece) for piece in pieces if piece),
            "url": DART_DISCLOSURE_VIEW_URL.format(rcept_no=receipt_no) if receipt_no else None,
            "source": "opendart",
            "published_at": filing_date,
            "raw_payload": disclosure,
            "relevance_score": 1.0,
        }

    def _should_scan(self, stock: Stock) -> bool:
        market = (stock.market or "").strip().lower()
        return market in KOREAN_MARKETS or bool(stock.dart_corp_code or stock.stock_code)

    def _parse_filing_date(self, value: str) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y%m%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    def _node_text(self, node: ET.Element, tag: str) -> str:
        found = node.find(tag)
        return (found.text or "").strip() if found is not None else ""

    def _normalize_code(self, value: str | None) -> str:
        return (value or "").strip().upper()

    def _normalize_name(self, value: str | None) -> str:
        return (value or "").replace(" ", "").strip().lower()
