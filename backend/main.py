"""FastAPI app: upload songs, poll job status, download combined stems."""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

import jobs
import separator
from jobs import DATA_DIR, Job

app = FastAPI(title="Stems")

# Not strictly needed (Vite proxies /api), but harmless and helps if the frontend
# is ever served from another origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    jobs.start_worker()


@app.post("/api/upload")
async def upload(files: list[UploadFile] = File(...)) -> list[dict]:
    created = []
    for f in files:
        job_id = uuid.uuid4().hex[:12]
        job_dir = DATA_DIR / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        suffix = Path(f.filename or "song").suffix or ".mp3"
        input_path = job_dir / f"input{suffix}"
        with open(input_path, "wb") as out:
            out.write(await f.read())

        job = Job(id=job_id, filename=f.filename or f"song{suffix}", input_path=input_path)
        jobs.add_job(job)
        created.append(job.to_dict())
    return created


@app.get("/api/jobs")
def list_jobs() -> list[dict]:
    return [j.to_dict() for j in jobs.all_jobs()]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    return job.to_dict()


@app.get("/api/jobs/{job_id}/stem/{name}")
def get_stem(job_id: str, name: str) -> FileResponse:
    """Serve a single raw stem WAV (used by the browser preview mixer)."""
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    if job.status != "done" or name not in job.stems:
        raise HTTPException(404, "stem not available")
    path = separator.stem_path(job.stems_dir, name)
    if not path.exists():
        raise HTTPException(404, "stem file missing")
    return FileResponse(str(path), media_type="audio/wav")


def _label(stem_names: list[str]) -> str:
    """A friendly label for the chosen stem combination."""
    s = set(stem_names)
    if s == {"drums", "bass", "other"}:
        return "Instrumental"
    if s == {"vocals"}:
        return "Acapella"
    # canonical order
    order = ["vocals", "drums", "bass", "other"]
    return "+".join(n for n in order if n in s)


@app.get("/api/jobs/{job_id}/download")
def download(
    job_id: str,
    stems: str = Query(..., description="comma-separated stem names"),
    format: str = Query("wav", pattern="^(wav|mp3)$"),
) -> FileResponse:
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    if job.status != "done":
        raise HTTPException(409, f"job not ready (status: {job.status})")

    requested = [s.strip() for s in stems.split(",") if s.strip()]
    valid = set(job.stems)
    chosen = [s for s in requested if s in valid]
    if not chosen:
        raise HTTPException(400, "no valid stems requested")

    label = _label(chosen)
    base = Path(job.filename).stem

    # Filename tag like " [128 8A]" when BPM/key are known.
    tag_bits = " ".join(str(x) for x in (job.bpm, job.key) if x)
    suffix = f" [{tag_bits}]" if tag_bits else ""
    out_name = f"{base} ({label}){suffix}.{format}"
    out_path = job.out_dir / out_name

    try:
        separator.combine(job.stems_dir, chosen, out_path, fmt=format)
        # Carry source tags/artwork + detected BPM/key into the output.
        meta = separator.read_source_meta(job.input_path, fallback_title=base)
        meta["title"] = f"{meta['title']} ({label})"
        meta["bpm"] = job.bpm
        meta["key"] = job.key
        separator.tag_output(out_path, format, meta)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"combine failed: {exc}") from exc

    media = "audio/wav" if format == "wav" else "audio/mpeg"
    return FileResponse(str(out_path), media_type=media, filename=out_name)
