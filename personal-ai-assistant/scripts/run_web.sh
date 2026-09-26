#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
uvicorn interfaces.web.server:app --host "${WEB_HOST:-0.0.0.0}" --port "${WEB_PORT:-8000}"
