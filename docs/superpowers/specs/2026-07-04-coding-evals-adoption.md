# Coding Evals: Applying Cursor's Evaluation Methodology to Cutctx

**Date:** 2026-07-04
**Source:** Naman Jain (Cursor) — "Coding Evals: From Code Snippets to Codebases" (AI Engineer Code Summit)
**Status:** Analysis & Design
**Author:** Aryan Singh

---

## 1. Executive Summary

Naman Jain (Cursor) traces four years of coding benchmark evolution — from single-line Pandas completions to multi-hour codebase transformations — and exposes the failure modes that emerge at each capability jump. The core finding: **every generation of AI capability breaks the previous generation's evaluation methodology.**

This talk is not about context management — it's about *evaluating* AI agents. Relevance to Cutctx is indirect but strategic: the evaluation methodology applies directly to Cutctx's compression quality measurement and the `cutctx learn` self-improvement system.

The key transferable ideas:
- **Binary pass/fail breaks for complex tasks** — use partial progress metrics
- **Static benchmarks become useless** — use dynamic eval sets sourced from real usage
- **Test suites alone are insufficient** — use LLM judges to detect reward hacking and quality loss
- **Synthetic test cases don't predict production** — ground evals in real-world sessions

---

## 2. Core Thesis

> *"My first project was generating single-line Pandas snippets. My last project was generating an entire codebase."*

### Four Generations of Coding Eval

| Gen | Era | Task | Metric | Failure Mode |
|-----|-----|------|--------|-------------|
| 1 | 2022 | Single-line completion (HumanEval) | Pass@k | Measures syntax, not semantics |
| 2 | 2023-24 | Repo-level patching (SWE-bench) | Test pass rate | Brittle test suites pass wrong solutions |
| 3 | 2025 | Multi-hour codebase transformations | Binary pass/fail | Misses partial progress; architectural quality invisible |
| 4 | 2026 | Full-codebase performance optimization | Real-world improvement | Synthetic benchmarks don't predict production |

### Three Persistent Problems

**1. Data contamination.** Models trained on the full internet have likely seen benchmark problems on Stack Overflow or GitHub. Static benchmarks become useless within months — models are "grading their own homework."

**2. Brittle test suites.** Test cases that pass semantically incorrect solutions while failing valid implementations. A solution can pass all tests but be unmaintainable, insecure, or non-idiomatic.

**3. Difficulty miscalibration.** Benchmarks cluster at either 80%+ (trivial for current models) or sub-1% (impossible). Neither extreme provides useful signal for improvement.

### Solutions

**Dynamic evaluation sets** — periodically refresh with problems released after the model's training cutoff. Solves contamination and allows recalibration of difficulty distributions as models improve.

**LLM judges / "Hack Detector"** — an LLM evaluator that detects non-idiomatic code patterns, reward hacking, and sophisticated exploitation. Provides nuanced verdicts beyond pass/fail.

**Partial progress metrics** — for long-horizon tasks, track intermediate completion, architectural consistency, and integration correctness. Not a single score but a profile.

**Real-world grounding** — source tasks from real commits (e.g., performance optimization patches from llama.cpp). Grade on improvement over human baseline, using real fuzzing and property-based testing.

---

## 3. Relevance to Cutctx

### Direct Application

| Cursor Insight | Cutctx Application | Actionability |
|---|---|---|
| Binary pass/fail breaks for complex tasks | Cutctx Learn uses binary failure detection | **High** — Add partial progress metrics |
| Static benchmarks become useless | Compression benchmarks use fixed test corpora | **Medium** — Dynamic eval set from real sessions |
| Test suites alone insufficient | Compression accuracy measured by token savings | **High** — LLM judge for context quality |
| LLM judge detects reward hacking | No detection of "compressed but useless" output | **High** — Add quality guarantee via probe questions |
| Real-world grounding predicts production | Cutctx Learn mines real sessions | **Medium** — Systematic eval set from session logs |
| Difficulty miscalibration | Compression benchmarks may cluster easy/hard | **Low** — Multi-difficulty eval sets (nice to have) |

### Current State

| Area | Current Cutctx | Gap |
|---|---|---|
| Compression accuracy | Token savings % reported | No measure of *information preservation* — what if we saved 80% of tokens but lost the key fact? |
| Cutctx Learn failure detection | Binary (failed/succeeded) | No partial progress — "3 of 5 attempts failed" instead of "degradation started at turn 12" |
| Benchmark corpora | Static files (`benchmarks/corpora/`) | Fixed set; could be contaminated or unrepresentative |
| Quality verification | AccuracyGuard (configurable strict/balanced/off) | Rule-based (function names, identifiers). No semantic/semantic quality check. |

---

## 4. Adoption Opportunities

### A — LLM Judge for Context Quality (Medium, 2-3 weeks)

The highest-impact idea. Add a `cutctx eval quality` command that uses an LLM to verify compression quality:

```
cutctx eval quality --input original.txt --compressed compressed.txt --probes probes.json

Output:
  Recall:      0.92 (92% of probe questions answerable from compressed)
  Precision:   0.88 (88% of compressed content is relevant to original task)
  Token ratio: 0.18 (82% compression)
  Quality:     GOOD
```

**How probe questions work:**
1. LLM generates N probe questions answerable from the original content
2. LLM attempts to answer each probe from the compressed content only
3. Recall = questions answerable after compression / total questions
4. Low recall → compression destroyed critical information

**Detects reward hacking:** A compressor that drops all content but preserves a high ratio would get recall=0. Links token savings to actual information preservation.

**Implementation sketch:**
```python
class ContextQualityJudge:
    def __init__(self, model: str = "claude-sonnet-4-5"):
        self.model = model
    
    async def evaluate(self, original: str, compressed: str, task_type: str) -> QualityReport:
        probes = await self._generate_probes(original, task_type)
        answers = await self._answer_from_compressed(compressed, probes)
        return QualityReport(
            recall=answers.correct / len(probes),
            precision=self._measure_relevance(compressed, task_type),
            token_ratio=len(compressed) / len(original),
        )
    
    async def _generate_probes(self, original: str, task_type: str) -> list[Probe]:
        # LLM generates N questions whose answers exist in original
        ...
```

### B — Partial Progress Metrics for Cutctx Learn (Small, 1 week)

Current `cutctx learn` mines failed sessions and reports binary findings:

```python
# Current: "Read failed 5 times" → 5 binary failures
# Proposed: track progress across retries
```

**New capabilities:**
- **Degradation detection**: "Agent accuracy dropped 40% between turn 5 and turn 15"
- **Recovery tracking**: "Agent self-corrected 3 of 7 failures"
- **Architectural consistency**: "Agent maintained same approach across 4 of 5 retries"

Implementation: extend the session analyzer to score each turn rather than classifying entire sessions as pass/fail.

### C — Dynamic Eval Set from Real Sessions (Medium, 2 weeks)

Instead of static benchmark files, build `cutctx eval dynamic` that:
1. Anonymizes real agent sessions from session logs
2. Creates compression challenges at each session's key decision points
3. Reports: "On 100 real sessions, Cutctx preserved critical content in 94 cases"
4. Refreshes the eval set periodically

This mirrors Cursor's approach of sourcing evals from real commits rather than curated problems.

### D — Multi-Difficulty Compression Benchmark (Small, 3 days)

Add stratified difficulty levels to compression benchmarks:

```python
# Current: run all benchmarks, report average
# Proposed: report by difficulty
```

| Difficulty | Content Type | Target Compression | Current Performance |
|---|---|---|---|
| Easy | JSON arrays, repeated logs | 80-95% | ✅ Achieved |
| Medium | Mixed code + prose | 60-80% | ⚠️ Needs work |
| Hard | High-density prose, dependency-heavy code | 30-50% | ❌ Quality risk |

This prevents the "cluster at 80%+ or 0%" problem — developers can see which content types still need improvement.

---

## 5. Where This Fits: The Full Stack (7 Talks)

```
APPLICATION LAYER
  Instruction  ← Supabase (Skills + MCP)
  Tool         ← Cloudflare (Code Mode)
  Session      ← Arize (Sub-agents)
  Memory       ← Neo4j K&Z (Context Graphs)
  Decision     ← Neo4j Blumenfeld (Decision Traces)

INFERENCE LAYER
  KV Cache     ← Baseten (STILL)

EVALUATION LAYER ◄── THIS TALK
  Eval methodology ← Cursor (Coding Evals)
  → Dynamic eval sets, LLM judges, partial progress
  → Directly feeds into Cutctx Learn + compression quality
```

The evaluation layer sits *above* everything — measuring whether the other layers are working correctly.

---

## 6. Validation Plan

### Phase 1: LLM Judge for Quality (2-3 weeks)

| Step | Action | Success Criteria |
|---|---|---|
| J1 | Design probe generation prompt | Generates 5-10 probes that are answerable from original content |
| J2 | Implement `ContextQualityJudge` class | Creates probes, answers from compressed, scores recall |
| J3 | Validate against known-good and known-bad compressions | Known-good → recall >0.9; known-bad → recall <0.5 |
| J4 | Wire into `cutctx eval quality` CLI command | Command produces structured JSON output |

### Phase 2: Partial Progress for Cutctx Learn (1 week)

| Step | Action | Success Criteria |
|---|---|---|
| P1 | Extend session analyzer to score per-turn accuracy | Turn-level scores instead of binary session classification |
| P2 | Implement degradation detection (sliding window over turns) | Flags sessions where accuracy drops >30% across 5 turns |
| P3 | Add recovery tracking | Reports "agent self-corrected X of Y failures" |
| P4 | Validate against 10 real session logs | Degradation detection matches manual analysis |

### Phase 3: Dynamic Eval Set (2 weeks)

| Step | Action | Success Criteria |
|---|---|---|
| D1 | Build anonymized session extractor | Strips PII; preserves content structure |
| D2 | Implement eval set builder | Creates compression challenges at session decision points |
| D3 | Run `cutctx eval dynamic` against 100 sessions | Produces reliable quality score |
| D4 | Compare static vs dynamic benchmark results | Dynamic shows different (more realistic) quality distribution |

### Success Gates

| Gate | Entry | Go/No-Go |
|---|---|---|
| **J1-J4** | Quality judge catches known-bad compressions | ✅ Phase 2 |
| **P1-P4** | Degradation detection matches manual analysis | ✅ Phase 3 |
| **D1-D4** | Dynamic eval produces stable, realistic scores | ✅ Feature complete |

---

## 7. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| LLM judge is expensive (extra API calls per eval) | Medium | Medium | Run judge only on demand (`cutctx eval quality`), not inline |
| LLM judge quality is inconsistent | Medium | High | Use strong model (Claude Sonnet 4.5); average over multiple runs |
| Probe generation is noisy — probes may not be answerable | High | Medium | Validate probes against original; discard if LLM can't answer from original |
| Partial progress metrics add complexity to learn pipeline | Medium | Low | Additive — existing binary detection continues unchanged |

---

## 8. Success Metrics

| Metric | Current Baseline | Target |
|---|---|---|
| Context quality judge recall detection | Not measured | Detects >90% of known-quality-loss cases |
| Cutctx Learn partial progress reporting | Binary only | Turn-level scores available |
| Dynamic eval set size | Static (5 files) | >100 real sessions |
| Eval set refresh frequency | Never | Weekly |

---

## 9. Recommendation

**Build in order: J1→J4 (LLM judge), then P1→P4 (partial progress), then D1→D4 (dynamic eval).**

The LLM quality judge (Phase 1) is the highest-value addition — it directly addresses the gap that Cutctx measures *compression ratio* but not *information preservation*. Without it, there's no way to know whether a 90% compression ratio means "efficient" or "destructive."

Partial progress metrics (Phase 2) upgrade Cutctx Learn from primitive binary classification to continuous quality monitoring. Low effort, immediate improvement to the self-improvement loop.

Dynamic eval set (Phase 3) is longer-term infrastructure that mirrors what Cursor built. Not urgent but important for avoiding benchmark contamination.

---

## 10. References

- Talk: "Coding Evals: From Code Snippets to Codebases" — Naman Jain, Cursor (AI Engineer Code Summit)
- Previous adoption analyses (all in `docs/superpowers/specs/`):
  - `2026-07-04-subagent-context-management-adoption.md` (Arize)
  - `2026-07-04-skills-mcp-context-graphs-adoption.md` (Supabase + Neo4j K&Z)
  - `2026-07-04-mcp-mega-context-problem-adoption.md` (Cloudflare)
  - `2026-07-04-decision-traces-adoption.md` (Neo4j Blumenfeld)
  - `2026-07-04-kv-cache-compaction-adoption.md` (Baseten)
