"""Durable per-account/per-slot claims. Never reclaim uncertain/running sends."""
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, JSON, Integer, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column, Session
from .storage import Base


class ReportRun(Base):
    __tablename__ = 'report_runs'
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    account: Mapped[str] = mapped_column(String(64), index=True)
    slot: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(40))
    snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)


def run_key(account, slot):
    return account + ':' + slot.astimezone(timezone.utc).isoformat()


class ReportStore:
    def __init__(self, engine): self.engine = engine

    def claim(self, account, slot):
        key = run_key(account, slot)
        with Session(self.engine) as session:
            session.add(ReportRun(key=key, account=account, slot=slot, started_at=datetime.now(timezone.utc), status='running'))
            try: session.commit()
            except IntegrityError:
                session.rollback()
                existing = session.get(ReportRun, key)
                if existing is None: raise
                return key, False, existing.status
        return key, True, 'running'

    def previous(self, account):
        with Session(self.engine) as session:
            previous = session.scalar(select(ReportRun).where(ReportRun.account == account, ReportRun.status == 'sent').order_by(ReportRun.slot.desc()).limit(1))
            return previous.snapshot if previous else None

    def finish(self, key, status, snapshot=None, message_id=None, error=None):
        with Session(self.engine) as session:
            run = session.get(ReportRun, key)
            if run is None: raise ValueError('Report claim not found')
            run.status, run.snapshot, run.message_id, run.error = status, snapshot, message_id, error
            run.finished_at = datetime.now(timezone.utc)
            session.commit()
