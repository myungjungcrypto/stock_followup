import json
import re
from dataclasses import dataclass

from openai import AsyncOpenAI

from app.config import get_settings
from app.models import Event, Stock, TrackingItem


TRACKING_SCHEMA_HINT = {
    "tracking_items": [
        {
            "label": "short item to monitor",
            "rationale": "why it matters",
            "query": "search query",
            "priority": 3,
            "cadence_minutes": 180,
        }
    ]
}

DECISION_SCHEMA_HINT = {
    "action": "NO_ACTION | WATCH | RESEARCH | POSITIVE | NEGATIVE | REDUCE_RISK | EXIT_CHECK",
    "confidence": 0.0,
    "reasoning": "brief thesis-aware reasoning",
    "counterpoints": "what could make this interpretation wrong",
}


@dataclass
class DecisionDraft:
    action: str
    confidence: float
    reasoning: str
    counterpoints: str


class AIService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = AsyncOpenAI(api_key=self.settings.openai_api_key) if self.settings.openai_api_key else None

    async def extract_tracking_items(self, stock: Stock, note_content: str) -> list[dict]:
        if self.client:
            try:
                return await self._extract_with_openai(stock, note_content)
            except Exception:
                return self._extract_fallback(stock, note_content)
        return self._extract_fallback(stock, note_content)

    async def evaluate_event(self, stock: Stock, tracking_item: TrackingItem | None, event: Event) -> DecisionDraft:
        if self.client:
            try:
                return await self._evaluate_with_openai(stock, tracking_item, event)
            except Exception:
                return self._evaluate_fallback(stock, tracking_item, event)
        return self._evaluate_fallback(stock, tracking_item, event)

    async def _extract_with_openai(self, stock: Stock, note_content: str) -> list[dict]:
        prompt = f"""
You are an equity follow-up analyst. Extract concrete monitoring items from the user's note.

Stock:
- Ticker: {stock.ticker}
- Stock code: {stock.stock_code or "N/A"}
- DART corp code: {stock.dart_corp_code or "N/A"}
- Company: {stock.company_name}
- Current thesis: {stock.thesis or "N/A"}

Return strict JSON matching this shape:
{json.dumps(TRACKING_SCHEMA_HINT, ensure_ascii=False)}

Rules:
- Create 3-7 items.
- Each item should be something a monitoring system can search or check repeatedly.
- Use Korean if the input is mostly Korean; otherwise English is fine.
- priority is 1 low to 5 urgent.
- cadence_minutes should be 60, 180, 360, 720, or 1440.

User note:
{note_content}
""".strip()
        response = await self.client.chat.completions.create(
            model=self.settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        content = response.choices[0].message.content or "{}"
        payload = json.loads(content)
        return self._normalize_tracking_items(payload.get("tracking_items", []), stock)

    async def _evaluate_with_openai(
        self, stock: Stock, tracking_item: TrackingItem | None, event: Event
    ) -> DecisionDraft:
        prompt = f"""
You are an equity follow-up analyst. Decide whether this new event changes the user's stock thesis.

Return strict JSON matching this shape:
{json.dumps(DECISION_SCHEMA_HINT, ensure_ascii=False)}

Allowed actions:
- NO_ACTION: not important
- WATCH: worth watching, no action yet
- RESEARCH: user should investigate
- POSITIVE: strengthens the thesis
- NEGATIVE: weakens the thesis
- REDUCE_RISK: consider reducing position/risk
- EXIT_CHECK: check sell/exit conditions immediately

Stock:
- Ticker: {stock.ticker}
- Stock code: {stock.stock_code or "N/A"}
- DART corp code: {stock.dart_corp_code or "N/A"}
- Company: {stock.company_name}
- Thesis: {stock.thesis or "N/A"}
- Position: {stock.position_type}
- Target: {stock.target_price or "N/A"}
- Stop loss: {stock.stop_loss or "N/A"}

Tracking item:
{tracking_item.label if tracking_item else "General stock monitoring"}
{tracking_item.rationale if tracking_item else ""}

Event:
- Title: {event.title}
- Summary: {event.summary}
- URL: {event.url or "N/A"}
""".strip()
        response = await self.client.chat.completions.create(
            model=self.settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        payload = json.loads(response.choices[0].message.content or "{}")
        return DecisionDraft(
            action=str(payload.get("action", "WATCH")).upper(),
            confidence=float(payload.get("confidence", 0.5)),
            reasoning=str(payload.get("reasoning", "")),
            counterpoints=str(payload.get("counterpoints", "")),
        )

    def _extract_fallback(self, stock: Stock, note_content: str) -> list[dict]:
        candidates = []
        candidates.extend(self._domain_tracking_candidates(stock, note_content))
        lines = [line.strip("-* 	") for line in note_content.splitlines() if line.strip()]
        keywords = self._keywords(note_content)
        for keyword in keywords[:5]:
            if len(candidates) >= 6:
                break
            candidates.append(
                {
                    "label": f"{keyword} 관련 변화",
                    "rationale": f"입력 메모에서 '{keyword}'가 중요 신호로 감지됐습니다.",
                    "query": f"{self._stock_query_prefix(stock)} {keyword}",
                    "priority": 3,
                    "cadence_minutes": stock.check_interval_minutes,
                }
            )
        for line in lines[:3]:
            if len(candidates) >= 6:
                break
            label = line[:80]
            candidates.append(
                {
                    "label": label,
                    "rationale": "사용자 입력에서 직접 추출한 팔로우업 항목입니다.",
                    "query": f"{self._stock_query_prefix(stock)} {label}",
                    "priority": 3,
                    "cadence_minutes": stock.check_interval_minutes,
                }
            )
        if not candidates:
            candidates.append(
                {
                    "label": f"{stock.company_name} 핵심 뉴스",
                    "rationale": "기본 종목 뉴스 모니터링입니다.",
                    "query": f"{self._stock_query_prefix(stock)} stock news",
                    "priority": 2,
                    "cadence_minutes": stock.check_interval_minutes,
                }
            )
        return self._normalize_tracking_items(candidates, stock)

    def _domain_tracking_candidates(self, stock: Stock, text: str) -> list[dict]:
        lowered = text.lower()
        stock_query = self._stock_query_prefix(stock)
        patterns = [
            (
                ["실적", "매출", "영업이익", "영업이익률", "roe"],
                "분기 실적과 마진 개선 지속 여부",
                "입력 thesis에서 실적 개선과 수익성이 핵심 근거로 제시됐습니다.",
                f"{stock_query} 실적 영업이익 영업이익률",
                4,
            ),
            (
                ["euv", "arf", "pr", "pag", "모노머", "폴리머"],
                "EUV/ArF PR 핵심 원료 공급 확대",
                "선단공정 소재 확장이 re-rating 근거로 제시됐습니다.",
                f"{stock_query} EUV ArF PR PAG 모노머 폴리머",
                4,
            ),
            (
                ["식각액", "디벨로퍼", "불산", "tsv", "패키징"],
                "식각액·디벨로퍼·패키징 소재 개발 진척",
                "제품군 확장과 신규 공정 소재 개발이 thesis의 중요한 축입니다.",
                f"{stock_query} 식각액 디벨로퍼 TSV 패키징 소재",
                3,
            ),
            (
                ["텍사스", "미국", "현지", "공급망", "고객사"],
                "미국 현지 공급망과 고객사 대응",
                "미국 법인과 현지 공급망 대응은 고객사 확대 여부를 판단하는 단서입니다.",
                f"{stock_query} 미국 텍사스 공급망 고객사",
                3,
            ),
            (
                ["per", "pbr", "roe", "부채비율", "밸류에이션"],
                "밸류에이션과 재무 안정성 변화",
                "현재 매력의 일부가 낮은 밸류에이션과 안정적 재무지표에 의존합니다.",
                f"{stock_query} PER PBR ROE 부채비율 밸류에이션",
                3,
            ),
            (
                ["반도체", "디스플레이", "전자재료", "정밀화학"],
                "반도체·디스플레이 소재 업황",
                "업황 변화가 매출과 마진에 직접 영향을 줄 수 있습니다.",
                f"{stock_query} 반도체 디스플레이 전자재료 소재 업황",
                3,
            ),
        ]
        candidates = []
        for needles, label, rationale, query, priority in patterns:
            if any(needle in lowered for needle in needles):
                candidates.append(
                    {
                        "label": label,
                        "rationale": rationale,
                        "query": query,
                        "priority": priority,
                        "cadence_minutes": stock.check_interval_minutes or self.settings.default_check_interval_minutes,
                    }
                )
        return candidates

    def _evaluate_fallback(
        self, stock: Stock, tracking_item: TrackingItem | None, event: Event
    ) -> DecisionDraft:
        text = f"{event.title} {event.summary}".lower()
        negative = [
            "downgrade",
            "lawsuit",
            "probe",
            "investigation",
            "fraud",
            "recall",
            "delay",
            "miss",
            "warning",
            "cuts guidance",
            "하향",
            "소송",
            "조사",
            "리콜",
            "지연",
            "실적 부진",
            "감소",
            "하락",
            "적자",
            "손실",
            "악화",
            "둔화",
            "철회",
            "중단",
            "취소",
        ]
        positive = [
            "upgrade",
            "approval",
            "beat",
            "raises guidance",
            "partnership",
            "contract",
            "record",
            "surge",
            "승인",
            "상향",
            "호실적",
            "계약",
            "파트너십",
            "증가",
            "개선",
            "수혜",
            "기대",
            "확대",
            "진입",
            "동력",
            "성장",
            "흑자",
            "최대",
            "수주",
            "공급",
            "개발",
        ]
        if any(word in text for word in negative):
            action = "NEGATIVE" if stock.position_type == "watchlist" else "REDUCE_RISK"
            return DecisionDraft(
                action=action,
                confidence=0.68,
                reasoning=f"{stock.ticker} 관련 부정 키워드가 새 이벤트에서 감지됐습니다. thesis 훼손 여부를 확인해야 합니다.",
                counterpoints="제목 기반 판단이라 원문 세부 내용, 시장 컨텍스트, 실제 수치 확인이 필요합니다.",
            )
        if any(word in text for word in positive):
            return DecisionDraft(
                action="POSITIVE",
                confidence=0.64,
                reasoning=f"{stock.ticker} 관련 긍정 키워드가 새 이벤트에서 감지됐습니다. 기존 thesis 강화 가능성이 있습니다.",
                counterpoints="뉴스가 이미 가격에 반영됐거나 일회성 이벤트일 수 있습니다.",
            )
        return DecisionDraft(
            action="WATCH",
            confidence=0.45,
            reasoning=f"{stock.ticker} 관련 새 정보가 발견됐지만 방향성은 명확하지 않습니다.",
            counterpoints="정보의 중요도가 낮거나 기존 thesis와 직접 관련이 없을 수 있습니다.",
        )

    def _stock_query_prefix(self, stock: Stock) -> str:
        pieces = [stock.stock_code or stock.ticker, stock.company_name]
        words = []
        seen = set()
        for piece in pieces:
            key = str(piece or "").strip().lower()
            if key and key not in seen:
                words.append(str(piece).strip())
                seen.add(key)
        return " ".join(words)

    def _normalize_tracking_items(self, items: list[dict], stock: Stock) -> list[dict]:
        normalized = []
        seen = set()
        default_cadence = stock.check_interval_minutes or self.settings.default_check_interval_minutes
        for item in items:
            label = str(item.get("label", "")).strip()
            if not label or label.lower() in seen:
                continue
            seen.add(label.lower())
            cadence = item.get("cadence_minutes") or default_cadence
            normalized.append(
                {
                    "label": label[:255],
                    "rationale": str(item.get("rationale", ""))[:2000],
                    "query": str(item.get("query") or f"{self._stock_query_prefix(stock)} {label}")[:500],
                    "priority": min(max(int(item.get("priority", 3)), 1), 5),
                    "cadence_minutes": min(max(int(cadence), 15), 10080),
                }
            )
        return normalized[:7]

    def _keywords(self, text: str) -> list[str]:
        words = re.findall(r"[A-Za-z가-힣][A-Za-z가-힣0-9%+.-]{2,}", text)
        stopwords = {
            "the",
            "and",
            "for",
            "with",
            "that",
            "this",
            "from",
            "about",
            "관련",
            "해서",
            "있는",
            "없는",
            "그리고",
        }
        ranked: dict[str, int] = {}
        for word in words:
            key = word.strip().lower()
            if key in stopwords:
                continue
            ranked[key] = ranked.get(key, 0) + 1
        return [word for word, _ in sorted(ranked.items(), key=lambda pair: pair[1], reverse=True)]
