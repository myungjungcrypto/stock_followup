from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


settings = get_settings()

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def ensure_schema() -> None:
    inspector = inspect(engine)
    if not inspector.has_table("stocks"):
        return
    columns = {column["name"] for column in inspector.get_columns("stocks")}
    additions = {
        "stock_code": "ALTER TABLE stocks ADD COLUMN stock_code VARCHAR(32)",
        "dart_corp_code": "ALTER TABLE stocks ADD COLUMN dart_corp_code VARCHAR(32)",
    }
    with engine.begin() as connection:
        for column, ddl in additions.items():
            if column not in columns:
                connection.execute(text(ddl))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
