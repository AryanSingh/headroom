# Context Strategy Integrity Code Review

## Scope

- Base: `8147b0c7`
- Reviewed implementation: `324e9bf8` plus the review remediations recorded after that commit
- Requirements:
  - `docs/superpowers/specs/2026-07-19-context-strategy-integrity-design.md`
  - `docs/superpowers/plans/2026-07-19-context-strategy-integrity.md`

## Strengths

- Structural strategies now preserve tool protocol integrity across Anthropic,
  OpenAI Chat, and OpenAI Responses shapes.
- CCR writes are staged until byte-range surgery succeeds, and snapshot session
  state advances only after a successful mutation.
- Provider dispatch separates licensed Anthropic CCR from strategy-gated OpenAI
  and Bedrock CCR, with byte-level integration coverage.
- Snapshot payloads are content-addressed without wall-clock data and remain
  compatible with legacy stored documents containing extra fields.
- Selection and application telemetry are separated, and invalid header values
  are both warned and counted.

## Findings and Resolution

### Critical

None.

### Important

1. Unknown or malformed tool protocol items away from a snapshot boundary were
   not initially fail-closed. The range validator now rejects any partition
   containing an unlinked protocol item, with a regression fixture placing the
   unknown item away from both boundaries.
2. Generic application failure warnings initially omitted the provider field
   required by the design. All generic and Bedrock paths now emit
   `context_strategy_application_failed` with request, provider, strategy, and
   bounded error context.
3. The public application metric helper initially accepted arbitrary label
   strings. Strategy and outcome values are now normalized to fixed
   vocabularies with an `other` fallback.

### Minor

- Application outcome matching is repeated across generic, Bedrock invoke, and
  Bedrock streaming paths. A future refactor could centralize it, but doing so
  in this safety fix would increase churn without changing behavior.

## Verification Reviewed

- `cargo test --workspace`: 1489 passed, 3 ignored.
- `cargo test --workspace --all-features`: 1490 passed, 3 ignored.
- `cargo clippy --workspace --all-targets --all-features -- -D warnings`: clean.
- `pytest tests/test_release_workflows.py -q`: 43 passed.
- Focused context strategy and Bedrock integration suites: passed.

## Assessment

Ready to merge. Post-review formatting, clippy, focused provider suites, the
all-features workspace suite, release-workflow tests, and whitespace checks all
passed. The all-features rerun also exposed and fixed an unrelated fingerprint
test that had been deleting the real install UUID while parallel tests read it.
