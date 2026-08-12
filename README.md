# Stems

Local web app to extract high-quality stems from your songs (MP3/WAV/FLAC/…) using
[Demucs](https://github.com/facebookresearch/demucs), then recombine any subset of
the 4 stems into a single ready-to-play file for Rekordbox (or anything else).

- Separates each song into **vocals / drums / bass / other**
- Tick any combination → download **one file** (e.g. Instrumental = drums+bass+other,
  Acapella = vocals only, or any custom mix)
- Download as **WAV (lossless)** or **MP3 320k**
- Multi-file batch upload
- Runs **100% locally** — no cloud, no cost, nothing leaves your machine

> Why not just use Rekordbox's built-in STEMS? That runs a smaller real-time model
> and can't import pre-made stems. Demucs (offline) gives noticeably better quality;
> you bounce the combo you want into a normal file and load it into Rekordbox.

## Architecture

- **Backend** — Python + FastAPI + Demucs. Separates songs on a background worker,
  serves stems, and sums selected stems into WAV/MP3 on download.
- **Frontend** — Vite + React (TypeScript). Drag-and-drop upload, live progress,
  per-song stem picker + format toggle.

## One-time setup

### 1. System packages (WSL/Ubuntu)

```bash
sudo apt update && sudo apt install -y ffmpeg python3-pip python3-venv
```

`ffmpeg` is required for reading MP3s and encoding MP3 output.

### 2. Backend Python environment

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

> The first separation downloads the `htdemucs` model weights (~few hundred MB).
> This happens once and needs an internet connection.

### 3. Frontend dependencies

```bash
cd frontend
npm install
```

## Running

From the project root:

```bash
bash start.sh
```

Then open **http://localhost:5173**.

`start.sh` boots the FastAPI backend on `:8000` and the Vite dev server on `:5173`
(Vite proxies `/api/*` to the backend). Press `Ctrl+C` to stop both.

## Usage

1. Drag songs onto the dropzone (or click to browse). Multiple files are queued.
2. Each song shows progress while Demucs runs (CPU: a few minutes per song).
3. When done, tick the stems you want, pick WAV or MP3, and download the combined file.
   Quick buttons for **Instrumental** and **Acapella** are provided too.

## Notes

- No GPU here → CPU separation (a few minutes per song). If you later add an NVIDIA
  GPU, it's used automatically.
- Generated files live under `backend/data/` (gitignored). Delete that folder to
  reclaim space.
