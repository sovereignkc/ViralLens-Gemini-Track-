#!/bin/bash
# ./run.sh  -> http://127.0.0.1:8000   (keys from .env in this folder; see .env.example)
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  if command -v uv >/dev/null; then uv venv -q .venv && uv pip install -q --python .venv/bin/python -r requirements.txt
  else python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt; fi
fi
for f in .env ../../.env; do
  [ -f "$f" ] && { export $(grep -E '^(GEMINI_(PAID_)?API_KEY|YOUTUBE_API_KEY|GEMINI_MODEL)=' "$f" | xargs); break; }
done
exec .venv/bin/uvicorn main:app --host 127.0.0.1 --port "${PORT:-8000}"
