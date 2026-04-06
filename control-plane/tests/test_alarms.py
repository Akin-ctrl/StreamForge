from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Alarm, Gateway
from app.routers.alarms import ingest_alarm
from app.schemas.alarms import AlarmIngestRequest


def _session_factory():
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def test_ingest_alarm_accepts_aware_datetimes_and_clears_existing_alarm():
    session_factory = _session_factory()

    with session_factory() as db:
        gateway = Gateway(
            gateway_id="gateway-demo-01",
            hostname="gateway-demo-01",
            approved=True,
            status="approved",
        )
        db.add(gateway)
        db.commit()
        db.refresh(gateway)

        raised_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        active = AlarmIngestRequest(
            alarm_id="alarm-01",
            asset_id="boiler-01",
            type="temperature_threshold",
            severity="CRITICAL",
            state="ACTIVE",
            message="Temperature exceeded threshold",
            raised_at=raised_at,
            value=120.0,
            threshold=100.0,
            unit="C",
        )
        active_item = ingest_alarm(active, db=db, gateway=gateway)

        assert active_item.state == "ACTIVE"
        assert active_item.raised_at.tzinfo == timezone.utc

        cleared_at = raised_at + timedelta(minutes=2)
        cleared = AlarmIngestRequest(
            alarm_id="alarm-01",
            asset_id="boiler-01",
            type="temperature_threshold",
            severity="CRITICAL",
            state="CLEARED",
            message="Temperature recovered",
            raised_at=raised_at,
            cleared_at=cleared_at,
            value=80.0,
            threshold=100.0,
            unit="C",
        )
        cleared_item = ingest_alarm(cleared, db=db, gateway=gateway)

        assert cleared_item.state == "CLEARED"
        assert cleared_item.cleared_at == cleared_at
        assert cleared_item.cleared_at.tzinfo == timezone.utc
        assert cleared_item.duration_seconds == 120

        stored_alarm = db.execute(select(Alarm).where(Alarm.alarm_id == "alarm-01")).scalar_one()
        assert stored_alarm.state == "CLEARED"
        assert stored_alarm.cleared_at == cleared_at.replace(tzinfo=None)
        assert stored_alarm.duration_seconds == 120
