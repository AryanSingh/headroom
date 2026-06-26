#!/usr/bin/env bash
# Cutctx plugin setup — checks if cutctx CLI is installed and proxy is running
set -euo pipefail

resolve_cutctx() {
  if [[ -n "${CUTCTX_CLI_PATH:-}" && -x "${CUTCTX_CLI_PATH}" ]]; then
    printf '%s\n' "${CUTCTX_CLI_PATH}"
    return 0
  fi
  if command -v cutctx &>/dev/null; then
    command -v cutctx
    return 0
  fi
  if [[ -x "/Library/Frameworks/Python.framework/Versions/3.13/bin/cutctx" ]]; then
    printf '%s\n' "/Library/Frameworks/Python.framework/Versions/3.13/bin/cutctx"
    return 0
  fi
  return 1
}

if ! CUTCTX_CMD="$(resolve_cutctx)"; then
  echo '{"status":"not_installed","message":"Run: pip install cutctx-ai"}'
  exit 0
fi

# Check if proxy is running
if curl -sf http://127.0.0.1:8787/livez >/dev/null 2>&1; then
  echo '{"status":"ready","proxy":"http://127.0.0.1:8787"}'
else
  echo '{"status":"installed","proxy":"not_running","message":"Starting proxy..."}'
  # Auto-start the proxy in background
  "$CUTCTX_CMD" proxy --port 8787 &>/dev/null &
  PROXY_PID=$!
  # Wait for it to be ready. The first launch can take a few seconds while
  # proxy dependencies initialize, so give it a longer window.
  for i in $(seq 1 40); do
    if curl -sf http://127.0.0.1:8787/livez >/dev/null 2>&1; then
      echo "{\"status\":\"ready\",\"proxy\":\"http://127.0.0.1:8787\",\"pid\":$PROXY_PID}"
      exit 0
    fi
    sleep 0.5
  done
  echo '{"status":"error","message":"Proxy started but not responding on port 8787"}'
fi
