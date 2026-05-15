from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_gateway_token
from app.db.base import Base
from app.db.models import Gateway, Pipeline, Sink
from app.routers.gateways import get_gateway_config


def _session_factory():
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def test_get_gateway_config_includes_events_and_aggregates():
    session_factory = _session_factory()

    with session_factory() as db:
        gateway = Gateway(
            gateway_id="gateway-demo-01",
            hostname="gateway-demo-01.local",
            approved=True,
            status="approved",
        )
        db.add(gateway)
        db.commit()
        db.refresh(gateway)

        pipeline = Pipeline(
            name="demo-pipeline",
            gateway_id=gateway.id,
            config={
                "adapters": [
                    {
                        "adapter_id": "modbus-demo-01",
                        "adapter_type": "modbus_tcp",
                        "config": {
                            "output": {
                                "topic": "telemetry.raw",
                                "events_topic": "events.raw",
                                "asset_id": "demo_sensor_01",
                            }
                        },
                    }
                ],
                "validation": {"enabled": True, "raw_topic": "telemetry.raw", "clean_topic": "telemetry.clean"},
                "events": {"enabled": True, "raw_topic": "events.raw", "clean_topic": "events.clean", "dlq_topic": "dlq.events"},
                "aggregates": {"enabled": True, "source_topic": "telemetry.clean"},
            },
        )
        db.add(pipeline)
        db.commit()
        db.refresh(pipeline)

        sink = Sink(
            pipeline_id=pipeline.id,
            sink_type="timescaledb",
            config={"topic": "events.clean", "table": "events", "message_format": "event"},
            status="active",
        )
        db.add(sink)
        db.commit()

        token, _ = create_gateway_token(gateway.gateway_id)
        payload = get_gateway_config(gateway.gateway_id, token=token, db=db)

        assert payload["gateway_id"] == "gateway-demo-01"
        assert payload["validation"]["clean_topic"] == "telemetry.clean"
        assert payload["events"]["clean_topic"] == "events.clean"
        assert payload["events"]["dlq_topic"] == "dlq.events"
        assert payload["aggregates"]["source_topic"] == "telemetry.clean"
        assert payload["adapters"][0]["config"]["output"]["events_topic"] == "events.raw"
        assert payload["sinks"][0]["config"]["message_format"] == "event"
