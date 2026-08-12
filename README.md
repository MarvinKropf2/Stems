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

The app runs on **Linux/WSL and macOS** (and Windows via WSL). It auto-detects the
best available device: NVIDIA **CUDA**, Apple Silicon **MPS** (Metal GPU), or **CPU**.

## One-time setup

### 0. Get the code

Clone the repo (needs [git](https://git-scm.com) — preinstalled on macOS, or `brew install git`):

```bash
git clone https://github.com/MarvinKropf2/Stems.git
cd Stems
```

> No git? Download the ZIP from the GitHub page (**Code → Download ZIP**), unzip it,
> and `cd` into the folder in Terminal instead.

### 1. System packages

**Linux / WSL (Ubuntu):**

```bash
sudo apt update && sudo apt install -y ffmpeg python3-pip python3-venv
```

**macOS** (with [Homebrew](https://brew.sh)):

```bash
brew install ffmpeg python node
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

> **Note (macOS):** on Apple Silicon the default `pip install -r requirements.txt`
> gives you a PyTorch build with **MPS** GPU support — separation runs in seconds
> instead of minutes. Nothing extra to configure; the app uses it automatically.
>
> **Note (Linux, CPU-only):** if `pip install -r requirements.txt` pulls a large
> CUDA PyTorch you don't need, install the CPU build first:
> `pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu`

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
2. Each song shows progress while Demucs runs (seconds on a GPU/Apple Silicon,
   a few minutes on CPU).
3. When done, tick the stems you want, pick WAV or MP3, and download the combined file.
   Quick buttons for **Instrumental** and **Acapella** are provided too.

## Troubleshooting

Hitting an error during setup? See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) —
covers the `npm install` SIX-Artifactory error and git "divergent branches" on pull.

## Notes

- **Speed depends on hardware.** The app auto-selects NVIDIA CUDA → Apple Silicon
  MPS → CPU, in that order. GPU/Apple Silicon: seconds per song. CPU: a few minutes.
- Generated files live under `backend/data/` (gitignored). Delete that folder to
  reclaim space.
