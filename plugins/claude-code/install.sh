#!/usr/bin/env bash
# CutCtx Claude Code Plugin Installer
# Usage: bash install.sh [--proxy-url URL] [--no-mcp] [--no-hook]

set -euo pipefail

PROXY_URL="${CUTCTX_PROXY_URL:-http://127.0.0.1:8787}"
INSTALL_MCP=1
INSTALL_HOOK=1
PLUGIN_DIR="$(cd "$(dirname "$0")" && pwd)"

# Parse args
while [[ $# -gt 0 ]]; do
  case $1 in
    --proxy-url) PROXY_URL="$2"; shift 2 ;;
    --no-mcp) INSTALL_MCP=0; shift ;;
    --no-hook) INSTALL_HOOK=0; shift ;;
    -h|--help)
      echo "Usage: $0 [--proxy-url URL] [--no-mcp] [--no-hook]"
      echo ""
      echo "Options:"
      echo "  --proxy-url URL   Proxy URL (default: http://127.0.0.1:8787)"
      echo "  --no-mcp          Skip MCP server installation"
      echo "  --no-hook         Skip hook installation"
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

echo "CutCtx Claude Code Plugin Installer"
echo "===================================="

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

# 1. Install plugin to ~/.claude/plugins/cutctx/
CLAUDE_PLUGINS_DIR="${HOME}/.claude/plugins"
TARGET_DIR="${CLAUDE_PLUGINS_DIR}/cutctx"

echo ""
echo "1. Installing plugin to ${TARGET_DIR}..."
mkdir -p "${TARGET_DIR}"
cp -r "${PLUGIN_DIR}/.claude-plugin" "${TARGET_DIR}/"
cp -r "${PLUGIN_DIR}/hooks" "${TARGET_DIR}/"
cp "${PLUGIN_DIR}/README.md" "${TARGET_DIR}/"
echo "   ✓ Plugin files installed"

# 2. Register plugin in ~/.claude/settings.json
SETTINGS_FILE="${HOME}/.claude/settings.json"
echo ""
echo "2. Registering plugin in ${SETTINGS_FILE}..."

if command -v python3 &>/dev/null; then
  python3 -c "
import json, os, sys

settings_path = os.path.expanduser('~/.claude/settings.json')
os.makedirs(os.path.dirname(settings_path), exist_ok=True)

if os.path.exists(settings_path):
    with open(settings_path) as f:
        settings = json.load(f)
else:
    settings = {}

plugins = settings.get('plugins', {})
plugins['cutctx'] = {
    'path': '${TARGET_DIR}',
    'enabled': True
}
settings['plugins'] = plugins

with open(settings_path, 'w') as f:
    json.dump(settings, f, indent=2)
    f.write('\n')

print('   ✓ Plugin registered in settings.json')
"
else
  echo "   ⚠ python3 not found — add plugin to settings.json manually"
fi

# 3. Install MCP server
if [[ $INSTALL_MCP -eq 1 ]]; then
  echo ""
  echo "3. Installing MCP server..."
  if ${CLI} mcp install --agent claude --proxy-url "${PROXY_URL}" 2>/dev/null; then
    echo "   ✓ MCP server installed"
  else
    echo "   ⚠ MCP install failed — run manually: ${CLI} mcp install --agent claude"
  fi
else
  echo ""
  echo "3. Skipping MCP installation (--no-mcp)"
fi

# 4. Install hooks
if [[ $INSTALL_HOOK -eq 1 ]]; then
  echo ""
  echo "4. Installing hooks..."
  # Hooks are already in the plugin directory
  # Claude Code reads hooks from .claude-plugin/hooks.json
  echo "   ✓ Hooks installed (via plugin directory)"
fi

echo ""
echo "===================================="
echo "Installation complete!"
echo ""
echo "Next steps:"
echo "  1. Start the proxy: ${CLI} proxy"
echo "  2. Restart Claude Code to pick up the plugin"
echo "  3. The plugin will auto-start the proxy on future sessions"
echo ""
echo "To uninstall: bash $(dirname "$0")/uninstall.sh"
