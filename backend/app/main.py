from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.config import get_settings
from app.database import Base, engine, get_db
from app.services.ai import AIService
from app.services.monitor import MonitorService
from app.services.scheduler import start_scheduler, stop_scheduler


settings = get_settings()
ai = AIService()
monitor = MonitorService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "app": settings.app_name, "environment": settings.environment}


@app.get("/api/stocks", response_model=list[schemas.StockRead])
def list_stocks(db: Session = Depends(get_db)):
    return crud.list_stocks(db)


@app.post("/api/stocks", response_model=schemas.StockRead, status_code=status.HTTP_201_CREATED)
def create_stock(payload: schemas.StockCreate, db: Session = Depends(get_db)):
    return crud.create_stock(db, payload)


@app.get("/api/stocks/{stock_id}", response_model=schemas.StockRead)
def get_stock(stock_id: int, db: Session = Depends(get_db)):
    stock = crud.get_stock_or_none(db, stock_id)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    return stock


@app.patch("/api/stocks/{stock_id}", response_model=schemas.StockRead)
def update_stock(stock_id: int, payload: schemas.StockUpdate, db: Session = Depends(get_db)):
    stock = db.get(models.Stock, stock_id)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    return crud.update_stock(db, stock, payload)


@app.delete("/api/stocks/{stock_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_stock(stock_id: int, db: Session = Depends(get_db)):
    stock = db.get(models.Stock, stock_id)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    db.delete(stock)
    db.commit()
    return None


@app.post("/api/stocks/{stock_id}/notes", response_model=schemas.StockRead, status_code=status.HTTP_201_CREATED)
async def add_note(stock_id: int, payload: schemas.NoteCreate, db: Session = Depends(get_db)):
    stock = db.get(models.Stock, stock_id)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    note = models.Note(
        stock_id=stock.id,
        title=payload.title,
        url=str(payload.url) if payload.url else None,
        source_type=payload.source_type,
        content=payload.content,
    )
    db.add(note)
    db.commit()

    extracted = await ai.extract_tracking_items(stock, payload.content)
    for item in extracted:
        db.add(
            models.TrackingItem(
                stock_id=stock.id,
                label=item["label"],
                rationale=item["rationale"],
                query=item["query"],
                priority=item["priority"],
                cadence_minutes=item["cadence_minutes"],
            )
        )
    db.commit()
    refreshed = crud.get_stock_or_none(db, stock.id)
    if not refreshed:
        raise HTTPException(status_code=404, detail="Stock not found")
    return refreshed


@app.post("/api/stocks/{stock_id}/tracking-items", response_model=schemas.StockRead, status_code=status.HTTP_201_CREATED)
def add_tracking_item(stock_id: int, payload: schemas.TrackingItemCreate, db: Session = Depends(get_db)):
    stock = db.get(models.Stock, stock_id)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    db.add(models.TrackingItem(stock_id=stock.id, **payload.model_dump()))
    db.commit()
    refreshed = crud.get_stock_or_none(db, stock.id)
    if not refreshed:
        raise HTTPException(status_code=404, detail="Stock not found")
    return refreshed


@app.post("/api/stocks/{stock_id}/scan", response_model=schemas.ScanResult)
async def scan_stock(stock_id: int, db: Session = Depends(get_db)):
    stock = db.get(models.Stock, stock_id)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    return await monitor.scan_stock(db, stock_id)

