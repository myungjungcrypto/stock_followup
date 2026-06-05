from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import models, schemas


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
    stock = models.Stock(
        ticker=payload.ticker.upper().strip(),
        company_name=payload.company_name.strip(),
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
        setattr(stock, field, value)
    if stock.ticker:
        stock.ticker = stock.ticker.upper().strip()
    db.add(stock)
    db.commit()
    db.refresh(stock)
    return stock

