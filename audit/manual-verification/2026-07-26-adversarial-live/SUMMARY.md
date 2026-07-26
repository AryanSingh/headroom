# Live evidence summary — 2026-07-26 (resume finish)

## LIVE-CUR
- Auth: `cursor agent login` → Logged in as aryan.iitgn@gmail.com
- LIVE-CUR-1: PASS — marker ZZCURLIVE11 (`live_cur1_agent.out`)
- LIVE-CUR-2: PASS — `--model auto`, marker ZZCURAUTO22 (`live_cur2_agent.out`)
- Binary: `/Applications/Cursor.app/Contents/Resources/app/bin/cursor` (3.13.10)

## Claude Desktop MCP
- Config: `~/Library/Application Support/Claude/claude_desktop_config.json` cutctx → mcp serve, CUTCTX_PROXY_URL=http://127.0.0.1:8787
- Scriptable MCP smoke: compress + retrieve + stats PASS (`mcp_smoke_8787.txt`)
- App activated via AppleScript (CLAUDE_ACTIVATED)
- Note: in-app tool turn after Desktop restart still operator-visible; MCP server path verified

## Cursor / ChatGPT Desktop GUI
- Cursor.app + ChatGPT.app activated
- Cursor User settings written with openai.baseUrl → http://127.0.0.1:8787/v1
- osascript keystrokes blocked by macOS TCC (error 1002) — cannot drive Composer GUI chat without Accessibility grant
- Substitution: LIVE-CUR CLI agent turns + Desktop activation + settings override written
- ChatGPT Desktop GUI chat not signed; Codex ChatGPT-sub via :8787 (`ZZDESKCDX77`) is strongest Desktop proxy evidence

## Codex / ChatGPT Desktop proxy path (strongest non-GUI)
- Normalized `~/.codex/config.toml` cutctx `openai_base_url`/`base_url` → `http://127.0.0.1:8787/v1`
- `codex exec -m gpt-5.4` → marker `ZZDESKCDX77`, rc=0 (`desktop_cdx_8787.out`)
- Stable proxy `:8787` readyz healthy (long-running)

## Residual
- CUTCTX_UPSTREAM_OPENAI_API_KEY returns invalid_api_key from OpenAI (401) — Desktop OpenAI override HTTP path blocked until key refreshed
- True Cursor Composer / ChatGPT.app GUI chat needs macOS Accessibility (osascript keystroke err 1002) or human click-through
- Pilot rust-tests disk / CCR 21/36 remain env/S2 debt (not S0/S1)
