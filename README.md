<div align="center"><pre>
   ██████╗██╗   ██╗████████╗ ██████╗████████╗██╗  ██╗
  ██╔════╝██║   ██║╚══██╔══╝██╔════╝╚══██╔══╝╚██╗██╔╝
  ██║     ██║   ██║   ██║   ██║        ██║    ╚███╔╝
  ██║     ██║   ██║   ██║   ██║        ██║    ██╔██╗
  ╚██████╗╚██████╔╝   ██║   ╚██████╗   ██║   ██╔╝ ██╗
   ╚═════╝ ╚═════╝    ╚═╝    ╚═════╝   ╚═╝   ╚═╝  ╚═╝
              The context compression layer for AI agents
</pre></div>

<p align="center"><strong>Context control plane for AI agents · govern · attribute · remember · compress · local-first · reversible</strong></p>

<p align="center">
  <a href="https://github.com/cutctx/cutctx/actions/workflows/ci.yml"><img src="https://github.com/cutctx/cutctx/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://app.codecov.io/gh/cutctx/cutctx"><img src="https://codecov.io/gh/cutctx/cutctx/graph/badge.svg" alt="codecov"></a>
  <a href="https://pypi.org/project/cutctx-ai/"><img src="https://img.shields.io/pypi/v/cutctx-ai.svg" alt="PyPI"></a>
  <a href="https://www.npmjs.com/package/cutctx-ai"><img src="https://img.shields.io/npm/v/cutctx-ai.svg" alt="npm"></a>
  <a href="https://huggingface.co/cutctx/kompress-v2-base"><img src="https://img.shields.io/badge/model-Kompress--v2--base-yellow.svg" alt="Model: Kompress-v2-base"></a>
  <a href="LICENSING.md"><img src="https://img.shields.io/badge/license-open--core-blue.svg" alt="License: Open Core (Apache-2.0 + Commercial)"></a>
  <a href="https://cutctx.com/docs"><img src="https://img.shields.io/badge/docs-online-blue.svg" alt="Docs"></a>
</p>

<p align="center">
  <a href="https://cutctx.com/docs">Docs</a> ·
  <a href="#get-started-60-seconds">Install</a> ·
  <a href="#proof">Proof</a> ·
  <a href="#agent-compatibility-matrix">Agents</a> ·
  <a href="https://discord.gg/yRmaUNpsPJ">Discord</a> ·
  <a href="llms.txt">llms.txt</a> ·
  <a href="ENTERPRISE.md">Enterprise</a> ·
  <a href="artifacts/pricing-sheet.md">Pricing</a> ·
  <a href="TERMS.md">Terms</a> ·
  <a href="PRIVACY.md">Privacy</a>
</p>

<p align="center"><sub>
  <b>AI agents / LLMs:</b> read <a href="llms.txt"><code>/llms.txt</code></a> here, or fetch <a href="https://cutctx.com/llms.txt">the live index</a> / <a href="https://cutctx.com/llms-full.txt">full docs blob</a>.
</sub></p>

---
<p align="center"><a href="https://trendshift.io/repositories/20881" target="_blank"><img src="https://trendshift.io/api/badge/repositories/20881" alt="cutctx%2Fcutctx | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a></p>

Cutctx compresses everything your AI agent reads — tool outputs, logs, RAG chunks, files, and conversation history — before it reaches the LLM. Same answers, fraction of the tokens.

> Product naming: **Cutctx** is the public product brand. The historical Python module name `cutctx` still exists for compatibility behind the `cutctx` alias, but end-user installs and commands are `cutctx` / `cutctx-ai`.

<p align="center">
  <img src="CutctxDemo-Fast.gif" alt="Cutctx in action" width="820">
  <br/><sub>Live: 10,144 → 1,260 tokens — same FATAL found.</sub>
</p>

## What it does

- **Library** — `compress(messages)` in Python or TypeScript, inline in any app
- **Proxy** — `cutctx proxy --port 8787`, zero code changes, any language
- **Agent wrap** — `cutctx wrap claude|codex|cursor|aider|copilot|windsurf|zed|opencode` in one command
- **MCP server** — `cutctx_compress`, `cutctx_retrieve`, `cutctx_status` for any MCP client
- **Cross-agent memory** — shared store across Claude, Codex, Gemini, auto-dedup
- **`cutctx learn`** — agent self-improvement: mines failed sessions, detects failure patterns, writes corrections to `CLAUDE.md` / `AGENTS.md` so agents get smarter every session
- **Reversible (CCR)** — originals are cached for retrieval on demand
- **Image optimization** — images in tool outputs and messages compressed automatically, 40–90% reduction (JPEG quality routing + format conversion), zero config

## How it works (30 seconds)

```
 Your agent / app
   (Claude Code, Cursor, Codex, LangChain, Agno, Strands, your own code…)
        │   prompts · tool outputs · logs · RAG results · files
        ▼
    ┌────────────────────────────────────────────────────┐
    │  Cutctx    (runs locally — your data stays here)  │
    │  ────────────────────────────────────────────────  │
    │  CacheAligner  →  ContentRouter  →  CCR            │
    │                    ├─ SmartCrusher   (JSON)        │
    │                    ├─ CodeCompressor (AST)         │
    │                    └─ Kompress-base  (text, HF)    │
    │                                                    │
    │  Cross-agent memory  ·  cutctx learn  ·  MCP     │
    └────────────────────────────────────────────────────┘
        │   compressed prompt  +  retrieval tool
        ▼
 LLM provider  (Anthropic · OpenAI · Bedrock · …)
```

- **ContentRouter** — detects content type, selects the right compressor
- **SmartCrusher / CodeCompressor / Kompress-base** — compress JSON, AST, or prose
- **CacheAligner** — stabilizes prefixes so provider KV caches actually hit
- **CCR** — stores originals locally; LLM calls `cutctx_retrieve` if it needs them

→ [Architecture](docs/project-architecture.md) · [Docs architecture](https://cutctx.com/docs/architecture) · [CCR reversible compression](https://cutctx.com/docs/ccr) · [Kompress-v2-base model card](https://huggingface.co/cutctx/kompress-v2-base)

## Get started (60 seconds)

```bash
# 1 — Install
pip install "cutctx-ai[all]"          # Python (broad bundle; some heavy/proprietary extras omitted)
npm install cutctx-ai                 # Node / TypeScript

# 2 — Pick your mode
cutctx wrap claude                    # wrap a coding agent
cutctx proxy --port 8787              # drop-in proxy, zero code changes
# or: from cutctx import compress      # inline library

# 3 — See the savings
cutctx perf

# 4 — Explore capabilities
cutctx capabilities                   # show all algorithms, formats, and options
```

**CLI commands** — Key commands to get started:
- `cutctx wrap <agent>` — wrap Claude, Cursor, Codex, and other agents
- `cutctx proxy` — drop-in proxy server for any LLM client
- `cutctx perf` — show token savings metrics
- `cutctx capabilities` — list compression algorithms, supported formats, and configuration options
- `cutctx learn` — analyze failed sessions and auto-generate corrections

**Accuracy guard** — `--accuracy-guard strict` (default in agent profiles) verifies that compressed output preserves critical identifiers, function names, and references before forwarding. Use `CUTCTX_ACCURACY_GUARD=strict|balanced|off` to tune.

Granular extras: `[proxy]`, `[mcp]`, `[ml]`, `[code]`, `[memory]`, `[relevance]`, `[image]`, `[agno]`, `[langchain]`, `[evals]`, `[pytorch-mps]` (Apple-GPU memory-embedder offload — set `CUTCTX_EMBEDDER_RUNTIME=pytorch_mps`). Requires **Python 3.10+**.

## Proof

**Savings on real agent workloads:**

| Workload                      | Before | After  | Savings |
|-------------------------------|-------:|-------:|--------:|
| Code search (100 results)     | 17,765 |  1,408 | **92%** |
| SRE incident debugging        | 65,694 |  5,118 | **92%** |
| GitHub issue triage           | 54,174 | 14,761 | **73%** |
| Codebase exploration          | 78,502 | 41,254 | **47%** |

**Accuracy preserved on standard benchmarks:**

| Benchmark  | Category | N   | Baseline | Cutctx | Delta      |
|------------|----------|----:|---------:|---------:|------------|
| GSM8K      | Math     | 100 |    0.870 |    0.870 | **±0.000** |
| TruthfulQA | Factual  | 100 |    0.530 |    0.560 | **+0.030** |
| SQuAD v2   | QA       | 100 |        — |  **97%** | 19% compression |
| BFCL       | Tools    | 100 |        — |  **97%** | 32% compression |

Reproduce: `cutctx evals benchmark --dataset tool_outputs --dataset hotpotqa --dataset squad --compressors all --metrics ratio --metrics tokens_saved --metrics f1 --metrics rouge_l --markdown` · [Full benchmarks & methodology](https://cutctx.com/docs/benchmarks)

**Real output from the command above** (seed `42`, zero-LLM):

| Dataset | N | Code | ContentRouter | Kompress | LLMLingua |
|---|---|---:|---:|---:|---:|
| ToolOutputSamples | 8 | 80.5% | 78.2% | 78.8% | 45.4% |
| HotpotQA | 50 | 81.6% | 81.7% | 81.6% | 54.3% |
| SQuAD v2 | 50 | 93.1% | 93.3% | 93.3% | 54.5% |

Full per-compressor breakdown (all 10 compressors × ratio/tokens-saved/F1/ROUGE-L) in `benchmark_results.md` at the repo root.

<a href="https://www.star-history.com/?repos=cutctx%2Fcutctx&type=date&legend=top-left">
 <picture>
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=cutctx/cutctx&type=date&legend=top-left" />
 </picture>
</a>

## Agent compatibility matrix

| Agent       | `cutctx wrap` | Notes                            |
|-------------|:---------------:|----------------------------------|
| Claude Code | ✅              | `--memory` · `--code-graph`      |
| Codex       | ✅              | shares memory with Claude        |
| Cursor      | ✅              | prints config — paste once       |
| Aider       | ✅              | starts proxy + launches          |
| Copilot CLI | ✅              | starts proxy + launches          |
| OpenClaw    | ✅              | installs as ContextEngine plugin |

Any OpenAI-compatible client works via `cutctx proxy`. MCP-native: `cutctx mcp install`.

### GitHub Copilot CLI subscription mode

Cutctx can route GitHub Copilot CLI subscription traffic through the local proxy:

```bash
cutctx wrap copilot --subscription -- --model gpt-4o
```

This lets Cutctx intercept OpenAI-compatible Copilot CLI requests and apply the same proxy compression pipeline before forwarding to GitHub Copilot's hosted API. The wrapper resolves the account-specific Copilot API endpoint and prints it as `COPILOT_PROVIDER_API_URL=...` during launch.

Platform support note: macOS auth reuse via Copilot CLI Keychain storage has been smoke-tested. Windows Credential Manager, Linux Secret Service / `secret-tool`, and Docker/CI token-injection paths are implemented or planned as auth-discovery paths, but still need real OS validation before they should be considered fully vetted. For Docker and CI, prefer passing an explicit `GITHUB_COPILOT_TOKEN` or `GITHUB_COPILOT_GITHUB_TOKEN` rather than relying on host keychain access.

## When to use · When to skip

**Great fit if you…**
- run AI coding agents daily and want savings without changing your code
- work across multiple agents and want shared memory
- need reversible compression — originals are retrievable via CCR within the configured TTL

**Skip it if you…**
- only use a single provider's native compaction and don't need cross-agent memory
- work in a sandboxed environment where local processes can't run

## Commercial resources

For buyers, operators, and security reviewers:

- [Enterprise overview](ENTERPRISE.md)
- [Pricing sheet](artifacts/pricing-sheet.md)
- [Packaging matrix](artifacts/packaging-matrix.md)
- [Security one-pager](artifacts/security-one-pager.md)
- [Deployment architecture](docs/deployment-architecture.md)
- [Commercialization execution kit](artifacts/COMMERCIALIZATION_EXECUTION_KIT.md)
- [Artifacts index](artifacts/README.md)

<details>
<summary><b>Integrations — drop Cutctx into any stack</b></summary>

| Your setup             | Hook in with                                                     |
|------------------------|------------------------------------------------------------------|
| Any Python app         | `compress(messages, model=…)`                                    |
| Any TypeScript app     | `await compress(messages, { model })`                            |
| Anthropic / OpenAI SDK | Cutctx client wrappers for existing Anthropic and OpenAI SDK clients |
| Vercel AI SDK          | `wrapLanguageModel({ model, middleware: cutctxMiddleware() })` |
| LiteLLM                | Cutctx callback integration for LiteLLM                          |
| LangChain              | Cutctx LangChain chat wrapper                                    |
| Agno                   | Cutctx Agno model wrapper                                        |
| Strands                | [Strands guide](https://cutctx.com/docs/strands)  |
| ASGI apps              | `app.add_middleware(CompressionMiddleware)`                      |
| Multi-agent            | `SharedContext().put / .get`                                     |
| MCP clients            | `cutctx mcp install`                                           |

</details>

<details>
<summary><b>What's inside</b></summary>

- **SmartCrusher** — universal JSON compression: arrays of dicts, nested objects, mixed types.
- **CodeCompressor** — AST-aware compression for Python, JS, Go, Rust, Java, C++.
- **Kompress-base** — HuggingFace model trained on agentic traces.
- **DiffCompressor** — diff-aware compression with SIMD-accelerated line splitting.
- **LogCompressor** — structured log compression with aho-corasick pattern detection.
- **SearchCompressor** — search result compression with relevance scoring.
- **Image compression** — inline base64 image compression with CCR storage.
- **Audio routes** — `/v1/audio/*` traffic is proxied pass-through today; no token compression is applied to audio payloads.
- **JSON schema compression** — 40% token savings on tool definitions (32 metadata keys stripped).
- **CacheAligner** — stabilizes prefixes so Anthropic/OpenAI KV caches actually hit.
- **CCR** — reversible compression; LLM retrieves originals on demand via `cutctx_retrieve`.
- **Cross-agent memory** — shared store, agent provenance, auto-dedup.

</details>

<details>
<summary><b>Intelligence layer</b></summary>

- **Task-aware compression** — extracts working task from messages, scores each context segment by BM25 relevance, modulates compression rate per message.
- **Semantic deduplication** — rolling SHA-256 hash index replaces repeated content with CCR pointers across sessions.
- **Context budgeting** — token budget per session with progressive compression through GREEN/YELLOW/RED/CRITICAL zones.
- **Cross-session profiles** — learns compression patterns per workspace over time, adjusts future recommendations.
- **Multi-agent shared state** — SharedCompressionCache with content-hash keyed LRU+TTL cache.
- **Cost forecasting** — pre-task cost estimation with PolicyEngine (6 rules), tracks spend across sessions.

</details>

<details>
<summary><b>Savings attribution (5 sources)</b></summary>

Every token saved is tagged with the source that produced it. The buyer report and the dashboard never double-count. The five sources:

- **Provider prompt cache** — Anthropic `cache_read_input_tokens`, OpenAI `cached_tokens`, Gemini `cachedContentTokenCount`. Observed on the upstream side.
- **Cutctx compression** — tokens removed by SmartCrusher, LiveZone, CodeCompressor, LogCompressor, etc. Observed on the proxy side.
- **Semantic cache** — tokens avoided by serving a prior near-duplicate request from the response cache. Cross-provider.
- **Self-hosted prefix cache** — tokens served by vLLM Automatic Prefix Caching. Reported separately from provider cache.
- **Model routing** — tokens served by a cheaper model than the user originally requested, plus the resulting USD savings.

**Attribution invariant:** the total reported savings is the sum of per-source values, never the difference between raw and optimized input. The buyer's CFO sees the marginal value of Cutctx above and beyond their existing provider cache, in dollars, with a reproducible schema.

```bash
cutctx report buyer --format json   # full breakdown, machine-readable
cutctx savings --by-source --format json
cutctx integrations status         # which parsers are wired
```

</details>

<details>
<summary><b>Security & governance</b></summary>

- **LLM Firewall** — 27 regex patterns (injection, PII, jailbreak, data exfiltration) + streaming redactor.
- **Structured output validation** — jsonschema enforcement with 3x auto-retry on invalid JSON.
- **Multi-model ensemble** — asyncio.gather fan-out with evaluator model picks best response.
- **Budget cut-offs** — token/cost hard limits with streaming SSE truncation.
- **SSO/OAuth2** — JWT/JWKS, OIDC discovery, RFC 7662 introspection, timing-safe claim validation.
- **RBAC** — Viewer/Operator/Admin roles, 15+ permissions, wired into ALL admin endpoints.
- **Audit logging** — SQLite WAL-backed structured events, queryable with filters, JSONL export.
- **Entitlements** — 59-feature × 4-tier matrix (Builder/Team/Business/Enterprise) with runtime enforcement.

</details>

<details>
<summary><b>Pipeline internals</b></summary>

Cutctx exposes one stable request lifecycle across `compress()`, the SDK, and the proxy:

`Setup` → `Pre-Start` → `Post-Start` → `Input Received` → `Input Cached` → `Input Routed` → `Input Compressed` → `Input Remembered` → `Pre-Send` → `Post-Send` → `Response Received`

- **Transforms** do the work: CacheAligner, ContentRouter, SmartCrusher, CodeCompressor, Kompress-base, IntelligentContext / RollingWindow.
- **Pipeline extensions** observe or customize lifecycle stages via `on_pipeline_event(...)`.
- **Compression hooks** sit alongside the canonical lifecycle as an additional extension seam.
- **Proxy extensions** remain the server/app integration seam for ASGI middleware, routes, and startup policy.

Provider and tool-specific behavior lives under `cutctx/providers/` so core orchestration stays focused on lifecycle, sequencing, and policy.

- **CLI/tool slices**: `cutctx/providers/claude`, `copilot`, `codex`, `openclaw`
- **Provider runtime slices**: `cutctx/providers/claude`, `gemini`, plus shared backend/runtime dispatch in `cutctx/providers/registry.py`
- **Core files stay orchestration-first**: `wrap.py`, `client.py`, `cli/proxy.py`, and `proxy/server.py` delegate provider-specific env shaping, API target normalization, backend selection, and transport dispatch.

</details>

## Install

```bash
pip install "cutctx-ai[all]"          # Python, broad bundle (not every heavy/proprietary extra)
npm install cutctx-ai                 # TypeScript / Node
docker pull ghcr.io/cutctx/cutctx:latest
```

Granular extras: `[proxy]`, `[mcp]`, `[ml]` (Kompress-base), `[code]`, `[memory]`, `[relevance]`, `[image]`, `[agno]`, `[langchain]`, `[evals]`, `[pytorch-mps]` (Apple-GPU memory-embedder offload — set `CUTCTX_EMBEDDER_RUNTIME=pytorch_mps`). Requires **Python 3.10+**.

Using `pipx`? Choose a supported interpreter explicitly:

```bash
pipx install --python python3.13 "cutctx-ai[all]"
```

→ [Installation guide](https://cutctx.com/docs/installation) — Docker tags, persistent service, PowerShell, devcontainers.

### Corporate / SSL-inspection environments

If `pip install "cutctx-ai[all]"` fails with `CERTIFICATE_VERIFY_FAILED`
(`unable to get local issuer certificate`), your network uses **SSL inspection** — a MITM
proxy presenting a company-issued CA. The build backend (`maturin`) downloads `rustup` over a
connection your TLS stack doesn't trust. **Install Rust first** so the build doesn't fetch it:

```bash
# macOS / Linux
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh && rustup default stable
# Windows
winget install Rustlang.Rustup && rustup default stable
```

Restart your shell, then `pip install "cutctx-ai[all]"`. A prebuilt wheel avoids the Rust
build entirely where available: `pip install --only-binary cutctx-ai cutctx-ai`.

Two runtime assets are fetched over TLS; if they are blocked, trust your corporate CA via
`REQUESTS_CA_BUNDLE` / `SSL_CERT_FILE` / `CURL_CA_BUNDLE`:

- **`cdn.pyke.io`** — the ONNX Runtime for the Rust core. Alternatively pre-provide it with
  `ORT_STRATEGY=system` and `ORT_LIB_LOCATION=/path/to/onnxruntime`.
- **`huggingface.co`** — the `kompress-base` compression model. Pre-download it and run with
  `HF_HUB_OFFLINE=1`, or set `HF_ENDPOINT` to a trusted mirror.

Running with compression disabled (pure gateway) requires neither asset.

## cutctx learn

<p align="center">
  <img src="cutctx_learn.gif" alt="cutctx learn in action" width="720">
</p>

`cutctx learn` — mines failed sessions, writes corrections to `CLAUDE.md` / `AGENTS.md` / `GEMINI.md`.

## Documentation

| Start here                                                                    | Go deeper                                                                          |
|-------------------------------------------------------------------------------|------------------------------------------------------------------------------------|
| [Quickstart](https://cutctx.com/docs/quickstart)                | [Architecture](https://cutctx.com/docs/architecture)                 |
| [Proxy](https://cutctx.com/docs/proxy)                          | [How compression works](https://cutctx.com/docs/how-compression-works) |
| [MCP tools](https://cutctx.com/docs/mcp)                        | [CCR — reversible compression](https://cutctx.com/docs/ccr)          |
| [Memory](https://cutctx.com/docs/memory)                        | [Cache optimization](https://cutctx.com/docs/cache-optimization)     |
| [Failure learning](https://cutctx.com/docs/failure-learning)    | [Benchmarks](https://cutctx.com/docs/benchmarks)                    |
| [Configuration](https://cutctx.com/docs/configuration)          | [Limitations](https://cutctx.com/docs/limitations)                  |

## Compared to

Cutctx runs **locally**, covers **every** content type, works with every major framework, and is **reversible**.

|                                                                              | Scope                                          | Deploy                             | Local | Reversible |
|------------------------------------------------------------------------------|------------------------------------------------|------------------------------------|:-----:|:----------:|
| **Cutctx**                                                                 | All context — tools, RAG, logs, files, history | Proxy · library · middleware · MCP | Yes   | Yes        |
| [RTK](https://github.com/rtk-ai/rtk)                                        | CLI command outputs                            | CLI wrapper                        | Yes   | No         |
| [lean-ctx](https://github.com/yvgude/lean-ctx)                               | CLI commands, MCP tools, editor rules          | CLI wrapper · MCP                  | Yes   | No         |
| [Compresr](https://compresr.ai), [Token Co.](https://thetokencompany.ai)    | Text sent to their API                         | Hosted API call                    | No    | No         |
| OpenAI Compaction                                                            | Conversation history                           | Provider-native                    | No    | No         |

> **Attribution.** Cutctx ships with the excellent [RTK](https://github.com/rtk-ai/rtk) binary for shell-output rewriting — `git show --short`, scoped `ls`, summarized installers. Huge thanks to the RTK team; their tool is a first-class part of our stack, and Cutctx compresses everything downstream of it. Cutctx can also use [lean-ctx](https://github.com/yvgude/lean-ctx) as the selected CLI context tool; set `CUTCTX_CONTEXT_TOOL=lean-ctx` before running `cutctx wrap ...`.

## Contributing

```bash
git clone https://github.com/cutctx/cutctx.git && cd cutctx
pip install -e ".[dev]" && pytest
```

Devcontainers in `.devcontainer/` (default + `memory-stack` with Qdrant & Neo4j). See [CONTRIBUTING.md](CONTRIBUTING.md).

## Community

- **[Discord](https://discord.gg/yRmaUNpsPJ)** — questions, feedback, war stories.
- **[Kompress-v2-base on HuggingFace](https://huggingface.co/cutctx/kompress-v2-base)** — the model behind our text compression.

## License

Open-core: the client (compression engine, proxy, SDKs, CLI, MCP server, base model) is **Apache 2.0**; the commercial core (control plane, enterprise modules, agent-tuned models) is **proprietary, All Rights Reserved**. See **[LICENSING.md](LICENSING.md)** (authoritative boundary), [LICENSE](LICENSE), and [LICENSE-COMMERCIAL](LICENSE-COMMERCIAL).
