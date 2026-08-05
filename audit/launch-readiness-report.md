# Launch Readiness Report

**Candidate:** `main` at `be75d107` plus the release-prep correction in this change

**Assessment date:** 2026-08-05

**Decision:** **No-go for an unrestricted public/GA release. Go for a controlled pilot only after the remote CI run for this exact commit passes and the named operational owners accept the listed holds.**

## Engineering release gates

| Gate | Result | Evidence | Sign-off |
| --- | --- | --- | --- |
| Working tree baseline | Passed before release-prep work | `main` was clean and 166 commits ahead of `origin/main`; no unreviewed user changes were present. | Release engineering |
| Python regression suite | Passed | `.venv/bin/python -m pytest tests scripts/tests -q` collected 10,708 tests with one environment-dependent skip and completed without a failure. | Engineering |
| CI-pinned lint and format | Passed after remediation | `uvx ruff@0.9.4 check .` and `uvx ruff@0.9.4 format --check .` pass after formatting five EE release files. | Engineering |
| Type ratchet, secrets, repository hygiene | Passed | `scripts/mypy_ratchet.py`, `scripts/check_secret_patterns.py`, and `scripts/check_repo_hygiene.py` completed successfully. | Engineering |
| EE release path | Passed | `tests/test_compile_ee_script.py`, `tests/test_ee_release_evidence.py`, `tests/test_verify_ee_wheel.py`, and `tests/test_ee_release_pipeline.py`: 32 passed. | Engineering |
| OSS package artifact | Passed | `maturin build --release` produced the macOS ABI3 wheel; `scripts/assert_oss_wheel_clean.py` accepted it and the native extension imported. | Engineering |
| Dashboard unit, lint, and production build | Passed | 31 Node tests passed; ESLint passed with zero warnings; Vite production build completed. | Engineering |
| Dashboard accessibility and visual E2E | Passed | `dashboard/e2e/accessibility.spec.js` and `dashboard/e2e/visual-identity.spec.js` completed from the release check. | Engineering |
| Dependency audit | Passed | `npm --prefix dashboard audit --audit-level=high` completed without a high-severity finding. | Engineering |
| Version coherence | Passed | Python, Rust, TypeScript, OpenClaw, Helm, and release-please metadata each state `0.31.0`; `uv.lock` now matches the EE package version. | Release engineering |
| Remote CI for exact candidate | Pending | The 166 candidate commits have not yet been pushed, so GitHub has no CI result for their exact SHA. | Release engineering |

## Release automation and artifact status

| Item | Status | Required action |
| --- | --- | --- |
| `v0.31.0` tag | Present | Create the missing GitHub Release object to unblock release-please. |
| `v0.31.0` GitHub Release object | Blocked before this pass | Requires a repository writer account; the documented recovery command is `gh release create v0.31.0 --verify-tag --title "v0.31.0" --generate-notes`. |
| Current candidate | Not remote | Commit this release-prep correction, push `main`, and wait for required GitHub Actions gates. |
| Next semantic release | Not created | Once the old release object exists and the candidate reaches GitHub, release-please should create the next release PR. Its merge remains subject to the operational holds below. |

## Operational sign-offs still required

These are not source-code defects and cannot be completed from this repository.

| Gate | Current state | Required owner/action |
| --- | --- | --- |
| Alert delivery and on-call response | No Alertmanager receiver, route, escalation target, acknowledgement SLA, or staging delivery test is recorded. | Operations: configure receiver/routing, name on-call owner, and execute a staging alert test. |
| Release authority and rollback execution | Runbooks exist, but no release window, named release manager, deployed artifact digest, or production telemetry snapshot applies to this candidate. | Release Manager and SRE: approve the change record, cohort plan, stop authority, and rollback verification. |
| Support and customer communications | Support channel and customer-status owner are not named in the pilot materials. | Support Lead: name contact path, escalation owner, and customer communication channel. |
| Paid checkout email | The current license-email hook only logs issuance; it is not a customer email transport. | Commercial/Operations: configure and verify an idempotent external email provider before enabling checkout that relies on email delivery. |
| Legal and compliance | No qualified legal approval for customer terms/DPA is recorded. | Legal: approve the customer-facing terms and applicable DPA. |

## Go/no-go conditions

- **Controlled pilot:** Proceed only when the release-prep commit is pushed, the required GitHub Actions checks pass for that exact SHA, and the Release Manager/SRE accept the operational risk with an explicit rollout and rollback record.
- **Broad public GA:** Hold until every operational sign-off above has a named owner and recorded evidence. Do not represent alerting, support response, or license-email delivery as production-ready before then.

## Reproduction commands

```bash
rtk proxy zsh -lc '.venv/bin/python -m pytest tests scripts/tests -q'
rtk proxy zsh -lc 'uvx ruff@0.9.4 check .; uvx ruff@0.9.4 format --check .'
rtk proxy zsh -lc '.venv/bin/python scripts/mypy_ratchet.py; .venv/bin/python scripts/check_secret_patterns.py; .venv/bin/python scripts/check_repo_hygiene.py'
rtk proxy zsh -lc '.venv/bin/maturin build --release --out /tmp/cutctx-release-dist; .venv/bin/python scripts/assert_oss_wheel_clean.py /tmp/cutctx-release-dist'
rtk proxy zsh -lc 'npm --prefix dashboard test; npm --prefix dashboard run lint; npm --prefix dashboard run build; npm --prefix dashboard run test:e2e -- --reporter=line dashboard/e2e/accessibility.spec.js dashboard/e2e/visual-identity.spec.js; npm --prefix dashboard audit --audit-level=high'
```
