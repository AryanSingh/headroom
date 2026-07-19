# Event-Sourced Agent Harness Integration

**Version:** 1.0
**Status:** Design Exploration
**Author:** Aryan Singh
**Date:** 2026-07-19
**Source:** Jonas Templestein, "Make your own event-sourced agent harness using stream processors" — Iterate (https://www.youtube.com/watch?v=vi-2nasppAg)

## Executive Summary

The event-sourced agent harness architecture (every LLM interaction recorded as an append-only event, state derived via a synchronous reducer, side effects triggered by after-append hooks) maps naturally onto CutCtx's existing position as the middleware layer between agents and LLMs. This document explores integration points, architectural changes, and commercial implications.

## Core Abstraction (from the talk)

Three components:

| Component | Role | Property |
|-----------|------|----------|
| **Event stream** | Append-only log of everything that happens (prompts, streaming chunks, tool calls, errors, circuit breaker triggers) | Immutable, replayable, ordered |
| **Reducer** | Synchronous function that derives current state by replaying events | Deterministic, fast, no LLM calls |
| **After-append hook** | Side effects triggered after new events are appended | Async, fallible, composable |

The key insight: **On restart, the reducer replays events — not LLM requests.** This is the fundamental cost/performance advantage over naive agent implementations.

## Current State of CutCtx

CutCtx is a context compression layer that sits between agents and LLM providers. Its current pipeline:

```
Agent → CutCtx proxy/SDK → Compression pipeline → LLM provider
                              │
                              └─ Analytics, caching, routing
```

CutCtx already:
- Intercepts every agent → LLM interaction (in proxy mode)
- Maintains CCR (Compress-Cache-Retrieve) for reversible compression
- Provides cross-agent memory via `cutctx learn`
- Has a plugin system for extensibility

What CutCtx does **not** currently do:
- Maintain a durable, replayable event log of agent interactions
- Derive agent state from event replay
- Host composable stream processors

## Integration Architecture

### Layer 1: Event Log on the Proxy

The CutCtx proxy already sees every message. Add an **event journal** that records each significant interaction as a structured event:

```
Proxy intercept
       │
       ▼
┌──────────────────────────────┐
│  Event Journal                │
│  ─────────────────────       │
│  event_id │ type │ payload   │──→ SQLite (local, append-only)
│  ─────────────────────       │
│  001  │ prompt_received   │  │
│  002  │ compression_applied│  │
│  003  │ llm_request_sent   │  │
│  004  │ chunk_received     │  │
│  005  │ tool_call_detected │  │
│  ...                         │
└──────────────────────────────┘
       │
       ▼
┌──────────────────────────────┐
│  Reducer                      │
│  ─────────────────────       │
│  Replay events → derive       │
│  state (current context,       │
│  compression stats, failure    │
│  patterns, usage metrics)     │
└──────────────────────────────┘
       │
       ▼
┌──────────────────────────────┐
│  After-Append Hooks           │
│  ─────────────────────       │
│  - Compression decision       │
│  - cutctx learn trigger       │
│  - Cache warming              │
│  - Enterprise audit export   │
└──────────────────────────────┘
```

**Event types:**

```rust
enum AgentEvent {
    SessionStarted { agent_id: String, model: String },
    PromptReceived { message_count: u32, token_count: u64 },
    CompressionApplied { strategy: String, tokens_before: u64, tokens_after: u64 },
    LlmRequestSent { model: String, provider: String },
    ChunkReceived { stream_id: String, content_type: String },
    ToolCallDetected { tool_name: String, args_hash: String },
    ToolResultReceived { tool_name: String, status: ResultStatus },
    CircuitBreakerTriggered { reason: String, cooldown_ms: u64 },
    Error { code: String, message: String },
    SessionEnded { duration_ms: u64, total_tokens_saved: u64 },
    // Dynamic worker (see Layer 3)
    ProcessorDeployed { processor_id: String, source_hash: String },
}
```

### Layer 2: Reducer for State Derivation

The reducer is a synchronous, deterministic function that replays events to derive state. Because it never calls LLMs, it can replay thousands of events in milliseconds.

**What the reducer derives:**

| State | Source Events | Purpose |
|-------|--------------|---------|
| Current context snapshot | SessionStarted, PromptReceived | Track what the agent has seen |
| Compression savings | CompressionApplied | Real-time cost dashboard |
| Failure pattern profile | Error, CircuitBreakerTriggered | `cutctx learn` input |
| Tool success rates | ToolCallDetected, ToolResultReceived | Quality metrics |
| Cache hit/miss ratios | LlmRequestSent, ChunkReceived | Cache tuning |
| Session usage summary | All events | Billing, auditing |

**On proxy restart:**

```
1. Load last N sessions from event journal
2. Run reducer over events → reconstruct state
3. Continue with hot state (no LLM replay)
4. Start appending new events
```

The split matters: **100 events replayed = 2ms, not 100 LLM calls.**

### Layer 3: Stream Processors (Dynamic Workers)

Jonas's most interesting idea: processors whose *payload is code* appended as an event to the stream.

```
Event: ProcessorDeployed {
    processor_id: "safety-checker-v2",
    source: "async function check(ctx) { ... }"  // JS string
}
```

In CutCtx, this maps to the existing plugin system:

```rust
trait StreamProcessor: Send + Sync {
    fn name(&self) -> &str;
    fn filter(&self) -> EventFilter;           // Which events to process
    fn handle(&self, event: &AgentEvent, state: &AgentState) -> Result<SideEffect>;
}

// Built-in processors ship with CutCtx
struct CompressionDecisionProcessor;    // Which strategy to apply per event
struct LearnFromFailureProcessor;       // cutctx learn integration
struct AuditExportProcessor;            // Enterprise compliance export

// User-deployed processors via plugin API
struct UserProcessor {
    source: String,   // WASM or JS sandbox
    config: ProcessorConfig,
}
```

**Composability model:**

```
                ┌── CompressionDecisionProcessor
                │         (200ms window before LLM call)
Event Stream ───┼── SafetyCheckProcessor
                │         (injects context before LLM)
                ├── LearnFromFailureProcessor
                │         (async, eventual)
                └── AuditExportProcessor
                          (async, eventual)
```

Processors from different authors can compose against the same stream. A safety checker can inject context in a 200ms window before an LLM request without blocking the agent if it doesn't make it in time.

### Layer 4: Dynamic Worker Deployment Model

This is the most commercially interesting layer. Processors are deployed as event payloads — no deploy pipeline, no server restart.

```
1. Client appends ProcessorDeployed event to stream
   ├── payload = JavaScript/WASM processor source
   └── source_hash verified against signed manifest

2. CutCtx proxy detects event, loads processor into sandbox
   ├── WASM sandbox for untrusted processors
   ├── V8 isolate for JS processors
   └── Native trait for trusted/built-in processors

3. Processor starts receiving filtered events
   └── No restart, no deploy pipeline, no server dependency

4. Processor removed by appending ProcessorRemoved event
   └── Clean shutdown, in-flight handlers drain
```

Implication: **a CutCtx proxy instance becomes an AI agent host without needing a separate server or deployment pipeline.**

## Integration Points with Existing CutCtx Features

### `cutctx learn` Enhancement

Current: mines failed sessions, writes corrections to CLAUDE.md / AGENTS.md.

With event sourcing:
- Failure events are already in the log with full context
- Reducer identifies exact failure sequences (circuit breaker → error → recovery)
- Pattern mining becomes a stream processor that reads the event stream
- Corrections are tagged with the event_id that triggered them for traceability

```rust
// Existing: cutctx learn
// Enhanced: event-sourced version
impl StreamProcessor for LearnFromFailureProcessor {
    fn filter(&self) -> EventFilter {
        EventFilter::any(&[EventType::Error, EventType::CircuitBreakerTriggered])
    }

    fn handle(&self, event: &AgentEvent, state: &AgentState) -> Result<SideEffect> {
        // Full event context available for root-cause analysis
        let failure_sequence = state.replay_sequence(event.id() - 10..=event.id());
        let correction = analyze_failure_sequence(failure_sequence);
        write_correction(correction)
    }
}
```

### CCR (Compress-Cache-Retrieve) Integration

The CCR store becomes a natural cache for both compression originals AND event state snapshots:

```
Event journal ──→ Reducer ──→ State snapshot (optionally cached in CCR)
                    │
                    ▼
              On restart: check CCR for latest state snapshot
              If found: start from snapshot, replay only newer events
              If not found: replay from beginning (still fast)
```

This gives O(1) restart recovery with the bounded event log for consistency.

### Multi-Agent Compression State

The existing multi-agent shared compression state spec (`multi-agent-state.md`) takes on a new dimension:

- Event stream is **shared across agents** in the same workspace
- Agent A's compression decisions are events that Agent B's reducer can see
- Cross-agent coordination becomes a stream processor, not bespoke orchestration

## Data Model

```rust
// Core event structure
struct StoredEvent {
    event_id: u64,          // Monotonic, append-only
    timestamp: i64,         // Unix ms
    session_id: Uuid,
    agent_id: String,
    event_type: EventType,
    payload: Vec<u8>,       // Serialized event data
    parent_event_id: Option<u64>,  // Causal chain
}

// Event journal (SQLite table)
// ─────────────────────────────────────────────────
// CREATE TABLE event_journal (
//     event_id    INTEGER PRIMARY KEY AUTOINCREMENT,
//     timestamp   INTEGER NOT NULL,
//     session_id  TEXT NOT NULL,
//     agent_id    TEXT NOT NULL,
//     event_type  TEXT NOT NULL,
//     payload     BLOB NOT NULL,
//     parent_id   INTEGER REFERENCES event_journal(event_id)
// );
//
// CREATE INDEX idx_event_journal_session ON event_journal(session_id);
// CREATE INDEX idx_event_journal_agent ON event_journal(agent_id);
// CREATE INDEX idx_event_journal_type ON event_journal(event_type);
// CREATE INDEX idx_event_journal_time ON event_journal(timestamp);

// Reducer state (in-memory, reconstructed on restart)
struct AgentState {
    agent_id: String,
    session_summaries: Vec<SessionSummary>,
    compression_stats: CompressionStats,
    failure_profile: FailureProfile,
    tool_statistics: HashMap<String, ToolStats>,
    last_event_id: u64,
}

// Stream processor registration
struct ProcessorRegistration {
    processor_id: String,
    event_filter: EventFilter,
    priority: u8,              // Execution order
    timeout_ms: u64,           // Max processing time
    side_effect: SideEffectType,  // sync (blocking) or async (fire-and-forget)
}
```

## Deployment Model

### Phase 1: Embedded Event Journal (Current Proxy)

- SQLite-backed event journal built into cutctx-proxy
- Configurable retention (default: 7 days, max: unbounded)
- Reducer runs in-proc on restart
- Stream processors limited to built-in set
- Zero external dependencies

```
cutctx proxy --event-journal-enabled --event-retention-days 30
```

### Phase 2: Plugin-Based Stream Processors

- User processors via WASM/V8 sandbox
- Processor lifecycle managed by event stream (deploy/remove events)
- Priority-based execution ordering
- Timeout protection (rogue processors don't block the stream)

```
# Deploy a processor via event
cutctx event append processor-deploy \
  --source ./safety-checker.wasm \
  --filter "Error,CircuitBreakerTriggered"
```

### Phase 3: Distributed Event Store (Enterprise)

- Event journal backed by PostgreSQL/PGStream for cross-process durability
- Multi-proxy instances share event streams
- Global reducer for enterprise-wide state (aggregate stats across all agents)
- Reducer snapshots in S3/compatible object store

## Commercial Implications

### Differentiation from Competitors

| Feature | Temporal | LangGraph Cloud | CutCtx + Event Sourcing |
|---------|----------|-----------------|------------------------|
| Compression | None | None | **Built-in, proven** |
| Event sourcing | Yes (workflows) | Partial | **Agent-native** |
| Dynamic workers | No (SDK-defined) | No | **Event-payload deploy** |
| Cross-agent memory | No | No | **Yes (cutctx learn)** |
| Reversible compression | No | No | **Yes (CCR)** |
| Local-first | No | Cloud | **Yes** |
| Agent-agnostic | No | LangChain-only | **Any agent** |

### Monetization Vectors

1. **Event Journal Pro** — Extended retention, cross-session replay, export pipelines
2. **Stream Processor Marketplace** — Certified processors (safety, compliance, routing), revenue share
3. **Enterprise Audit** — Immutable event log for SOC2/HIPAA compliance, with query API
4. **Agent Observability Suite** — Dashboard built on reducer state, per-agent cost breakdowns, failure analysis
5. **Distributed Event Store** — Multi-proxy, cross-workspace, global state — enterprise tier

## Open Questions

1. **Storage overhead:** Event journal for a high-traffic proxy — how much data per session? Target: < 10KB/event, < 100MB/day/proxy. Need benchmarks.

2. **Processor sandboxing:** WASM vs V8 isolate for untrusted processor code. WASM has better security properties but limits API surface. V8 is more capable but heavier. Recommendation: start with built-in native processors, add WASM in Phase 2.

3. **Determinism guarantees:** Reducer must be deterministic for replay correctness. How to handle non-deterministic inputs (time, random, external API calls)? Options: (a) record them as events, (b) require processors to be pure functions, (c) snapshot + replay from snapshot.

4. **Event schema evolution:** As CutCtx evolves, event types will change. Backward compatibility strategy needed for long-lived journals. Apache Avro / Protobuf schema registry?

5. **Retention vs completeness:** How long to keep events? Cost of storage vs value of replay. Options: (a) time-based TTL, (b) size-based, (c) importance-based pruning (keep errors forever, drop routine events).

6. **Dynamic processor trust model:** If processors are deployed as event payloads, who signs them? Which processors get 200ms sync window vs async-only? Recommendation: signed manifests for sync processors, async-only for unsigned.

## References

- Jonas Templestein, "Make your own event-sourced agent harness using stream processors" — Iterate (https://www.youtube.com/watch?v=vi-2nasppAg)
- `docs/content/docs/architecture.mdx` — Current CutCtx architecture
- `docs/specs/multi-agent-state.md` — Multi-agent shared compression state design
- `crates/cutctx-proxy/src/` — Current proxy implementation
- `plugins/cutctx-plugin/` — Plugin system
