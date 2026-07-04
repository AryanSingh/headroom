#!/bin/bash
# Cutctx Proxy Restart Script
# Run this in a SEPARATE terminal window
# Usage: bash restart-proxy.sh

set -e

ADMIN_KEY=$(cat ~/.cutctx/admin_key.txt 2>/dev/null || echo "dev-admin-key-change-in-prod")
PORT=8787
HOST=127.0.0.1

echo "=== Cutctx Proxy Restart ==="
echo "Port: $PORT"
echo "Admin key: ${ADMIN_KEY:0:8}..."

# Kill existing proxy on the port
PID=$(lsof -ti tcp:$PORT 2>/dev/null || true)
if [ -n "$PID" ]; then
  echo "Killing existing proxy (PID: $PID)..."
  kill "$PID" 2>/dev/null || true
  sleep 2
  # Force kill if still alive
  if kill -0 "$PID" 2>/dev/null; then
    kill -9 "$PID" 2>/dev/null || true
    sleep 1
  fi
  echo "Old proxy stopped."
fi

# Verify the port is free
if lsof -ti tcp:$PORT >/dev/null 2>&1; then
  echo "ERROR: Port $PORT is still in use. Cannot start proxy."
  exit 1
fi

echo "Starting new proxy..."

# Start the proxy with admin key
CUTCTX_ADMIN_API_KEY="$ADMIN_KEY" \
CUTCTX_PROXY_HOST="$HOST" \
CUTCTX_PROXY_PORT="$PORT" \
CUTCTX_LOG_LEVEL=INFO \
nohup "$(which cutctx)" proxy \
  --host "$HOST" \
  --port "$PORT" \
  > /tmp/cutctx_restart.log 2>&1 &

NEW_PID=$!
echo "New proxy PID: $NEW_PID"

# Wait for it to be ready
echo -n "Waiting for proxy..."
for i in $(seq 1 30); do
  sleep 1
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://$HOST:$PORT/health 2>/dev/null || echo "000")
  if [ "$STATUS" = "200" ]; then
    echo " READY!"
    break
  fi
  echo -n "."
done
echo ""

# Verify dashboard access
echo ""
echo "=== Verification ==="
echo "Health:  $(curl -s http://$HOST:$PORT/health | python3 -c 'import sys,json;d=json.load(sys.stdin);print(f\"{d[\"status\"]} v{d[\"version\"]}\")' 2>/dev/null || echo 'FAIL')"
echo "Dashboard: $(curl -s -w '%{http_code}' -o /dev/null -H 'Authorization: Bearer '$ADMIN_KEY http://$HOST:$PORT/dashboard 2>/dev/null || echo 'FAIL')"
echo "Stats:    $(curl -s -H 'Authorization: Bearer '$ADMIN_KEY http://$HOST:$PORT/stats 2>/dev/null | python3 -c 'import sys,json;d=json.load(sys.stdin);print(f\"{d[\"summary\"][\"saved\"]} saved, {d[\"requests\"][\"total\"]} requests\")' 2>/dev/null || echo 'no data')"

echo ""
echo "Dashboard URL: http://$HOST:$PORT/dashboard"
echo "Admin key: $ADMIN_KEY"
echo ""
echo "Proxy is running (PID: $NEW_PID)."
echo "To view logs: tail -f /tmp/cutctx_restart.log"
echo "To stop: kill $NEW_PID"
