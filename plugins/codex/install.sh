#!/usr/bin/env bash
# CutCtx Codex Plugin Installer
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

echo "CutCtx Codex Plugin Installer"
echo "=============================="

# Check prerequisites
if ! command -v cutctx &>/dev/null && ! command -v headroom &>/dev/null; then
  echo "Error: cutctx/headroom CLI not found."
  echo "Install: pip install cutctx-ai"
  exit 1
fi

# Determine CLI command
CLI="cutctx"
if ! command -v cutctx &>/dev/null; then
  CLI="headroom"
fi

# 1. Configure Codex provider in ~/.codex/config.toml
CODEX_CONFIG="${HOME}/.codex/config.toml"
echo ""
echo "1. Configuring Codex provider in ${CODEX_CONFIG}..."

MARKER_START="# --- CutCtx persistent provider ---"
MARKER_END="# --- end CutCtx persistent provider ---"

# Ensure directory exists
mkdir -p "$(dirname "${CODEX_CONFIG}")"

# Build the provider section
PROVIDER_SECTION="${MARKER_START}
model_provider = \"cutctx\"
openai_base_url = \"${PROXY_URL}\"

[model_providers.cutctx]
name = \"CutCtx persistent proxy\"
base_url = \"${PROXY_URL}\"
supports_websockets = true
${MARKER_END}
"

if [[ -f "${CODEX_CONFIG}" ]]; then
  # Check if already installed
  if grep -q "${MARKER_START}" "${CODEX_CONFIG}" 2>/dev/null; then
    echo "   ✓ CutCtx provider already configured — updating"
    # Remove old block and append new
    if command -v python3 &>/dev/null; then
      python3 -c "
import re
with open('${CODEX_CONFIG}') as f:
    content = f.read()
pattern = re.compile(r'${MARKER_START}.*?${MARKER_END}', re.DOTALL)
content = pattern.sub('', content).rstrip()
with open('${CODEX_CONFIG}', 'w') as f:
    f.write(content + '\n\n${PROVIDER_SECTION}\n')
"
    else
      # Fallback: sed-based replacement
      sed -i.bak "/${MARKER_START//\//\\/}/,/${MARKER_END//\//\\/}/d" "${CODEX_CONFIG}"
      rm -f "${CODEX_CONFIG}.bak"
      echo "" >> "${CODEX_CONFIG}"
      echo "${PROVIDER_SECTION}" >> "${CODEX_CONFIG}"
    fi
  else
    # Append new block
    echo "" >> "${CODEX_CONFIG}"
    echo "${PROVIDER_SECTION}" >> "${CODEX_CONFIG}"
  fi
else
  # Create new config
  echo "${PROVIDER_SECTION}" > "${CODEX_CONFIG}"
fi

echo "   ✓ Codex provider configured"

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
echo "=============================="
echo "Installation complete!"
echo ""
echo "Next steps:"
echo "  1. Start the proxy: ${CLI} proxy"
echo "  2. Start Codex: codex"
echo "  3. Codex will route through CutCtx proxy automatically"
echo ""
echo "To uninstall: bash $(dirname "$0")/uninstall.sh"
