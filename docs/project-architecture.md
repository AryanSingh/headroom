# Cutctx Project Architecture

Cutctx is a local-first context plane for AI agents. It sits between agents and
LLM providers, compresses expensive context before it leaves the machine, keeps
originals retrievable through CCR, tracks savings, and exposes memory,
governance, and observability surfaces for operators.

## System View

```mermaid
flowchart LR
    subgraph Clients["Agents and apps"]
        Codex["Codex / Claude Code / Cursor"]
        SDKs["Python SDK / TypeScript SDK"]
        Apps["LangChain / Agno / custom apps"]
    end

    subgraph Entry["Cutctx entry points"]
        CLI["cutctx CLI and wrap commands"]
        Proxy["Python proxy API server"]
        MCP["MCP server and tools"]
        SDKEntry["compress() library calls"]
    end

    subgraph Core["Compression and intelligence core"]
        Policy["Policy and auth-mode detection"]
        CacheAligner["CacheAligner"]
        Router["ContentRouter"]
        Pipeline["Transform pipeline"]
        Guard["Accuracy guard"]
        Outcome["RequestOutcome funnel"]
    end

    subgraph Stores["Local state"]
        CCR["CCR store\nin-memory / SQLite / Redis"]
        Savings["SavingsTracker\nproxy_savings.json"]
        Memory["Cross-agent memory"]
        Profiles["Workspace profiles"]
    end

    subgraph Surfaces["Operator surfaces"]
        Dashboard["React dashboard"]
        Metrics["/stats, /stats-history, Prometheus"]
        Reports["Buyer reports and CLI perf"]
    end

    Providers["LLM providers\nOpenAI / Anthropic / Gemini / Bedrock / Vertex / Azure"]

    Codex --> CLI
    Codex --> Proxy
    SDKs --> SDKEntry
    Apps --> Proxy
    CLI --> Proxy
    MCP --> Core
    SDKEntry --> Core
    Proxy --> Core
    Policy --> CacheAligner --> Router --> Pipeline --> Guard --> Providers
    Pipeline --> CCR
    Core --> Outcome
    Outcome --> Savings
    Outcome --> Metrics
    Memory --> MCP
    Profiles --> Policy
    Proxy --> Dashboard
    Savings --> Dashboard
    Savings --> Reports
    CCR --> MCP
```

## Request Lifecycle

```mermaid
sequenceDiagram
    participant Agent as Agent or SDK
    participant Proxy as Cutctx proxy
    participant Policy as Policy engine
    participant Pipe as Compression pipeline
    participant CCR as CCR store
    participant LLM as LLM provider
    participant Stats as Savings and metrics

    Agent->>Proxy: LLM request with prompts, tools, files, logs
    Proxy->>Policy: classify provider, auth mode, model, cache risk
    Policy->>Pipe: choose safe compression policy
    Pipe->>Pipe: align cache prefix and route content by type
    Pipe->>CCR: store originals for offloaded content
    CCR-->>Pipe: retrieval hashes and markers
    Pipe-->>Proxy: compressed request
    Proxy->>LLM: forward optimized provider-native request
    LLM-->>Proxy: response and provider usage metadata
    Proxy->>Stats: record tokens, dollars, model, source attribution
    Proxy-->>Agent: provider-compatible response
```

The important design choice is that compression is reversible where it matters:
large or risky drops are replaced by CCR markers, and the original bytes stay in
local storage until the configured TTL expires.

## Compression Pipeline

```mermaid
flowchart TD
    Input["Incoming context"] --> Normalize["Normalize provider shape"]
    Normalize --> Cache["CacheAligner\nstable prompt prefixes"]
    Cache --> Detect["Content detection\nJSON, code, log, diff, HTML, search, image, prose"]
    Detect --> Route{"ContentRouter"}

    Route --> Json["SmartCrusher\nJSON arrays and tool output"]
    Route --> Code["CodeCompressor\nAST and tree-sitter aware code"]
    Route --> Logs["LogCompressor\nerrors, warnings, stack traces"]
    Route --> Diff["DiffCompressor and Difftastic\nchange-aware diffs"]
    Route --> Search["SearchCompressor\nquery relevance ranking"]
    Route --> Text["Kompress-base / lexical compressors\nagentic prose"]
    Route --> Images["Image compression\nquality and format routing"]
    Route --> Schema["Tool schema compaction\nmetadata key stripping"]

    Json --> Merge["Merge optimized fragments"]
    Code --> Merge
    Logs --> Merge
    Diff --> Merge
    Search --> Merge
    Text --> Merge
    Images --> Merge
    Schema --> Merge

    Merge --> Guard["Accuracy guard\npreserve identifiers and references"]
    Guard --> Output["Compressed request plus CCR markers"]
```

The pipeline favors specialized transforms over one generic summarizer. That is
why logs, JSON rows, diffs, code, images, and prose have separate algorithms.

## Main Modules

```mermaid
flowchart TB
    subgraph Python["Python package: cutctx/"]
        ProxyRoutes["proxy/\nFastAPI app, provider handlers, streaming, admin"]
        CLI["cli/\nwrap, perf, report, savings, integrations"]
        Providers["providers/\nClaude, Copilot, OpenAI-compatible adapters"]
        SavingsPy["savings/ and proxy/savings_tracker.py\nsource attribution and persistence"]
        MemoryPy["memory/\ncross-agent facts and corrections"]
        DashboardPkg["dashboard/\npackaged React assets"]
    end

    subgraph Rust["Rust crates: crates/"]
        CoreRust["cutctx-core\nCCR, tokenizer, transforms, SmartCrusher, live-zone compression"]
        ProxyRust["cutctx-proxy\nRust proxy experiments and provider paths"]
        Parity["cutctx-parity\nPython/Rust parity checks"]
    end

    subgraph Web["dashboard/"]
        React["React dashboard\nOverview, capabilities, governance, memory, replay"]
        Build["Vite build\nsynced into cutctx/dashboard"]
    end

    ProxyRoutes --> CoreRust
    CLI --> ProxyRoutes
    Providers --> ProxyRoutes
    ProxyRoutes --> SavingsPy
    MemoryPy --> CLI
    React --> Build --> DashboardPkg
    CoreRust --> Parity
```

## Tools And Algorithms In Use

| Area | Tools / algorithms | Purpose |
| --- | --- | --- |
| Proxy runtime | FastAPI, provider-native handlers, streaming SSE/WebSocket paths | Intercepts and forwards LLM traffic without client changes. |
| Compression core | ContentRouter, SmartCrusher, CodeCompressor, LogCompressor, DiffCompressor, SearchCompressor, Kompress-base | Chooses a content-specific strategy and removes low-value context. |
| Reversibility | CCR with hash keys, in-memory / SQLite / Redis backends | Stores originals locally and lets agents retrieve exact content later. |
| Token accounting | tiktoken, HuggingFace tokenizers, provider usage metadata | Measures before/after tokens and model-specific costs. |
| Cache optimization | CacheAligner, Anthropic/OpenAI prompt-cache metadata, prefix stability checks | Keeps reusable prefixes stable so provider prompt caches hit. |
| Cost attribution | RequestOutcome funnel, SavingsSource enum, SavingsTracker | Tags savings by source without double-counting. |
| Intelligence | BM25-style relevance, rolling hashes, task-aware policies, workspace profiles | Adjusts compression based on task, recency, repeats, and context budget. |
| Security | LLM firewall regexes, structured-output validation, audit logging, RBAC/entitlements | Governs risky prompts, admin access, and enterprise controls. |
| Observability | React dashboard, `/stats`, `/stats-history`, Prometheus metrics, buyer reports | Shows savings, active compression, model attribution, history, and capability state. |
| Developer stack | Python, Rust, Vite/React, pytest, Playwright specs, Cargo tests | Splits hot compression logic from proxy and dashboard surfaces. |

## Savings Attribution

```mermaid
flowchart LR
    Request["Completed request"] --> Outcome["RequestOutcome"]
    Outcome --> Sources["SavingsSource breakdown"]

    Sources --> Direct["Cutctx compression"]
    Sources --> ProviderCache["Provider prompt cache"]
    Sources --> Semantic["Semantic cache"]
    Sources --> Prefix["Self-hosted prefix cache"]
    Sources --> Routing["Model routing"]
    Sources --> Schema["Tool schema compaction"]
    Sources --> Normalize["Tokenizer normalization"]
    Sources --> Batch["Batch routing"]
    Sources --> Memo["Tool memoization"]
    Sources --> OutputOpt["Output optimization"]

    Direct --> Persist["SavingsTracker"]
    ProviderCache --> Persist
    Semantic --> Persist
    Prefix --> Persist
    Routing --> Persist
    Schema --> Persist
    Normalize --> Persist
    Batch --> Persist
    Memo --> Persist
    OutputOpt --> Persist

    Persist --> Stats["/stats and /stats-history"]
    Persist --> Dashboard["Dashboard attribution panels"]
    Persist --> Reports["Buyer reports"]
```

The attribution path is intentionally centralized. Provider handlers produce a
`RequestOutcome`; the funnel derives one source map; metrics, reports, and the
dashboard consume that same map.

## Deployment Modes

```mermaid
flowchart LR
    Local["Local developer machine"] --> Wrap["cutctx wrap codex/claude/cursor"]
    Local --> Proxy["cutctx proxy --port 8787"]
    Local --> MCP["cutctx mcp serve"]
    Local --> SDK["Python or TypeScript SDK"]

    Wrap --> Agent["Agent process"]
    Agent --> Proxy
    SDK --> Core["Compression core"]
    MCP --> Tools["cutctx_retrieve and memory tools"]
    Proxy --> Provider["LLM provider"]

    Server["Team or enterprise service"] --> Docker["Docker / k8s / helm"]
    Docker --> Proxy
    Docker --> Stores["SQLite / Redis / audit stores"]
```

Most individual users run Cutctx locally as a wrapper or proxy. Team and
enterprise deployments can keep the same request lifecycle while adding Redis,
audit stores, SSO/RBAC, and centralized observability.

## What The Project Is About

Cutctx tries to make AI-agent context cheaper and safer without asking every
agent or application to change its prompt code. The product goal is:

1. Reduce tokens before they reach the provider.
2. Preserve accuracy by keeping originals available through CCR.
3. Improve provider cache hit rates instead of accidentally breaking them.
4. Attribute every saving to a concrete source.
5. Share useful memory and learned corrections across agents.
6. Give operators enough dashboard and report data to trust the system.

