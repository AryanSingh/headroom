#!/usr/bin/env bash
# diagnose_desktop_capture.sh
#
# Live diagnostic for: "cutctx requests from my Claude Desktop / Cowork session
# are not appearing in the dashboard."
#
# Run this on the Mac where the proxy + Claude Desktop actually run:
#   bash scripts/diagnose_desktop_capture.sh
#
# It checks each link in the chain and prints PASS / WARN / FAIL so you can see
# exactly where capture breaks. It is read-only except for one optional test
# request (only sent if you pass --send-test and have an API key set).

set -uo pipefail

PORT="${CUTCTX_PROXY_PORT:-8787}"
BASE="http://127.0.0.1:${PORT}"
SEND_TEST=0
[[ "${1:-}" == "--send-test" ]] && SEND_TEST=1

pass() { printf '  \033[32mPASS\033[0m  %s\n' "$1"; }
warn() { printf '  \033[33mWARN\033[0m  %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; }
hdr()  { printf '\n\033[1m%s\033[0m\n' "$1"; }

hdr "1. Is the cutctx proxy running and reachable on :${PORT}?"
if curl -fsS --max-time 3 "${BASE}/health" >/dev/null 2>&1; then
  pass "Proxy responds on ${BASE}/health"
else
  fail "No proxy on ${BASE}. Start it: cutctx proxy --port ${PORT}"
  warn "If your proxy runs on another port, re-run: CUTCTX_PROXY_PORT=XXXX bash $0"
fi

hdr "2. Does /stats currently show any recent requests?"
STATS="$(curl -fsS --max-time 5 "${BASE}/stats" 2>/dev/null)"
if [[ -n "${STATS}" ]]; then
  COUNT="$(printf '%s' "${STATS}" | python3 -c 'import sys,json;print(len((json.load(sys.stdin) or {}).get("recent_requests") or []))' 2>/dev/null || echo "?")"
  if [[ "${COUNT}" == "0" ]]; then
    warn "/stats reachable but recent_requests is EMPTY — nothing has been captured yet."
  else
    pass "/stats shows ${COUNT} recent request(s)."
    printf '%s' "${STATS}" | python3 -c 'import sys,json
d=json.load(sys.stdin) or {}
for r in (d.get("recent_requests") or [])[-3:]:
    print("        last:", r.get("timestamp"), r.get("provider"), r.get("model"))' 2>/dev/null
  fi
else
  fail "Could not read ${BASE}/stats"
fi

hdr "3. Is request logging enabled and NOT degraded to memory-only?"
# The proxy logs a warning when the request-log file is not writable. Look for it.
LOGHINT="$(printf '%s' "${STATS}" | python3 -c 'import sys,json;d=json.load(sys.stdin) or {};print(d.get("log_requests","unknown"))' 2>/dev/null || echo unknown)"
if [[ "${LOGHINT}" == "False" ]]; then
  fail "log_requests is disabled. Restart proxy WITHOUT --no-request-logging."
else
  pass "Request logging appears enabled (log_requests=${LOGHINT})."
fi
warn "If you see 'Request log file ... is not writable' in the proxy console, logging"
warn "has degraded to memory-only (this build still surfaces live requests from memory)."

hdr "4. Is Claude Desktop's traffic actually being routed INTO the proxy?"
echo "   Claude Desktop's own (first-party) Anthropic traffic does NOT honor"
echo "   ANTHROPIC_BASE_URL. It is only captured via transparent HTTPS intercept."
echo
echo "   a) Environment base-URL routing (covers Claude Code / Codex CLI subprocesses):"
for v in ANTHROPIC_BASE_URL OPENAI_BASE_URL; do
  val="$(launchctl getenv "$v" 2>/dev/null)"
  if [[ -n "${val}" ]]; then pass "$v=${val}"; else warn "$v is not set in the launchd environment"; fi
done
echo
echo "   b) Transparent HTTPS intercept (covers the Claude Desktop app itself):"
if command -v cutctx >/dev/null 2>&1; then
  cutctx intercept status 2>&1 | sed 's/^/        /' || warn "cutctx intercept status failed"
else
  warn "cutctx CLI not on PATH — cannot check intercept status"
fi
if grep -qE '(^|[[:space:]])api\.anthropic\.com' /etc/hosts 2>/dev/null; then
  pass "/etc/hosts redirects api.anthropic.com (intercept likely installed)"
else
  warn "/etc/hosts has no api.anthropic.com entry — desktop-app traffic is NOT intercepted."
  warn "To capture the Claude Desktop app itself: cutctx intercept install (then restart the app)."
fi

if [[ "${SEND_TEST}" == "1" ]]; then
  hdr "5. Sending one test request THROUGH the proxy to confirm capture + logging"
  if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
    BEFORE="$(curl -fsS "${BASE}/stats" | python3 -c 'import sys,json;print(len((json.load(sys.stdin) or {}).get("recent_requests") or []))' 2>/dev/null || echo 0)"
    curl -fsS --max-time 30 "${BASE}/v1/messages" \
      -H "x-api-key: ${ANTHROPIC_API_KEY}" \
      -H "anthropic-version: 2023-06-01" \
      -H "content-type: application/json" \
      -d '{"model":"claude-3-5-haiku-latest","max_tokens":8,"messages":[{"role":"user","content":"ping"}]}' \
      >/dev/null 2>&1 && pass "Test request sent." || warn "Test request failed (check key / model)."
    sleep 1
    AFTER="$(curl -fsS "${BASE}/stats" | python3 -c 'import sys,json;print(len((json.load(sys.stdin) or {}).get("recent_requests") or []))' 2>/dev/null || echo 0)"
    if [[ "${AFTER}" -gt "${BEFORE}" ]]; then
      pass "recent_requests grew ${BEFORE} -> ${AFTER}: capture + logging + display WORK end-to-end."
    else
      fail "recent_requests did not grow. The request reached the proxy but was not logged/displayed."
    fi
  else
    warn "ANTHROPIC_API_KEY not set — skipping live test request."
  fi
else
  hdr "5. (skipped) Re-run with --send-test to send one live request through the proxy."
fi

hdr "Summary"
echo "  • Requests only appear if they physically reach THIS proxy instance on :${PORT}."
echo "  • Claude Desktop APP traffic needs 'cutctx intercept install' (HTTPS capture)."
echo "  • Claude Code / CLI subprocess traffic needs ANTHROPIC_BASE_URL=${BASE}."
echo "  • The dashboard must point at the SAME proxy/port that is capturing."
