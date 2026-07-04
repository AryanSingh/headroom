# Cutctx - Product Manager Audit Report

## 1. Existing Features
Cutctx is a local-first context control plane for AI agents, offering a robust set of features to compress context, reduce token usage, and manage agent memory:
- **Deployment Modes**: Proxy server, Python/TypeScript library, Agent Wrap CLI (Claude Code, Cursor, Codex, etc.), and MCP Server.
- **Compression Pipeline**: 12 specialized algorithms (e.g., SmartCrusher for JSON, CodeCompressor for AST, Kompress-base for prose, Graphify for code graphs).
- **CCR (Reversible Compression)**: Lossless retrieval of compressed context on demand using `cutctx_retrieve`.
- **Memory System**: Cross-agent, hierarchical persistent memory with temporal versioning and agent provenance tracking.
- **Cutctx Learn**: Analyzes failed sessions to generate corrections for agent instructions (`CLAUDE.md`, `AGENTS.md`).
- **Enterprise Capabilities**: SSO, RBAC, Audit Logging, SCIM provisioning, LLM Firewall (regex matching for PII/injection), and granular entitlements.
- **Query-Aware Compression**: Dynamically adjusts compression aggressiveness based on the user's task type.

## 2. Missing Features
While Cutctx is feature-rich, there are areas for expansion:
- **Native IDE Extensions**: Currently, IDEs like Cursor require CLI wrapping and manual config pasting. Native VS Code or JetBrains extensions could provide a smoother, UI-driven configuration and visibility experience.
- **Cloud-Hosted SaaS Option**: The strict local-first architecture is a massive selling point for enterprise/security, but a fully managed cloud API version could capture smaller teams unwilling to manage their own proxies or infrastructure.
- **Formal Compliance Certifications**: SOC 2, formal DPA/MSA, and third-party audit reports are not available natively out-of-the-box (flagged as requiring external validation).
- **GUI Dashboard Expansion**: A more comprehensive web interface for analyzing memory graphs and tweaking compression thresholds visually.

## 3. Competitor Gaps
Cutctx positions itself favorably against competitors (RTK, lean-ctx, Compresr, OpenAI Compaction) by covering several critical gaps:
- **Reversibility (CCR)**: Most competitors perform lossy compression. Cutctx uniquely caches the original and allows the LLM to retrieve it.
- **Cross-Agent / Cross-Provider Memory**: No competitor offers a unified memory store that shares context between different tools (e.g., Claude and Codex) while providing temporal versioning and LLM-driven deduplication.
- **Local-First Proxy**: Unlike API-based solutions (Compresr), Cutctx ensures data never leaves the network for compression, fulfilling strict enterprise data governance requirements.

## 4. User Journey Friction & Onboarding Issues
- **Corporate Network SSL Issues**: Users in corporate environments with SSL inspection face `CERTIFICATE_VERIFY_FAILED` errors during `pip install` because of the Rust build dependency. The required workaround (installing Rust manually) creates a high friction point during initial onboarding.
- **Fragmented Installation Extras**: The `[all]` tag handles most use cases, but the granular extras (`[proxy]`, `[ml]`, `[code]`, `[memory]`, `[pytorch-mps]`) add cognitive load to setup. Users might be confused about which packages they actually need.
- **Manual Agent Configuration**: Commands like `cutctx wrap cursor` require the user to manually paste configuration snippets, breaking the "one-command" magic experience.
- **Air-Gap Setup Complexity**: Setting up air-gap mode requires pre-downloading HuggingFace models, providing local ONNX runtimes, and managing multiple environment variables (`HF_HUB_OFFLINE`, `CUTCTX_AIR_GAP`, `CUTCTX_LICENSE_HMAC_SECRET`).

## 5. Retention Issues
- **Agent Update Breakage**: Agent wrappers are inherently brittle. If Claude Code, Cursor, or Aider change their internal configuration paths or CLI arguments, the `cutctx wrap` commands could break, causing immediate churn until patched.
- **Trust in Reversibility**: If the LLM fails to realize it should use the `cutctx_retrieve` tool (e.g., a weaker model or poor prompting), the user will perceive the compression as lossy and detrimental to agent performance, leading them to uninstall.
- **Memory Bloat**: Despite semantic deduplication, long-lived projects might accumulate massive memory databases. If search relevance degrades because the vector index gets too noisy, users might experience degraded LLM performance over time.
