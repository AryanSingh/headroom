#!/usr/bin/env bash
# CutCtx plugin setup — checks if cutctx CLI is installed and proxy is running
set -euo pipefail

# Check if cutctx is installed
if ! command -v cutctx &>/dev/null; then
  echo '{"status":"not_installed","message":"Run: pip install headroom-ai"}'
  exit 0
fi

# Check if proxy is running
if curl -sf http://127.0.0.1:8787/livez >/dev/null 2>&1; then
  echo '{"status":"ready","proxy":"http://127.0.0.1:8787"}'
else
  echo '{"status":"installed","proxy":"not_running","message":"Starting proxy..."}'
  # Auto-start the proxy in background
  cutctx proxy --port 8787 &>/dev/null &
  PROXY_PID=$!
  # Wait for it to be ready (max 5 seconds)
  for i in $(seq 1 10); do
    if curl -sf http://127.0.0.1:8787/livez >/dev/null 2>&1; then
      echo "{\"status\":\"ready\",\"proxy\":\"http://127.0.0.1:8787\",\"pid\":$PROXY_PID}"
      exit 0
    fi
    sleep 0.5
  done
  echo '{"status":"error","message":"Proxy started but not responding on port 8787"}'
fi
