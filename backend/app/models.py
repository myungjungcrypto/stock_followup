from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class Stock(Base):
    __tablename__ = "stocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ticker: Mapped[str] = mapped_column(String(32), index=True)
    company_name: Mapped[str] = mapped_column(String(255))
    market: Mapped[str] = mapped_column(String(64), default="US")
    status: Mapped[str] = mapped_column(String(32), default="watching")
    position_type: Mapped[str] = mapped_column(String(32), default="watchlist")
    average_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    thesis: Mapped[str] = mapped_column(Text, default="")
    importance: Mapped[int] = mapped_column(Integer, default=3)
    check_interval_minutes: Mapped[int] = mapped_column(Integer, default=180)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    notes: Mapped[list["Note"]] = relationship(back_populates="stock", cascade="all, delete-orphan")
    tracking_items: Mapped[list["TrackingItem"]] = relationship(back_populates="stock", cascade="all, delete-orphan")
    events: Mapped[list["Event"]] = relationship(back_populates="stock", cascade="all, delete-orphan")
    decisions: Mapped[list["Decision"]] = relationship(back_populates="stock", cascade="all, delete-orphan")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="stock", cascade="all, delete-orphan")


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(255), default="")
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), default="memo")
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    stock: Mapped[Stock] = relationship(back_populates="notes")


class TrackingItem(Base):
    __tablename__ = "tracking_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(255))
    rationale: Mapped[str] = mapped_column(Text, default="")
    query: Mapped[str] = mapped_column(String(500), default="")
    priority: Mapped[int] = mapped_column(Integer, default=3)
    cadence_minutes: Mapped[int] = mapped_column(Integer, default=180)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    stock: Mapped[Stock] = relationship(back_populates="tracking_items")
    events: Mapped[list["Event"]] = relationship(back_populates="tracking_item")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"), index=True)
    tracking_item_id: Mapped[int | None] = mapped_column(ForeignKey("tracking_items.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(100), default="news")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    relevance_score: Mapped[float] = mapped_column(Float, default=0.5)
    sentiment: Mapped[str] = mapped_column(String(32), default="neutral")
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    stock: Mapped[Stock] = relationship(back_populates="events")
    tracking_item: Mapped[TrackingItem | None] = relationship(back_populates="events")
    decisions: Mapped[list["Decision"]] = relationship(back_populates="event")


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"), index=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(64), default="NO_ACTION")
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    reasoning: Mapped[str] = mapped_column(Text, default="")
    counterpoints: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    stock: Mapped[Stock] = relationship(back_populates="decisions")
    event: Mapped[Event | None] = relationship(back_populates="decisions")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="decision")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"), index=True)
    decision_id: Mapped[int | None] = mapped_column(ForeignKey("decisions.id"), nullable=True)
    channel: Mapped[str] = mapped_column(String(32), default="telegram")
    message: Mapped[str] = mapped_column(Text)
    sent: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    stock: Mapped[Stock] = relationship(back_populates="alerts")
    decision: Mapped[Decision | None] = relationship(back_populates="alerts")

