#!/bin/sh
set -e

echo "==> Starting uwu-ai-agent"
exec uvicorn app.main:app --host 0.0.0.0 --port 8100
