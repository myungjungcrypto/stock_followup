from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import models, schemas


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _clean_upper_optional(value: str | None) -> str | None:
    cleaned = _clean_optional(value)
    return cleaned.upper() if cleaned else None


def _stock_identifier(payload: schemas.StockCreate | schemas.StockUpdate, company_name: str) -> str:
    ticker = _clean_upper_optional(getattr(payload, "ticker", None))
    stock_code = _clean_upper_optional(getattr(payload, "stock_code", None))
    return ticker or stock_code or company_name.strip()


def get_stock_or_none(db: Session, stock_id: int) -> models.Stock | None:
    stmt = (
        select(models.Stock)
        .where(models.Stock.id == stock_id)
        .options(
            selectinload(models.Stock.notes),
            selectinload(models.Stock.tracking_items),
            selectinload(models.Stock.events),
            selectinload(models.Stock.decisions),
            selectinload(models.Stock.alerts),
        )
    )
    return db.scalar(stmt)


def list_stocks(db: Session) -> list[models.Stock]:
    stmt = (
        select(models.Stock)
        .order_by(models.Stock.updated_at.desc())
        .options(
            selectinload(models.Stock.notes),
            selectinload(models.Stock.tracking_items),
            selectinload(models.Stock.events),
            selectinload(models.Stock.decisions),
            selectinload(models.Stock.alerts),
        )
    )
    return list(db.scalars(stmt).all())


def create_stock(db: Session, payload: schemas.StockCreate) -> models.Stock:
    company_name = payload.company_name.strip()
    stock_code = _clean_upper_optional(payload.stock_code)
    stock = models.Stock(
        ticker=_stock_identifier(payload, company_name),
        stock_code=stock_code,
        dart_corp_code=_clean_upper_optional(payload.dart_corp_code),
        company_name=company_name,
        market=payload.market.upper().strip(),
        status=payload.status,
        position_type=payload.position_type,
        average_price=payload.average_price,
        target_price=payload.target_price,
        stop_loss=payload.stop_loss,
        thesis=payload.thesis,
        importance=payload.importance,
        check_interval_minutes=payload.check_interval_minutes,
    )
    db.add(stock)
    db.commit()
    db.refresh(stock)
    return stock


def update_stock(db: Session, stock: models.Stock, payload: schemas.StockUpdate) -> models.Stock:
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        if field in {"ticker", "stock_code", "dart_corp_code"}:
            value = _clean_upper_optional(value)
        elif field in {"company_name", "market", "status", "position_type", "thesis"} and value is not None:
            value = value.strip()
        setattr(stock, field, value)
    stock.company_name = stock.company_name.strip()
    stock.ticker = _clean_upper_optional(stock.ticker) or _clean_upper_optional(stock.stock_code) or stock.company_name
    if stock.stock_code:
        stock.stock_code = stock.stock_code.upper().strip()
    if stock.dart_corp_code:
        stock.dart_corp_code = stock.dart_corp_code.upper().strip()
    db.add(stock)
    db.commit()
    db.refresh(stock)
    return stock
