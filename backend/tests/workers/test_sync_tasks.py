from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.workers.scheduler import runner
from app.workers.tasks import sync_tasks


class DummyScheduler:
    def __init__(self) -> None:
        self.jobs: list[tuple[object, str, dict[str, object]]] = []
        self._removed: list[str] = []

    def add_job(self, func: object, trigger: str, **kwargs: object) -> None:
        self.jobs.append((func, trigger, kwargs))

    def remove_job(self, job_id: str) -> None:
        self._removed.append(job_id)


def _make_fake_config(job_type: str, trigger_type: str, **kwargs: object) -> SimpleNamespace:
    return SimpleNamespace(
        job_type=job_type,
        label=job_type,
        trigger_type=trigger_type,
        interval_minutes=kwargs.get("interval_minutes"),
        cron_hour=kwargs.get("cron_hour"),
        cron_minute=kwargs.get("cron_minute", 0),
        enabled=kwargs.get("enabled", True),
        updated_at=kwargs.get("updated_at"),
    )


def _default_configs() -> list[SimpleNamespace]:
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    return [
        _make_fake_config("esi_market_orders_sync", "interval", interval_minutes=10, updated_at=now),
        _make_fake_config("everef_history_sync", "cron", cron_hour=8, cron_minute=0, updated_at=now),
        _make_fake_config("adam4eve_sync", "cron", cron_hour=9, cron_minute=0, updated_at=now),
        _make_fake_config("character_sync", "interval", interval_minutes=15, updated_at=now),
        _make_fake_config("opportunity_rebuild", "interval", interval_minutes=60, updated_at=now),
    ]


def test_sync_esi_market_orders_job_delegates_to_sync_service(monkeypatch: pytest.MonkeyPatch) -> None:
    triggered_jobs: list[str] = []

    class FakeSyncService:
        def trigger_job(self, job_type: str) -> SimpleNamespace:
            triggered_jobs.append(job_type)
            return SimpleNamespace(id=42, status="success", records_processed=9)

    monkeypatch.setattr(sync_tasks, "SyncService", lambda: FakeSyncService())

    sync_tasks.sync_esi_market_orders_job()

    assert triggered_jobs == ["esi_market_orders_sync"]


def test_sync_adam4eve_job_delegates_to_sync_service(monkeypatch: pytest.MonkeyPatch) -> None:
    triggered_jobs: list[str] = []

    class FakeSyncService:
        def trigger_job(self, job_type: str) -> SimpleNamespace:
            triggered_jobs.append(job_type)
            return SimpleNamespace(id=42, status="success", records_processed=9)

    monkeypatch.setattr(sync_tasks, "SyncService", lambda: FakeSyncService())

    sync_tasks.sync_adam4eve_job()

    assert triggered_jobs == ["adam4eve_sync"]


def test_opportunity_rebuild_job_delegates_to_sync_service(monkeypatch: pytest.MonkeyPatch) -> None:
    triggered_jobs: list[str] = []

    class FakeSyncService:
        def trigger_job(self, job_type: str) -> SimpleNamespace:
            triggered_jobs.append(job_type)
            return SimpleNamespace(id=42, status="success", records_processed=9)

    monkeypatch.setattr(sync_tasks, "SyncService", lambda: FakeSyncService())

    sync_tasks.opportunity_rebuild_job()

    assert triggered_jobs == ["opportunity_rebuild"]


def test_register_jobs_loads_configs_from_db(monkeypatch: pytest.MonkeyPatch) -> None:
    """register_jobs reads schedule configs from DB and registers them."""
    configs = _default_configs()

    class FakeSession:
        def scalars(self, stmt: object) -> SimpleNamespace:
            return SimpleNamespace(all=lambda: configs)

        def close(self) -> None:
            pass

    monkeypatch.setattr(sync_tasks, "SessionLocal", FakeSession)
    scheduler = DummyScheduler()

    sync_tasks.register_jobs(scheduler)

    job_ids = {job[2]["id"] for job in scheduler.jobs if "id" in job[2]}
    # Heartbeat + 5 configurable jobs + _config_reload
    assert "heartbeat" in job_ids
    assert "esi_market_orders_sync" in job_ids
    assert "everef_history_sync" in job_ids
    assert "adam4eve_sync" in job_ids
    assert "character_sync" in job_ids
    assert "opportunity_rebuild" in job_ids
    assert "_config_reload" in job_ids

    # Verify correct trigger types
    esi_job = next(j for j in scheduler.jobs if j[2].get("id") == "esi_market_orders_sync")
    assert esi_job[1] == "interval"
    assert esi_job[2]["minutes"] == 10

    everef_job = next(j for j in scheduler.jobs if j[2].get("id") == "everef_history_sync")
    assert everef_job[1] == "cron"
    assert everef_job[2]["hour"] == 8
    assert everef_job[2]["minute"] == 0

    opportunity_job = next(j for j in scheduler.jobs if j[2].get("id") == "opportunity_rebuild")
    assert opportunity_job[1] == "interval"
    assert opportunity_job[2]["minutes"] == 60


def test_register_jobs_falls_back_when_db_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """When DB is unreachable, register_jobs uses hardcoded fallback configs."""

    class FailingSession:
        def scalars(self, stmt: object) -> None:
            raise RuntimeError("DB unavailable")

        def close(self) -> None:
            pass

    monkeypatch.setattr(sync_tasks, "SessionLocal", FailingSession)
    scheduler = DummyScheduler()

    sync_tasks.register_jobs(scheduler)

    job_ids = {job[2]["id"] for job in scheduler.jobs if "id" in job[2]}
    assert "heartbeat" in job_ids
    assert "esi_market_orders_sync" in job_ids
    assert "opportunity_rebuild" in job_ids


def test_disabled_job_is_removed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A disabled config removes the job from the scheduler."""
    from datetime import UTC, datetime

    config = _make_fake_config(
        "character_sync", "interval",
        interval_minutes=15,
        enabled=False,
        updated_at=datetime.now(UTC),
    )
    scheduler = DummyScheduler()
    sync_tasks._apply_schedule(scheduler, config)  # type: ignore[arg-type]

    assert "character_sync" in scheduler._removed
    assert not any(j[2].get("id") == "character_sync" for j in scheduler.jobs)


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
