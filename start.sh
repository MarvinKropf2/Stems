#!/usr/bin/env bash
# Boot the Stems backend (FastAPI :8000) and frontend (Vite :5173) together.
# Ctrl+C stops both.
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -d "$ROOT/backend/.venv" ]; then
  echo "Backend venv missing. Run the one-time setup first (see README.md)."
  exit 1
fi

cleanup() {
  echo
  echo "Stopping…"
  kill 0
}
trap cleanup EXIT INT TERM

# Corporate proxy CA bundle so model downloads (Hugging Face / torch.hub) work.
# Harmless if the file is absent (verification just falls back to system store).
CA_BUNDLE="$HOME/.certs/six-combined-ca.pem"

echo "Starting backend on http://localhost:8000 …"
(
  cd "$ROOT/backend"
  source .venv/bin/activate
  if [ -f "$CA_BUNDLE" ]; then
    export SSL_CERT_FILE="$CA_BUNDLE"
    export REQUESTS_CA_BUNDLE="$CA_BUNDLE"
    export CURL_CA_BUNDLE="$CA_BUNDLE"
  fi
  exec uvicorn main:app --host 127.0.0.1 --port 8000
) &

echo "Starting frontend on http://localhost:5173 …"
(
  cd "$ROOT/frontend"
  exec npm run dev
) &

wait
