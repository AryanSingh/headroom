# 001. Vision

**Status:** done

## What Cutctx is
Cutctx is a context-compression proxy for AI provider APIs. It sits between coding tools and provider APIs, reducing token usage before requests reach the model.

## Core value proposition
1. Token savings through compression, cache stabilization, and transport slimming
2. Lower API spend before provider transmission
3. Better effective context windows by removing repeated waste
4. Local-first privacy by default
5. Compatibility with existing tools through proxy, SDK, CLI, and MCP surfaces

## What Cutctx is not
- a model provider
- a prompt data store by default
- a billing platform
- a generic logging product

## Design principles

### 1. Local-first privacy
Prompt data should stay local unless a user explicitly exports it.

### 2. Transparent compression
Users should be able to see what was compressed, why, and where savings came from.

### 3. Composable integration
Cutctx should improve existing workflows without forcing users onto a new agent.

### 4. Production-ready defaults
Optional subsystems should degrade gracefully and safe defaults should work out of the box.

## Core guarantees
- Compression happens before provider transmission when enabled
- Prompt data does not leave the proxy by default
- Savings and cache behavior remain inspectable
- Integrations stay composable with existing AI tooling

## Target users
- Individual developers reducing personal AI coding costs
- Development teams sharing savings improvements and cache learnings
- Enterprises running self-hosted deployments with stronger privacy requirements
- Plugin and extension authors building on Cutctx seams

## Success metrics
- Token savings above 30 percent on eligible traffic
- Compression overhead below 50 ms per request
- Healthy cache-hit behavior on repeated-session traffic
- Zero prompt exfiltration by default

## Current strategic priorities
Cutctx's biggest next savings wins come from shrinking repeated scaffolding and stabilizing cache reuse, not just adding another generic compressor.

Priority order:
1. Tool schema compaction
2. API and MCP surface slimming
3. Reversible code payload minification
4. Shell and tool-output slimming
5. Token Optimizer style instrumentation
6. Prompt-cache remediation
7. Graphify runtime hardening
8. Minimal-build behavior

Roadmap reference:
- [Token-savings priorities](/Users/aryansingh/Documents/Claude/Projects/headroom/docs/specs/token-savings-priorities.md)
