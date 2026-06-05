import asyncio

from app.models import Event, Stock
from app.services.ai import AIService


def test_fallback_extracts_tracking_items_without_api_key():
    stock = Stock(ticker="NVDA", company_name="NVIDIA", thesis="AI data center growth")
    service = AIService()

    items = asyncio.run(service.extract_tracking_items(stock, "AI datacenter margin and Blackwell demand should be tracked."))

    assert items
    assert all(item["query"] for item in items)


def test_fallback_flags_negative_event():
    stock = Stock(ticker="TSLA", company_name="Tesla", thesis="FSD and margin recovery", position_type="holding")
    event = Event(title="Tesla faces investigation over recall delay", summary="", stock_id=1)
    service = AIService()

    decision = asyncio.run(service.evaluate_event(stock, None, event))

    assert decision.action in {"NEGATIVE", "REDUCE_RISK"}
    assert decision.confidence > 0.5

