#!/usr/bin/env bash
# CutCtx Codex Plugin Uninstaller
# Usage: bash uninstall.sh

set -euo pipefail

echo "CutCtx Codex Plugin Uninstaller"
echo "================================"

CODEX_CONFIG="${HOME}/.codex/config.toml"
MARKER_START="# --- CutCtx persistent provider ---"
MARKER_END="# --- end CutCtx persistent provider ---"

# 1. Remove provider from config
echo ""
echo "1. Removing CutCtx provider from ${CODEX_CONFIG}..."

if [[ -f "${CODEX_CONFIG}" ]] && grep -q "${MARKER_START}" "${CODEX_CONFIG}" 2>/dev/null; then
  if command -v python3 &>/dev/null; then
    python3 -c "
import re
with open('${CODEX_CONFIG}') as f:
    content = f.read()
pattern = re.compile(r'${MARKER_START}.*?${MARKER_END}', re.DOTALL)
content = pattern.sub('', content).rstrip()
with open('${CODEX_CONFIG}', 'w') as f:
    f.write(content + '\n')
"
    echo "   ✓ CutCtx provider removed"
  else
    sed -i.bak "/${MARKER_START//\//\\/}/,/${MARKER_END//\//\\/}/d" "${CODEX_CONFIG}"
    rm -f "${CODEX_CONFIG}.bak"
    echo "   ✓ CutCtx provider removed"
  fi
else
  echo "   CutCtx provider not found — skipping"
fi

# 2. Uninstall MCP server
echo ""
echo "2. Removing MCP server..."
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
echo "================================"
echo "Uninstall complete!"
echo ""
echo "The proxy is still running if you started it separately."
echo "Kill it with: pkill -f 'cutctx proxy' or 'kill \$(lsof -ti:8787)'"
