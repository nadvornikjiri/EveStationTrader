from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from threading import Lock, Thread
from uuid import uuid4

from .ingestion import IngestionService


@dataclass
class IngestionJobState:
    job_id: str
    status: str
    mode: str
    total_steps: int
    completed_steps: int
    current_label: str
    started_at: str
    finished_at: str | None = None
    error: str | None = None
    results: list[dict[str, object]] = field(default_factory=list)


class IngestionJobManager:
    def __init__(self, ingestion_service: IngestionService) -> None:
        self.ingestion_service = ingestion_service
        self._lock = Lock()
        self._jobs: dict[str, IngestionJobState] = {}

    def start_job(self, *, mode: str, hub_key: str | None, refresh: bool) -> IngestionJobState:
        with self._lock:
            active = self._active_job_locked()
            if active is not None:
                raise ValueError("An ingestion job is already running.")

            hubs = self._targets(mode, hub_key)
            state = IngestionJobState(
                job_id=uuid4().hex,
                status="running",
                mode=mode,
                total_steps=len(hubs),
                completed_steps=0,
                current_label="Queued",
                started_at=_utc_now(),
            )
            self._jobs[state.job_id] = state

        thread = Thread(target=self._run_job, args=(state.job_id, hubs, refresh), daemon=True)
        thread.start()
        return self.get_job(state.job_id)

    def get_job(self, job_id: str) -> IngestionJobState:
        with self._lock:
            state = self._jobs.get(job_id)
            if state is None:
                raise ValueError("Unknown job id.")
            return _copy_state(state)

    def latest_job(self) -> IngestionJobState | None:
        with self._lock:
            if not self._jobs:
                return None
            latest = max(self._jobs.values(), key=lambda item: item.started_at)
            return _copy_state(latest)

    def _run_job(self, job_id: str, hubs: list[object], refresh: bool) -> None:
        try:
            for hub in hubs:
                self._update(job_id, current_label=f"Ingesting {hub.name}")
                result = self.ingestion_service.ingest_hub_region(hub, refresh=refresh)
                self._advance(job_id, result)
            self._finish(job_id)
        except Exception as exc:  # pragma: no cover
            self._fail(job_id, str(exc))

    def _targets(self, mode: str, hub_key: str | None):
        if mode == "known-hubs":
            hubs = []
            seen_regions: set[int] = set()
            for hub in self.ingestion_service.trader_service.known_hubs():
                if hub.region_id in seen_regions:
                    continue
                hubs.append(hub)
                seen_regions.add(hub.region_id)
            return hubs
        if mode == "single-hub":
            return [self.ingestion_service.trader_service.resolve_hub(hub_key, None, None)]
        raise ValueError("Unknown ingestion mode.")

    def _active_job_locked(self) -> IngestionJobState | None:
        for job in self._jobs.values():
            if job.status == "running":
                return job
        return None

    def _update(self, job_id: str, *, current_label: str) -> None:
        with self._lock:
            state = self._jobs[job_id]
            state.current_label = current_label

    def _advance(self, job_id: str, result: dict[str, object]) -> None:
        with self._lock:
            state = self._jobs[job_id]
            state.results.append(result)
            state.completed_steps += 1
            if state.completed_steps < state.total_steps:
                state.current_label = f"Completed {state.completed_steps} of {state.total_steps}"
            else:
                state.current_label = "Finalizing"

    def _finish(self, job_id: str) -> None:
        with self._lock:
            state = self._jobs[job_id]
            state.status = "completed"
            state.current_label = "Complete"
            state.finished_at = _utc_now()

    def _fail(self, job_id: str, error: str) -> None:
        with self._lock:
            state = self._jobs[job_id]
            state.status = "failed"
            state.error = error
            state.current_label = "Failed"
            state.finished_at = _utc_now()


def serialize_job(state: IngestionJobState) -> dict[str, object]:
    payload = asdict(state)
    payload["progress_percent"] = 0 if state.total_steps == 0 else round((state.completed_steps / state.total_steps) * 100, 1)
    return payload


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _copy_state(state: IngestionJobState) -> IngestionJobState:
    return IngestionJobState(
        job_id=state.job_id,
        status=state.status,
        mode=state.mode,
        total_steps=state.total_steps,
        completed_steps=state.completed_steps,
        current_label=state.current_label,
        started_at=state.started_at,
        finished_at=state.finished_at,
        error=state.error,
        results=list(state.results),
    )
