#!/usr/bin/env bash
# Cutctx Codex Plugin Installer
# Usage: bash install.sh [--proxy-url URL] [--port PORT] [--no-mcp]

set -euo pipefail

PORT="${CUTCTX_PORT:-8787}"
PROXY_URL="http://127.0.0.1:${PORT}/v1"
INSTALL_MCP=1
PLUGIN_DIR="$(cd "$(dirname "$0")" && pwd)"

# Parse args
while [[ $# -gt 0 ]]; do
  case $1 in
    --proxy-url) PROXY_URL="$2"; shift 2 ;;
    --port) PORT="$2"; PROXY_URL="http://127.0.0.1:${PORT}/v1"; shift 2 ;;
    --no-mcp) INSTALL_MCP=0; shift ;;
    -h|--help)
      echo "Usage: $0 [--proxy-url URL] [--port PORT] [--no-mcp]"
      echo ""
      echo "Options:"
      echo "  --proxy-url URL   Proxy URL (default: http://127.0.0.1:8787/v1)"
      echo "  --port PORT       Proxy port (default: 8787)"
      echo "  --no-mcp          Skip MCP server installation"
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

echo "Cutctx Codex Plugin Installer"
echo "=============================="

# Determine CLI command (cutctx first, cutctx fallback)
CLI="cutctx"
if ! command -v cutctx &>/dev/null; then
  if command -v cutctx &>/dev/null; then
    CLI="cutctx"
  else
    echo "Error: cutctx CLI not found."
    echo "Install: pip install cutctx-ai"
    exit 1
  fi
fi

# 1. Configure Codex with the durable init path
echo ""
echo "1. Configuring Codex via durable Cutctx init..."

if ${CLI} init -g --port "${PORT}" codex; then
  echo "   ✓ Codex provider and hooks configured"
else
  echo "Error: durable Codex init failed"
  exit 1
fi

# 2. Install MCP server
if [[ $INSTALL_MCP -eq 1 ]]; then
  echo ""
  echo "2. Installing MCP server..."
  if ${CLI} mcp install --agent codex --proxy-url "http://127.0.0.1:${PORT}" 2>/dev/null; then
    echo "   ✓ MCP server installed"
  else
    echo "   ⚠ MCP install failed — run manually: ${CLI} mcp install --agent codex"
  fi
else
  echo ""
  echo "2. Skipping MCP installation (--no-mcp)"
fi

echo ""
echo "3. Ensuring local Cutctx runtime is running..."
if ${CLI} init hook ensure --profile init-user >/dev/null 2>&1; then
  if command -v curl >/dev/null 2>&1 && curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
    echo "   ✓ Cutctx proxy is healthy on http://127.0.0.1:${PORT}"
  else
    echo "   ⚠ Cutctx runtime was asked to start, but health could not be verified on http://127.0.0.1:${PORT}"
    echo "     Codex will not save tokens until the local proxy is reachable."
  fi
else
  echo "   ⚠ Could not auto-start the Cutctx runtime"
  echo "     Run: ${CLI} init hook ensure --profile init-user"
fi

echo ""
echo "=============================="
echo "Installation complete!"
echo ""
echo "Next steps:"
echo "  1. Restart Codex: codex"
echo "  2. Verify the proxy: curl http://127.0.0.1:${PORT}/health"
echo "  3. Codex will route through Cutctx automatically while the local proxy is running"
echo ""
echo "To uninstall: bash $(dirname "$0")/uninstall.sh"
