from datetime import date, datetime, timezone
from sqlalchemy import String, Date, DateTime, JSON, Boolean, UniqueConstraint, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Mapped, mapped_column, Session
from .storage import Base, engine
from .live_domain import LiveSnapshot


class MakeSnapshot(Base):
    __tablename__ = 'make_snapshots'
    __table_args__ = (UniqueConstraint('account_id', 'report_date', 'fetched_at', name='make_snapshot_identity'),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(64), index=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict] = mapped_column(JSON)
    is_test: Mapped[bool] = mapped_column(Boolean, default=False)


class SnapshotConflict(ValueError): pass


def save_snapshot(row, is_test=False):
    digest = row.digest()
    with Session(engine()) as session:
        statement = insert(MakeSnapshot).values(id=digest, account_id=row.account_id, report_date=row.date_start,
                  fetched_at=row.fetched_at, received_at=datetime.now(timezone.utc), payload=row.model_dump(mode='json'), is_test=is_test)
        result = session.execute(statement.on_conflict_do_nothing().returning(MakeSnapshot.id)).scalar_one_or_none()
        if result:
            session.commit(); return True
        existing = session.scalar(select(MakeSnapshot).where(MakeSnapshot.account_id == row.account_id,
            MakeSnapshot.report_date == row.date_start, MakeSnapshot.fetched_at == row.fetched_at))
        if existing is None or existing.id != digest or existing.is_test != is_test:
            raise SnapshotConflict('Snapshot identity has conflicting values')
        return False


def snapshots(account, start=None, end=None):
    with Session(engine()) as session:
        query = select(MakeSnapshot).where(MakeSnapshot.account_id == account)
        # Keep one overall latest row even when a filter selects an older/empty
        # period, so freshness metadata cannot be inferred from browser polling.
        latest = session.scalar(query.order_by(MakeSnapshot.fetched_at.desc()).limit(1))
        if latest is None: return []
        filtered = query
        if start: filtered = filtered.where(MakeSnapshot.report_date >= start)
        if end: filtered = filtered.where(MakeSnapshot.report_date <= end)
        rows = list(session.scalars(filtered))
        if all(row.id != latest.id for row in rows): rows.append(latest)
        return [(LiveSnapshot.model_validate(row.payload), row.received_at, row.is_test) for row in rows]
