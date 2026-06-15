#!/usr/bin/env bash
# CutCtx Claude Code Plugin Uninstaller
# Usage: bash uninstall.sh

set -euo pipefail

echo "CutCtx Claude Code Plugin Uninstaller"
echo "======================================"

# 1. Remove MCP server from Claude Code
echo ""
echo "1. Removing MCP server from Claude Code..."

if command -v claude &>/dev/null; then
  if claude mcp remove headroom -s user 2>&1; then
    echo "   ✓ MCP server removed"
  else
    echo "   headroom MCP not found or already removed"
  fi
else
  echo "   ⚠ claude CLI not found — remove manually:"
  echo "     claude mcp remove headroom -s user"
fi

# 2. Also remove from legacy mcp.json if present
LEGACY_CONFIG="${HOME}/.claude/mcp.json"
if [[ -f "${LEGACY_CONFIG}" ]]; then
  echo ""
  echo "2. Checking legacy mcp.json..."
  if command -v python3 &>/dev/null; then
    python3 -c "
import json, os
path = os.path.expanduser('~/.claude/mcp.json')
if not os.path.exists(path):
    exit(0)
with open(path) as f:
    config = json.load(f)
servers = config.get('mcpServers', {})
if 'headroom' in servers:
    del servers['headroom']
    with open(path, 'w') as f:
        json.dump(config, f, indent=2)
        f.write('\n')
    print('   ✓ Removed from mcp.json')
else:
    print('   headroom not in mcp.json')
"
  fi
fi

echo ""
echo "======================================"
echo "Uninstall complete!"
echo ""
echo "The proxy is still running if you started it separately."
echo "Kill it with: pkill -f 'headroom proxy' or 'kill \$(lsof -ti:8787)'"
