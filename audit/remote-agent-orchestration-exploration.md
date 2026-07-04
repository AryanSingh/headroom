# Cutctx — Remote Agent Orchestration: Exploratory Design

> **Status:** Exploratory · Pre-Design  
> **Date:** July 4, 2026  
> **Primary use case:** Live session monitoring & kill switch for agents routing through Cutctx  
> **Target agents:** Claude Code, Codex CLI, Gemini CLI  
> **Current phase:** Approach evaluation (not yet approved for implementation)

---

## 1. Problem Statement

Teams running AI coding agents in production (CI/CD, automated incident response, multi-agent workflows) have no visibility into what their agents are doing in real time. An agent can go off-track — browsing unintended code, writing bad patches, escalating tool call costs — and nobody knows until the bill arrives or the git history shows the damage.

Cutctx already sits on the request path between agents and LLM providers. This position makes it the natural place to add live session visibility and control.

---

## 2. Scope

**Primary (MVP):**
- Live session monitoring: see active agent sessions, current prompt, recent tool outputs, token usage
- Kill switch: terminate a misbehaving session from the operator's terminal
- Multi-agent support: Claude Code, Codex CLI, Gemini CLI (any agent routing through the proxy)
- CLI-native: `cutctx sessions`, `cutctx session get <id>`, `cutctx session kill <id>`

**Future (post-MVP, not designed here):**
- Prompt injection mid-session
- Tool output override
- Session recording & forensic replay
- Agent-as-a-service API
- Web dashboard
- MCP-based control plane

---

## 3. Approaches Considered

### Approach 1: Proxy-Native Session Inspector (Recommended)

Embed a session registry directly into the Cutctx proxy. The proxy already intercepts all agent↔LLM traffic. Add a ring buffer per session tracking recent exchanges, expose a WebSocket endpoint for live streaming, and CLI commands for interaction.

| Pro | Con |
|---|---|
| No new services to deploy | Web dashboard needs separate effort |
| Leverages existing proxy architecture | Session history limited to proxy memory |
| Instant value for existing users | Not composable with non-CLI tools |
| CLI-first matches Cutctx's product DNA | |

### Approach 2: MCP Tool-Based Control Plane

Expose session management as MCP tools (`cutctx_sessions`, `cutctx_session_get`, `cutctx_session_kill`). Any MCP client (dashboard, IDE, custom tool) can call them.

| Pro | Con |
|---|---|
| Composable — works with any MCP client | Requires MCP client running alongside |
| Clean API boundary | Over-engineered for MVP |
| Reuses existing MCP infrastructure | Most operators don't run an MCP client while agents run |

### Approach 3: Separate Control Server Sidecar

Run a separate HTTP/WS control server. Proxy pushes session events over a Unix socket; control server serves dashboard + kill API. Can be deployed independently.

| Pro | Con |
|---|---|
| Cleanest separation of concerns | Two services instead of one |
| Scales independently | Deployment complexity |
| Best for enterprise multi-team | Over-engineered until proven necessary |

### Recommendation

**Approach 1, with MCP wrappers added in Phase 2.** Session monitoring is a horizontal slice through the proxy — same binary, same deployment, same operational model. Once sessions are a proven concept, expose MCP tools for composability.

---

## 4. Architecture (Approach 1 MVP)

```
Agent ──→ Cutctx Proxy
            │
            ├── Pipeline (unchanged)
            │     CacheAligner → ContentRouter → CCR → compress → send
            │
            ├── SessionRegistry (in-memory)
            │     Per session:
            │     ├─ session_id (UUID, or X-Request-Id)
            │     ├─ agent_type  (detected from User-Agent / request shape)
            │     ├─ start_time / last_active
            │     ├─ state       (active | killed)
            │     ├─ recent_exchanges[N] (ring buffer, configurable depth)
            │     │     └─ each: prompt_snippet → compressed → response_snippet
            │     └─ token_usage (input / output / cache_hit)
            │
            ├── WebSocket endpoint (ws://host:8788/ws)
            │     └─ pushes session.updated / session.created / session.killed events
            │
            └── CLI command set
                  ├─ cutctx sessions
                  │     → table: ID, agent, state, duration, tokens, last activity
                  ├─ cutctx session get <id>
                  │     → full detail + last N exchanges (truncated for terminal)
                  └─ cutctx session kill <id>
                        → drops connection, marks killed, returns error to agent
```

### Session life cycle

```
Agent connects ──→ Session.created
                         │
                    ┌────┴────┐
                    │  active  │ ←── Session.updated on each request/response
                    └────┬────┘
                         │
                    ┌────┴────┐
                    │ killed  │ ←── Operator runs `session kill <id>`
                    └─────────┘
                         │
                    Connection closed
```

### Kill switch mechanics

**Hard kill (MVP):** Proxy closes the TCP/TLS connection to the LLM provider immediately. The agent sees a transport error (connection reset, timeout) and stops. Simple, reliable, works with every provider.

**Graceful kill (future):** Proxy injects a system-level stop signal or a specially crafted response that tells the agent to halt. Requires agent-specific handling; not in MVP.

---

## 5. Open Questions

| Question | Options | Decision needed |
|---|---|---|
| Session ring-buffer depth | 10 / 50 / 100 exchanges | Based on memory budget |
| Session identity | UUID per connection / X-Request-Id / agent-sent session token | Depends on agent capability |
| Kill confirmation | Require confirmation / fire-and-forget | Safety vs speed |
| WebSocket auth | None (localhost) / token / mTLS | Security posture |
| Persist sessions across proxy restart? | No (ephemeral) / Yes (SQLite) | Complexity vs utility |
| CLI output format | Table / JSON / both | User preference |

---

## 6. Related Work

- Cutctx proxy already supports `CUTCTX_ACCURACY_GUARD` for compression quality verification — session monitoring is a complementary safety layer
- Savings attribution (5 sources) could be extended to per-session breakdown in the monitoring view
- Audit logging (SQLite WAL) already records structured events — session events could share this pipeline

---

## 7. Next Steps

1. **Approve approach** — confirm Approach 1 (proxy-native) as the direction
2. **Resolve open questions** — session depth, identity, auth
3. **Write detailed spec** — component interfaces, data structures, CLI output format
4. **Implement MVP** — session registry + CLI commands
5. **Add WebSocket** — live streaming for future dashboard
6. **Expose MCP tools** — composability for ecosystem

---

*This document captures an exploratory design conversation. It is not an implementation spec, and no implementation work has been authorized based on it.*
