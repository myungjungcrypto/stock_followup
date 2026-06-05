from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.services.ai import AIService
from app.services.dart import DartService
from app.services.news import NewsService
from app.services.telegram import TelegramNotifier


IMPORTANT_ACTIONS = {"NEGATIVE", "REDUCE_RISK", "EXIT_CHECK", "POSITIVE", "RESEARCH"}


class MonitorService:
    def __init__(self) -> None:
        self.ai = AIService()
        self.dart = DartService()
        self.news = NewsService()
        self.telegram = TelegramNotifier()

    async def scan_stock(self, db: Session, stock_id: int, force: bool = True) -> dict:
        stock = db.get(models.Stock, stock_id)
        if not stock:
            return {
                "stock_id": stock_id,
                "events_created": 0,
                "decisions_created": 0,
                "alerts_created": 0,
                "events_skipped": 0,
                "dart_disclosures_created": 0,
                "dart_status": None,
            }

        events_created = 0
        decisions_created = 0
        alerts_created = 0
        events_skipped = 0
        dart_disclosures_created = 0
        dart_status = None

        items = [item for item in stock.tracking_items if item.enabled]
        if not items:
            item = models.TrackingItem(
                stock_id=stock.id,
                label=f"{stock.company_name} 핵심 뉴스",
                rationale="기본 종목 뉴스 모니터링입니다.",
                query=self._default_query(stock),
                priority=2,
                cadence_minutes=stock.check_interval_minutes,
            )
            db.add(item)
            db.commit()
            db.refresh(item)
            items = [item]

        should_scan_dart = force or any(self._is_due(item) for item in items)

        for item in items:
            if not force and not self._is_due(item):
                continue
            try:
                results = await self.news.search(stock, item)
            except Exception:
                item.last_checked_at = datetime.now(timezone.utc)
                db.add(item)
                db.commit()
                continue

            for result in results:
                if result.get("url") and self._event_exists(db, result["url"]):
                    continue
                relevance_score, relevance_terms = self.news.relevance(stock, item, result)
                if relevance_score < self.news.settings.news_min_relevance_score:
                    events_skipped += 1
                    continue
                raw_payload = result.get("raw_payload") or {}
                raw_payload["relevance_terms"] = relevance_terms
                event = models.Event(
                    stock_id=stock.id,
                    tracking_item_id=item.id,
                    title=result["title"],
                    summary=result.get("summary", ""),
                    url=result.get("url"),
                    source=result.get("source", "news"),
                    published_at=result.get("published_at"),
                    raw_payload=raw_payload,
                    relevance_score=relevance_score,
                )
                db.add(event)
                db.commit()
                db.refresh(event)
                events_created += 1

                draft = await self.ai.evaluate_event(stock, item, event)
                decision = models.Decision(
                    stock_id=stock.id,
                    event_id=event.id,
                    action=draft.action,
                    confidence=draft.confidence,
                    reasoning=draft.reasoning,
                    counterpoints=draft.counterpoints,
                )
                db.add(decision)
                db.commit()
                db.refresh(decision)
                decisions_created += 1

                if decision.action in IMPORTANT_ACTIONS and decision.confidence >= 0.55:
                    message = self._format_alert(stock, event, decision)
                    sent, error = await self.telegram.send(message)
                    alert = models.Alert(
                        stock_id=stock.id,
                        decision_id=decision.id,
                        message=message,
                        sent=sent,
                        error=error,
                    )
                    db.add(alert)
                    db.commit()
                    alerts_created += 1

            item.last_checked_at = datetime.now(timezone.utc)
            db.add(item)
            db.commit()

        if should_scan_dart:
            dart_result = await self.dart.search_disclosures(stock)
            dart_status = dart_result.status
            if dart_result.corp_code and not stock.dart_corp_code:
                stock.dart_corp_code = dart_result.corp_code
                db.add(stock)
                db.commit()

            for result in dart_result.events:
                if result.get("url") and self._event_exists(db, result["url"]):
                    continue
                event = models.Event(
                    stock_id=stock.id,
                    tracking_item_id=None,
                    title=result["title"],
                    summary=result.get("summary", ""),
                    url=result.get("url"),
                    source=result.get("source", "opendart"),
                    published_at=result.get("published_at"),
                    raw_payload=result.get("raw_payload") or {},
                    relevance_score=result.get("relevance_score", 1.0),
                )
                db.add(event)
                db.commit()
                db.refresh(event)
                events_created += 1
                dart_disclosures_created += 1

                draft = await self.ai.evaluate_event(stock, None, event)
                decision = models.Decision(
                    stock_id=stock.id,
                    event_id=event.id,
                    action=draft.action,
                    confidence=draft.confidence,
                    reasoning=draft.reasoning,
                    counterpoints=draft.counterpoints,
                )
                db.add(decision)
                db.commit()
                db.refresh(decision)
                decisions_created += 1

                if decision.action in IMPORTANT_ACTIONS and decision.confidence >= 0.55:
                    message = self._format_alert(stock, event, decision)
                    sent, error = await self.telegram.send(message)
                    alert = models.Alert(
                        stock_id=stock.id,
                        decision_id=decision.id,
                        message=message,
                        sent=sent,
                        error=error,
                    )
                    db.add(alert)
                    db.commit()
                    alerts_created += 1

        return {
            "stock_id": stock_id,
            "events_created": events_created,
            "decisions_created": decisions_created,
            "alerts_created": alerts_created,
            "events_skipped": events_skipped,
            "dart_disclosures_created": dart_disclosures_created,
            "dart_status": dart_status,
        }

    def due_stock_ids(self, db: Session) -> list[int]:
        stmt = select(models.Stock.id).order_by(models.Stock.importance.desc(), models.Stock.updated_at.desc())
        return list(db.scalars(stmt).all())

    def _is_due(self, item: models.TrackingItem) -> bool:
        if not item.last_checked_at:
            return True
        cadence = item.cadence_minutes or 180
        return item.last_checked_at <= datetime.now(timezone.utc) - timedelta(minutes=cadence)

    def _event_exists(self, db: Session, url: str) -> bool:
        return db.scalar(select(models.Event.id).where(models.Event.url == url).limit(1)) is not None

    def _format_alert(self, stock: models.Stock, event: models.Event, decision: models.Decision) -> str:
        parts = [
            f"[{self._display_symbol(stock)}] {decision.action}",
            f"확신도: {decision.confidence:.0%}",
            "",
            event.title,
            "",
            decision.reasoning,
        ]
        if event.url:
            parts.extend(["", event.url])
        if decision.counterpoints:
            parts.extend(["", f"주의: {decision.counterpoints}"])
        return "\n".join(parts)

    def _default_query(self, stock: models.Stock) -> str:
        if stock.market.strip().lower() in {"kr", "korea", "kospi", "kosdaq", "한국", "대한민국"}:
            return f"{stock.company_name} 뉴스 공시 실적"
        if self._display_symbol(stock) == stock.company_name:
            return f"{stock.company_name} stock news"
        return f"{self._display_symbol(stock)} {stock.company_name} stock news"

    def _display_symbol(self, stock: models.Stock) -> str:
        return stock.stock_code or stock.ticker or stock.company_name
