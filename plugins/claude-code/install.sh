#!/usr/bin/env bash
# CutCtx Claude Code Plugin Installer
# Usage: bash install.sh [--proxy-url URL] [--no-mcp]

set -euo pipefail

PROXY_URL="${CUTCTX_PROXY_URL:-http://127.0.0.1:8787}"
INSTALL_MCP=1
PORT="${CUTCTX_PORT:-8787}"

# Parse args
while [[ $# -gt 0 ]]; do
  case $1 in
    --proxy-url) PROXY_URL="$2"; shift 2 ;;
    --port) PORT="$2"; PROXY_URL="http://127.0.0.1:${PORT}"; shift 2 ;;
    --no-mcp) INSTALL_MCP=0; shift ;;
    -h|--help)
      echo "Usage: $0 [--proxy-url URL] [--port PORT] [--no-mcp]"
      echo ""
      echo "Options:"
      echo "  --proxy-url URL   Proxy URL (default: http://127.0.0.1:8787)"
      echo "  --port PORT       Proxy port (default: 8787)"
      echo "  --no-mcp          Skip MCP server installation"
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

echo "CutCtx Claude Code Plugin Installer"
echo "===================================="

# Check prerequisites
if ! command -v headroom &>/dev/null; then
  echo "Error: headroom CLI not found."
  echo "Install: pip install headroom-ai[all]"
  exit 1
fi

# 1. Register MCP server with Claude Code CLI
if [[ $INSTALL_MCP -eq 1 ]]; then
  echo ""
  echo "1. Registering MCP server with Claude Code..."

  # Remove any existing registration first
  claude mcp remove headroom -s user 2>/dev/null || true

  # Register via claude mcp add (writes to ~/.claude.json)
  if claude mcp add headroom -s user -- headroom mcp serve 2>&1; then
    echo "   ✓ MCP server registered (stdio, user scope)"
  else
    echo "   ⚠ claude mcp add failed — trying file fallback..."
    # Fallback: write directly to ~/.claude.json
    if command -v python3 &>/dev/null; then
      python3 -c "
import json, os
config_path = os.path.expanduser('~/.claude.json')
if os.path.exists(config_path):
    with open(config_path) as f:
        config = json.load(f)
else:
    config = {}
servers = config.setdefault('mcpServers', {})
servers['headroom'] = {
    'command': 'headroom',
    'args': ['mcp', 'serve'],
    'env': {}
}
with open(config_path, 'w') as f:
    json.dump(config, f, indent=2)
    f.write('\n')
print('   ✓ MCP server written to ~/.claude.json')
"
    else
      echo "   ✗ Could not register MCP server — add manually:"
      echo "     claude mcp add headroom -s user -- headroom mcp serve"
      exit 1
    fi
  fi

  # Verify
  echo ""
  echo "   Verifying..."
  if claude mcp get headroom 2>&1 | grep -q "headroom"; then
    echo "   ✓ Verified: headroom MCP server is registered"
  else
    echo "   ⚠ Registration may need a Claude Code restart"
  fi
else
  echo ""
  echo "1. Skipping MCP installation (--no-mcp)"
fi

# 2. Set up proxy environment
echo ""
echo "2. Proxy environment..."
echo "   Set ANTHROPIC_BASE_URL=${PROXY_URL} when launching Claude Code"
echo "   Or use: headroom wrap claude (auto-sets env + starts proxy)"

echo ""
echo "===================================="
echo "Installation complete!"
echo ""
echo "To use:"
echo "  Option A (recommended):"
echo "    headroom wrap claude        # starts proxy + launches Claude"
echo ""
echo "  Option B (manual):"
echo "    headroom proxy              # start proxy in background"
echo "    ANTHROPIC_BASE_URL=${PROXY_URL} claude"
echo ""
echo "To uninstall: bash $(dirname "$0")/uninstall.sh"
