from __future__ import annotations

from sqlmodel import Session, select

from backend.models import RunnerRecord, utc_now
from backend.schemas import RunnerHeartbeat, RunnerRegister


def register_runner(session: Session, payload: RunnerRegister) -> RunnerRecord:
    now = utc_now()
    runner = session.get(RunnerRecord, payload.runner_id)
    if runner is None:
        runner = RunnerRecord(
            runner_id=payload.runner_id,
            pid=payload.pid,
            hostname=payload.hostname,
            status="ONLINE",
            registered_at=now,
            last_heartbeat_at=now,
        )
    else:
        runner.pid = payload.pid
        runner.hostname = payload.hostname
        runner.status = "ONLINE"
        runner.last_heartbeat_at = now
    session.add(runner)
    session.commit()
    session.refresh(runner)
    return runner


def heartbeat(session: Session, payload: RunnerHeartbeat) -> RunnerRecord:
    register_payload = RunnerRegister(
        runner_id=payload.runner_id,
        pid=payload.pid,
        hostname=payload.hostname,
    )
    return register_runner(session, register_payload)


def list_runners(session: Session) -> list[RunnerRecord]:
    return list(session.exec(select(RunnerRecord).order_by(RunnerRecord.runner_id)).all())
