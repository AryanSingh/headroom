# Docs

This folder has two main tracks:

- `docs/spec/` for living product and governance documents
- `docs/specs/` for focused implementation specs and active roadmap notes

Links below are **repo-relative**. They previously pointed at absolute paths
under `Projects/cutctx/`, a directory that does not exist on a fresh checkout,
so every one of them was broken while the same files sat in this folder.

## Start here
- [**Handoff — 2026-07-28**](handoff-2026-07-28.md) — read first if you are
  picking up compression, savings reporting, or the release pipeline: what
  changed, what is measured, what is still open, and the traps.
- [Living spec](spec/SPEC.md)
- [Vision](spec/001-vision.md)
- [Token-savings priorities](specs/token-savings-priorities.md)

## Measured evidence

Every number in these is reproducible and carries its command. They also
record the **negative** results, so nobody re-runs a dead end.

- [Measured savings by engine](measured-savings.md) — per-engine, through a
  real proxy, including the zeros and why they are zero.
- [Why Codex traffic saves ~0%](why-codex-saves-nothing.md) — savings split by
  client, not model: codex 0.33% on 4.16B tokens vs claude-code 32.9%.
- [Head-to-head vs LLMLingua-2](benchmarks-vs-llmlingua.md) — matched-ratio
  comparison against the published baseline, plus the metric bias that was
  found and fixed.
- [Reversible code compression](reversible-code-compression.md) — 50.9% on
  source under four enforced contracts, and the economics for the default.

## Useful references
- [Graphify integration spec](graphify-integration-spec.md)
- [Task-aware compression](specs/task-aware-compression.md)
- [Semantic dedup](specs/semantic-dedup.md)
- [Compression profiles](specs/compression-profiles.md)
- [Model routing presets](content/docs/model-routing-presets.mdx)
- [Agent host coverage](agent-host-coverage.md)
