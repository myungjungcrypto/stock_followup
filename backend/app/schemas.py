from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class StockCreate(BaseModel):
    ticker: str = Field(min_length=1, max_length=32)
    company_name: str = Field(min_length=1, max_length=255)
    market: str = "US"
    status: str = "watching"
    position_type: str = "watchlist"
    average_price: float | None = None
    target_price: float | None = None
    stop_loss: float | None = None
    thesis: str = ""
    importance: int = Field(default=3, ge=1, le=5)
    check_interval_minutes: int = Field(default=180, ge=15)


class StockUpdate(BaseModel):
    company_name: str | None = None
    market: str | None = None
    status: str | None = None
    position_type: str | None = None
    average_price: float | None = None
    target_price: float | None = None
    stop_loss: float | None = None
    thesis: str | None = None
    importance: int | None = Field(default=None, ge=1, le=5)
    check_interval_minutes: int | None = Field(default=None, ge=15)


class NoteCreate(BaseModel):
    title: str = ""
    url: HttpUrl | None = None
    source_type: str = "memo"
    content: str = Field(min_length=5)


class TrackingItemCreate(BaseModel):
    label: str
    rationale: str = ""
    query: str = ""
    priority: int = Field(default=3, ge=1, le=5)
    cadence_minutes: int = Field(default=180, ge=15)
    enabled: bool = True


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class NoteRead(ORMModel):
    id: int
    stock_id: int
    title: str
    url: str | None
    source_type: str
    content: str
    created_at: datetime


class TrackingItemRead(ORMModel):
    id: int
    stock_id: int
    label: str
    rationale: str
    query: str
    priority: int
    cadence_minutes: int
    enabled: bool
    last_checked_at: datetime | None
    created_at: datetime


class EventRead(ORMModel):
    id: int
    stock_id: int
    tracking_item_id: int | None
    title: str
    summary: str
    url: str | None
    source: str
    published_at: datetime | None
    relevance_score: float
    sentiment: str
    created_at: datetime


class DecisionRead(ORMModel):
    id: int
    stock_id: int
    event_id: int | None
    action: str
    confidence: float
    reasoning: str
    counterpoints: str
    created_at: datetime


class AlertRead(ORMModel):
    id: int
    stock_id: int
    decision_id: int | None
    channel: str
    message: str
    sent: bool
    error: str | None
    created_at: datetime


class StockRead(ORMModel):
    id: int
    ticker: str
    company_name: str
    market: str
    status: str
    position_type: str
    average_price: float | None
    target_price: float | None
    stop_loss: float | None
    thesis: str
    importance: int
    check_interval_minutes: int
    created_at: datetime
    updated_at: datetime
    notes: list[NoteRead] = []
    tracking_items: list[TrackingItemRead] = []
    events: list[EventRead] = []
    decisions: list[DecisionRead] = []
    alerts: list[AlertRead] = []


class ScanResult(BaseModel):
    stock_id: int
    events_created: int
    decisions_created: int
    alerts_created: int

