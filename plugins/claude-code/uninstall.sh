#!/usr/bin/env bash
# CutCtx Claude Code Plugin Uninstaller
# Usage: bash uninstall.sh

set -euo pipefail

echo "CutCtx Claude Code Plugin Uninstaller"
echo "======================================"

# 1. Remove plugin directory
TARGET_DIR="${HOME}/.claude/plugins/cutctx"
if [[ -d "${TARGET_DIR}" ]]; then
  echo "1. Removing plugin directory..."
  rm -rf "${TARGET_DIR}"
  echo "   ✓ Removed ${TARGET_DIR}"
else
  echo "1. Plugin directory not found — skipping"
fi

# 2. Remove from settings.json
SETTINGS_FILE="${HOME}/.claude/settings.json"
echo ""
echo "2. Removing from ${SETTINGS_FILE}..."

if command -v python3 &>/dev/null && [[ -f "${SETTINGS_FILE}" ]]; then
  python3 -c "
import json, os

settings_path = os.path.expanduser('~/.claude/settings.json')
if not os.path.exists(settings_path):
    print('   Settings file not found — skipping')
    exit(0)

with open(settings_path) as f:
    settings = json.load(f)

plugins = settings.get('plugins', {})
if 'cutctx' in plugins:
    del plugins['cutctx']
    settings['plugins'] = plugins
    with open(settings_path, 'w') as f:
        json.dump(settings, f, indent=2)
        f.write('\n')
    print('   ✓ Removed cutctx from settings.json')
else:
    print('   cutctx not in settings.json — skipping')
"
else
  echo "   ⚠ python3 not found — remove cutctx from settings.json manually"
fi

# 3. Uninstall MCP server
echo ""
echo "3. Removing MCP server..."
CLI="cutctx"
if ! command -v cutctx &>/dev/null; then
  CLI="headroom"
fi

if command -v ${CLI} &>/dev/null; then
  if ${CLI} mcp uninstall 2>/dev/null; then
    echo "   ✓ MCP server removed"
  else
    echo "   ⚠ MCP uninstall failed — run manually: ${CLI} mcp uninstall"
  fi
else
  echo "   ⚠ CLI not found — remove MCP config manually"
fi

echo ""
echo "======================================"
echo "Uninstall complete!"
echo ""
echo "The proxy is still running if you started it separately."
echo "Kill it with: pkill -f 'cutctx proxy' or 'kill \$(lsof -ti:8787)'"
