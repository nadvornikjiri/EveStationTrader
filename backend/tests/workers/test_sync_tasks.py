from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.workers.scheduler import runner
from app.workers.tasks import sync_tasks


class DummyScheduler:
    def __init__(self) -> None:
        self.jobs: list[tuple[object, str, dict[str, object]]] = []

    def add_job(self, func: object, trigger: str, **kwargs: object) -> None:
        self.jobs.append((func, trigger, kwargs))


def test_rebuild_opportunities_job_delegates_to_sync_service(monkeypatch: pytest.MonkeyPatch) -> None:
    triggered_jobs: list[str] = []

    class FakeSyncService:
        def trigger_job(self, job_type: str) -> SimpleNamespace:
            triggered_jobs.append(job_type)
            return SimpleNamespace(id=42, status="success", records_processed=9)

    monkeypatch.setattr(sync_tasks, "SyncService", lambda: FakeSyncService())

    sync_tasks.rebuild_opportunities_job()

    assert triggered_jobs == ["opportunity_rebuild"]


def test_register_jobs_keeps_heartbeat_and_rebuild_cadence() -> None:
    scheduler = DummyScheduler()

    sync_tasks.register_jobs(scheduler)

    assert [job[1] for job in scheduler.jobs] == ["interval", "interval"]
    heartbeat_job = next(job for job in scheduler.jobs if job[2]["id"] == "heartbeat")
    rebuild_job = next(job for job in scheduler.jobs if job[2]["id"] == "rebuild_opportunities")

    assert heartbeat_job[0] is sync_tasks.heartbeat_job
    assert heartbeat_job[2]["minutes"] == 5
    assert heartbeat_job[2]["replace_existing"] is True
    assert rebuild_job[0] is sync_tasks.rebuild_opportunities_job
    assert rebuild_job[2]["minutes"] == 10
    assert rebuild_job[2]["replace_existing"] is True


def test_runner_main_registers_jobs_and_starts_scheduler(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeScheduler:
        def __init__(self, timezone: str) -> None:
            captured["timezone"] = timezone

        def start(self) -> None:
            captured["started"] = True

    def fake_register_jobs(scheduler: object) -> None:
        captured["registered"] = scheduler

    monkeypatch.setattr(runner, "BlockingScheduler", FakeScheduler)
    monkeypatch.setattr(runner, "register_jobs", fake_register_jobs)

    runner.main()

    assert captured["timezone"] == "UTC"
    assert isinstance(captured["registered"], FakeScheduler)
    assert captured["started"] is True
