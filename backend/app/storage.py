import os
from datetime import datetime, timezone
from sqlalchemy import create_engine, String, DateTime, JSON, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session
from .domain import AdRow

class Base(DeclarativeBase): pass
class Dataset(Base):
    __tablename__ = 'datasets'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    rows: Mapped[list] = mapped_column(JSON)

# Only created on a database operation; demo mode never needs a database or Meta.
_engine = None

def engine():
    global _engine
    if _engine is None:
        _engine = create_engine(os.environ.get('DATABASE_URL', 'postgresql+psycopg://dashboard:dashboard_local@127.0.0.1:5432/meta_ads'), pool_pre_ping=True, connect_args={'connect_timeout': 3})
    return _engine

def initialize(): Base.metadata.create_all(engine())

def save(rows, digest):
    from sqlalchemy.exc import IntegrityError
    with Session(engine()) as s:
        existing = s.get(Dataset, digest)
        if existing: return existing.imported_at, False
        record = Dataset(id=digest, imported_at=datetime.now(timezone.utc), rows=[r.model_dump(mode='json') for r in rows])
        s.add(record)
        try: s.commit()
        except IntegrityError:
            s.rollback()
            return s.get(Dataset, digest).imported_at, False
        return record.imported_at, True

def load(digest):
    with Session(engine()) as s:
        record = s.get(Dataset, digest)
        if not record: return None
        return [AdRow.model_validate(r) for r in record.rows], record.imported_at
