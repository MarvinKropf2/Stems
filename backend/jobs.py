"""In-memory job registry + a single background worker that runs separations.

Jobs are processed one at a time (Demucs is CPU/GPU heavy), so uploads return
immediately and the queue drains in the background.
"""
from __future__ import annotations

import queue
import threading
import traceback
from dataclasses import dataclass, field
from pathlib import Path

import separator

DATA_DIR = Path(__file__).parent / "data"


@dataclass
class Job:
    id: str
    filename: str  # original upload filename
    input_path: Path
    status: str = "queued"  # queued | processing | done | error
    error: str | None = None
    stems: list[str] = field(default_factory=list)

    @property
    def stems_dir(self) -> Path:
        return DATA_DIR / self.id / "stems"

    @property
    def out_dir(self) -> Path:
        return DATA_DIR / self.id / "out"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "filename": self.filename,
            "status": self.status,
            "error": self.error,
            "stems": self.stems,
        }


_jobs: dict[str, Job] = {}
_lock = threading.Lock()
_work: "queue.Queue[str]" = queue.Queue()


def add_job(job: Job) -> None:
    with _lock:
        _jobs[job.id] = job
    _work.put(job.id)


def get_job(job_id: str) -> Job | None:
    with _lock:
        return _jobs.get(job_id)


def all_jobs() -> list[Job]:
    with _lock:
        return list(_jobs.values())


def _worker() -> None:
    while True:
        job_id = _work.get()
        job = get_job(job_id)
        if job is None:
            _work.task_done()
            continue
        try:
            job.status = "processing"
            written = separator.separate(job.input_path, job.stems_dir)
            job.stems = written
            job.status = "done"
        except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
            job.status = "error"
            job.error = str(exc)
            traceback.print_exc()
        finally:
            _work.task_done()


def start_worker() -> None:
    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
