# Headroom Sales Deck Outline

## Slide 1: Title
**Headroom — Compress. Cache. Conquer.**
*The context layer for AI agents that cuts token costs 60-95%*

## Slide 2: The Problem
- AI agents are eating your LLM budget
- Average team spends $5k-$50k/month on API calls
- Context grows with every conversation turn
- Cache misses mean you pay for the same tokens twice
- No visibility into what's consuming your budget

## Slide 3: The Solution
Headroom sits between your agents and LLM providers:
- **SmartCrusher** — JSON-aware compression (60-80% reduction)
- **CodeCompressor** — AST-aware code compression (70-90%)
- **Kompress** — ML-based compression (80-95%)
- **CCR** — Reversible compression (lossless, decompress anytime)
- **CacheAligner** — Cross-request cache alignment
- **Cross-Agent Memory** — Share context between agents

## Slide 4: How It Works
```
Agent Request → Headroom Proxy → Compressed Context → LLM Provider
                    ↓
              Cache Layer (70% hit rate)
                    ↓
              Analytics Dashboard
```

**3 deployment modes:**
1. **Proxy** — Drop-in, zero code changes
2. **SDK** — Python/TypeScript/Go/Java libraries
3. **MCP Server** — For Claude Code, Cursor, etc.

## Slide 5: Results
| Metric | Before Headroom | After Headroom |
|--------|----------------|----------------|
| Monthly token spend | $15,000 | $3,200 |
| Cache hit rate | 12% | 67% |
| Context per request | 8,000 tokens | 1,200 tokens |
| API latency | 2.1s | 1.8s |

*Based on average customer results*

## Slide 6: Pricing
| Tier | Price | Best For |
|------|-------|----------|
| Builder | Free | Individual developers |
| Team | $1,500/mo | Small teams (5-10 devs) |
| Business | $3,500/mo | Growing companies |
| Enterprise | Custom | Large orgs, self-hosted |

**ROI:** Team tier pays for itself at ~$5k/mo LLM spend

## Slide 7: Competitive Moat
1. **CCR (Reversible Compression)** — Only tool that lets you decompress
2. **6 Algorithms** — Best compression for every data type
3. **Cross-Agent Memory** — Share context between Claude, GPT, Gemini
4. **headroom learn** — ML that improves over time
5. **Open Core** — Apache 2.0 OSS + commercial features

## Slide 8: Who Uses Headroom
- AI-native startups (saving 60-80% on API costs)
- Engineering orgs with $5k+ monthly LLM spend
- Platform teams managing multiple AI agents
- Multi-provider teams (OpenAI + Anthropic + Google)

## Slide 9: Enterprise Features
- Self-hosted deployment (Docker/K8s/Helm/Air-gap)
- SSO/OIDC + RBAC
- Audit logging
- Budget controls + policy presets
- Fleet management (manage 100+ agents)
- SLA + premium support

## Slide 10: Next Steps
1. **Free trial** — 14 days, no credit card
2. **ROI calculator** — See your savings in 2 minutes
3. **Pilot program** — We'll set it up for you

**Contact:** sales@headroom.sh
**Website:** headroom.sh
