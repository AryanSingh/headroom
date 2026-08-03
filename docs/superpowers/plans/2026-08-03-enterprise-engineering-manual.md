# Enterprise Engineering Manual Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reusable, product-agnostic enterprise engineering manual that compiles from modular Markdown into a professional 200–300 page Markdown, PDF, and DOCX publication with executable examples, model-specific prompts, controls, KPIs, scorecards, runbooks, and templates.

**Architecture:** `engineering-handbook/` is the canonical source tree. `SUMMARY.md` defines publication order; Python validation and build scripts assemble the source, export catalogs, generate DOCX and PDF artifacts, and produce coverage reports. Product-agnostic guidance remains primary, while Cutctx application notes link to repository evidence.

**Tech Stack:** Markdown, YAML front matter, Python 3 from the bundled Codex runtime, `python-docx`, ReportLab, PyYAML, Markdown parsing utilities, TypeScript Playwright examples, GitHub Actions examples, Mermaid, CSV, and the bundled `soffice` binary for optional DOCX-to-PDF comparison.

## Global Constraints

- Modular Markdown under `engineering-handbook/` is the canonical source.
- The compiled PDF must contain 200–300 substantive pages without duplicated filler or artificial spacing.
- Every chapter must contain purpose, scope, owners, inputs, SOP, worked example, automation, Opus/Sonnet/Haiku prompts, checklist, evidence requirements, findings, KPIs, scorecard, failure patterns, exit criteria, and related assets.
- Every executable example must state dependencies, file placement, invocation, expected output, failure interpretation, and cleanup.
- Every control and KPI must have a stable unique identifier.
- Standards claims must cite current official sources and use paraphrase rather than wholesale reproduction.
- Product-specific Cutctx material must appear as a labeled application note, not as a universal requirement.
- Generated files under `dist/` must be reproducible from a clean checkout.
- Preserve unrelated user changes already present in the worktree.
- Shell commands must use the repository-required `rtk` prefix.

---

## Program file map

### Canonical publication files

- Create: `engineering-handbook/README.md`
- Create: `engineering-handbook/SUMMARY.md`
- Create: `engineering-handbook/metadata.yaml`
- Modify: `ENGINEERING_HANDBOOK.md`

### Governance

- Create: `engineering-handbook/governance/handbook-charter.md`
- Create: `engineering-handbook/governance/roles-and-accountability.md`
- Create: `engineering-handbook/governance/evidence-standard.md`
- Create: `engineering-handbook/governance/risk-severity-model.md`
- Create: `engineering-handbook/governance/control-schema.md`
- Create: `engineering-handbook/governance/kpi-schema.md`
- Create: `engineering-handbook/governance/exception-management.md`

### Chapters

- Create: `engineering-handbook/chapters/01-operating-manual.md`
- Create: `engineering-handbook/chapters/02-product-discovery.md`
- Create: `engineering-handbook/chapters/03-cli-engineering.md`
- Create: `engineering-handbook/chapters/04-desktop-engineering.md`
- Create: `engineering-handbook/chapters/05-dashboard-ui.md`
- Create: `engineering-handbook/chapters/06-api-backend.md`
- Create: `engineering-handbook/chapters/07-agent-integrations.md`
- Create: `engineering-handbook/chapters/08-routing-orchestration.md`
- Create: `engineering-handbook/chapters/09-memory-governance-security.md`
- Create: `engineering-handbook/chapters/10-reliability-performance.md`
- Create: `engineering-handbook/chapters/11-commercial-readiness.md`
- Create: `engineering-handbook/chapters/12-release-engineering.md`
- Create: `engineering-handbook/chapters/13-agent-orchestration.md`
- Create: `engineering-handbook/chapters/14-playwright-testing.md`
- Create: `engineering-handbook/chapters/15-chaos-engineering.md`
- Create: `engineering-handbook/chapters/16-database-migrations.md`
- Create: `engineering-handbook/chapters/17-ai-quality-evaluation.md`
- Create: `engineering-handbook/chapters/18-api-sdk-compatibility.md`
- Create: `engineering-handbook/chapters/19-production-observability.md`
- Create: `engineering-handbook/chapters/20-continuous-verification.md`

### Reusable assets

- Create: `engineering-handbook/runbooks/production-release.md`
- Create: `engineering-handbook/runbooks/rollback.md`
- Create: `engineering-handbook/runbooks/hotfix.md`
- Create: `engineering-handbook/runbooks/incident-response.md`
- Create: `engineering-handbook/runbooks/security-incident.md`
- Create: `engineering-handbook/runbooks/provider-outage.md`
- Create: `engineering-handbook/runbooks/failed-migration.md`
- Create: `engineering-handbook/runbooks/data-recovery.md`
- Create: `engineering-handbook/checklists/master-checklist.md`
- Create: `engineering-handbook/prompts/prompt-selection-guide.md`
- Create: `engineering-handbook/scorecards/engineering-health.md`
- Create: `engineering-handbook/scorecards/release-readiness.md`
- Create: `engineering-handbook/scorecards/security-maturity.md`
- Create: `engineering-handbook/scorecards/ai-quality.md`
- Create: `engineering-handbook/scorecards/commercial-readiness.md`
- Create: `engineering-handbook/templates/audit-report.md`
- Create: `engineering-handbook/templates/evidence-register.md`
- Create: `engineering-handbook/templates/finding.md`
- Create: `engineering-handbook/templates/release-decision.md`
- Create: `engineering-handbook/templates/incident-review.md`
- Create: `engineering-handbook/templates/threat-model.md`
- Create: `engineering-handbook/templates/migration-plan.md`
- Create: `engineering-handbook/templates/benchmark-report.md`
- Create: `engineering-handbook/templates/ai-evaluation-report.md`

### Examples and automation

- Create: `engineering-handbook/examples/playwright/package.json`
- Create: `engineering-handbook/examples/playwright/playwright.config.ts`
- Create: `engineering-handbook/examples/playwright/fixtures/auth.ts`
- Create: `engineering-handbook/examples/playwright/pages/dashboard.page.ts`
- Create: `engineering-handbook/examples/playwright/tests/release-critical-flow.spec.ts`
- Create: `engineering-handbook/examples/playwright/tests/accessibility.spec.ts`
- Create: `engineering-handbook/examples/playwright/tests/visual-regression.spec.ts`
- Create: `engineering-handbook/examples/playwright/tests/error-states.spec.ts`
- Create: `engineering-handbook/examples/api-contracts/openapi-contract-test.py`
- Create: `engineering-handbook/examples/migrations/expand-contract.sql`
- Create: `engineering-handbook/examples/migrations/validate-migration.sql`
- Create: `engineering-handbook/examples/chaos/provider-faults.py`
- Create: `engineering-handbook/examples/observability/service-alerts.yaml`
- Create: `engineering-handbook/examples/ai-evaluation/dataset.jsonl`
- Create: `engineering-handbook/examples/ai-evaluation/rubric.yaml`
- Create: `engineering-handbook/examples/ai-evaluation/evaluate.py`
- Create: `engineering-handbook/automation/validate_handbook.py`
- Create: `engineering-handbook/automation/build_handbook.py`
- Create: `engineering-handbook/automation/export_catalogs.py`
- Create: `engineering-handbook/automation/check_examples.py`
- Create: `engineering-handbook/automation/requirements.txt`
- Create: `engineering-handbook/automation/tests/test_validate_handbook.py`
- Create: `engineering-handbook/automation/tests/test_build_handbook.py`
- Create: `engineering-handbook/automation/tests/test_export_catalogs.py`

### Appendices

- Create: `engineering-handbook/appendices/owasp-mapping.md`
- Create: `engineering-handbook/appendices/nist-mapping.md`
- Create: `engineering-handbook/appendices/control-catalog.md`
- Create: `engineering-handbook/appendices/kpi-catalog.md`
- Create: `engineering-handbook/appendices/competitive-benchmarking.md`
- Create: `engineering-handbook/appendices/glossary.md`
- Create: `engineering-handbook/appendices/cutctx-reference-implementation.md`

---

### Task 1: Establish the handbook schema, manifest, and validation contract

**Files:**
- Create: governance, metadata, manifest, and validation files listed above.
- Test: `engineering-handbook/automation/tests/test_validate_handbook.py`

**Interfaces:**
- Consumes: approved design specification at `docs/superpowers/specs/2026-08-03-enterprise-engineering-manual-design.md`.
- Produces: `load_manifest(root: Path) -> list[Path]`, `validate_handbook(root: Path) -> list[Finding]`, and stable metadata schemas used by every later task.

- [ ] **Step 1: Write validation tests for required chapter sections**

  Create fixtures with one complete chapter and one incomplete chapter. Assert that the incomplete chapter reports missing `Worked example`, `Opus prompt`, `Sonnet prompt`, `Haiku prompt`, `Checklist`, `KPIs`, and `Exit criteria` sections.

- [ ] **Step 2: Write tests for duplicate control and KPI IDs**

  Add fixture content containing repeated `SEC-AUTH-001` and `KPI-REL-001` identifiers. Assert that validation returns one duplicate finding for each identifier.

- [ ] **Step 3: Run the validation tests and confirm failure**

  Run: `rtk pytest engineering-handbook/automation/tests/test_validate_handbook.py -q`

  Expected: collection or import failure because `validate_handbook.py` does not exist.

- [ ] **Step 4: Implement metadata, manifest loading, and validation**

  Implement `Finding` as a dataclass with `code`, `path`, `message`, and `severity`. Parse `SUMMARY.md`, scan chapter headings, scan control and KPI identifiers, validate local links, and reject placeholder markers.

- [ ] **Step 5: Run validation tests**

  Run: `rtk pytest engineering-handbook/automation/tests/test_validate_handbook.py -q`

  Expected: all validation tests pass.

- [ ] **Step 6: Commit the foundation contract**

  Commit only Task 1 files with message `docs: establish handbook publication contract`.

### Task 2: Build the publication and catalog exporters

**Files:**
- Create: `engineering-handbook/automation/build_handbook.py`
- Create: `engineering-handbook/automation/export_catalogs.py`
- Create: `engineering-handbook/automation/tests/test_build_handbook.py`
- Create: `engineering-handbook/automation/tests/test_export_catalogs.py`
- Create: `engineering-handbook/automation/requirements.txt`

**Interfaces:**
- Consumes: `SUMMARY.md`, `metadata.yaml`, and validated Markdown.
- Produces: `build_markdown(root: Path, output: Path)`, `build_docx(root: Path, output: Path)`, `build_pdf(root: Path, output: Path)`, and `export_catalogs(root: Path, output_dir: Path)`.

- [ ] **Step 1: Write assembly and catalog tests**

  Assert that manifest order controls the assembled Markdown, front matter is removed from chapter bodies, the publication title appears once, control CSV columns equal `id,title,requirement,applicability,owner,frequency,standard`, and KPI CSV columns equal `id,name,decision,calculation,source,frequency,owner,target,warning`.

- [ ] **Step 2: Run build tests and confirm failure**

  Run: `rtk pytest engineering-handbook/automation/tests/test_build_handbook.py engineering-handbook/automation/tests/test_export_catalogs.py -q`

  Expected: import failure for missing build and export modules.

- [ ] **Step 3: Implement Markdown, DOCX, PDF, and CSV generation**

  Use `python-docx` for DOCX, ReportLab for PDF, PyYAML for metadata, and the bundled Python executable documented in `engineering-handbook/README.md`. Add page numbers, title page, headers, footers, heading hierarchy, tables, code-block styling, and explicit page breaks between volumes.

- [ ] **Step 4: Run build tests**

  Run: `rtk pytest engineering-handbook/automation/tests/test_build_handbook.py engineering-handbook/automation/tests/test_export_catalogs.py -q`

  Expected: all build and export tests pass.

- [ ] **Step 5: Commit publication tooling**

  Commit only Task 2 files with message `docs: add handbook publication pipeline`.

### Task 3: Author governance, control language, and core templates

**Files:**
- Create: all files under `engineering-handbook/governance/` and `engineering-handbook/templates/` listed in the program file map.

**Interfaces:**
- Consumes: Task 1 schemas.
- Produces: the normative control, evidence, finding, risk, exception, KPI, audit, release, incident, migration, benchmark, and AI evaluation formats used by all chapters.

- [ ] **Step 1: Author governance documents**

  Define E0–E4 evidence levels, P0–P3 severity, required/recommended/contextual applicability, exception expiry, retest conditions, decision ownership, and anti-gaming rules.

- [ ] **Step 2: Author templates with completed examples**

  Each template must include field instructions followed by one completed fictional-product example. Completed examples must avoid real credentials, customer data, and unsupported compliance claims.

- [ ] **Step 3: Validate governance assets**

  Run: `rtk proxy python3 engineering-handbook/automation/validate_handbook.py engineering-handbook`

  Expected: no schema, identifier, placeholder, or link findings in governance and template files.

- [ ] **Step 4: Commit governance and templates**

  Commit only Task 3 files with message `docs: add handbook governance and templates`.

### Task 4: Author Volume I and product discovery chapters

**Files:**
- Create: Chapters 1–2 and the master checklist.

**Interfaces:**
- Consumes: governance and template contracts.
- Produces: the audit operating workflow, capability mapping system, evidence lifecycle, and chapter reference pattern used by Chapters 3–20.

- [ ] **Step 1: Author Chapter 1**

  Include audit intake, scoping, risk mapping, evidence planning, execution, finding review, decision, retest, and closure. Add a complete API-release audit example and three model-specific prompts.

- [ ] **Step 2: Author Chapter 2**

  Include repository, runtime, route, command, data, provider, feature-flag, enterprise, and ownership discovery. Add a capability matrix example and automation commands.

- [ ] **Step 3: Add workflow checklists, KPIs, and scorecards**

  Include audit coverage, unknown-capability rate, evidence freshness, finding escape rate, retest latency, and exception age.

- [ ] **Step 4: Validate and commit Volume I foundation**

  Run handbook validation and commit with message `docs: author audit operations volume`.

### Task 5: Author Chapters 3–10 for product and platform engineering

**Files:**
- Create: `engineering-handbook/chapters/03-cli-engineering.md` through `10-reliability-performance.md`.
- Create: related checklists, prompts, examples, and scorecards referenced by these chapters.

**Interfaces:**
- Consumes: chapter contract and governance schemas.
- Produces: complete CLI, desktop, dashboard, API, integration, routing, memory, security, reliability, performance, and scale practices.

- [ ] **Step 1: Author CLI and desktop chapters**

  Include non-interactive behavior, configuration precedence, exit codes, streaming, IPC, local storage, upgrades, failure recovery, and real command examples.

- [ ] **Step 2: Author dashboard and API chapters**

  Include UI state matrices, accessibility, contract tests, authorization, idempotency, queues, webhooks, persistence, and error-envelope examples.

- [ ] **Step 3: Author integration, routing, and memory chapters**

  Include cross-harness parity, actual-versus-configured routing evidence, fallback, session continuity, isolation, replay, policy enforcement, and threat paths.

- [ ] **Step 4: Author reliability and performance chapter**

  Include workload design, percentile targets, warm/cold measurements, capacity, recovery, queue and cache metrics, and a complete load-test evidence example.

- [ ] **Step 5: Add Cutctx application notes**

  Link to `codemap.md`, `docs/project-architecture.md`, `docs/security-and-privacy.md`, `docs/observability.md`, and relevant verification chapters without converting Cutctx behavior into universal controls.

- [ ] **Step 6: Validate and commit Chapters 3–10**

  Run handbook validation and commit with message `docs: author product and platform engineering volume`.

### Task 6: Build and verify the Playwright example suite

**Files:**
- Create: all files under `engineering-handbook/examples/playwright/`.
- Create: `engineering-handbook/chapters/14-playwright-testing.md`.

**Interfaces:**
- Consumes: a deterministic local fixture described in the example README.
- Produces: executable `npm` scripts `test`, `test:a11y`, `test:visual`, and `test:errors` plus chapter instructions.

- [ ] **Step 1: Create the example package and configuration**

  Pin Playwright and accessibility dependencies, define Chromium, Firefox, WebKit, desktop, and mobile projects, configure traces on first retry, and route artifacts to `test-results/`.

- [ ] **Step 2: Implement authenticated fixtures and page objects**

  Provide storage-state setup, role-based fixtures, a dashboard page object, and stable role/label/test-id locators.

- [ ] **Step 3: Implement four executable test files**

  Cover a release-critical journey, accessibility scan, visual comparison, and loading/empty/error/unauthorized states with network interception.

- [ ] **Step 4: Install and execute the example suite**

  Run: `rtk npm install --prefix engineering-handbook/examples/playwright`

  Run: `rtk npm run test --prefix engineering-handbook/examples/playwright`

  Expected: all tests pass against the documented local fixture; if the fixture is intentionally embedded, its start and stop commands must be part of the test script.

- [ ] **Step 5: Author Chapter 14 and commit**

  Explain fixtures, locators, mocking, traces, visual baselines, accessibility, flake diagnosis, sharding, CI artifacts, and evidence retention. Commit with message `docs: add executable Playwright testing manual`.

### Task 7: Author security controls, OWASP mappings, and incident runbooks

**Files:**
- Create: `engineering-handbook/appendices/owasp-mapping.md`
- Create: `engineering-handbook/appendices/nist-mapping.md`
- Create: `engineering-handbook/appendices/control-catalog.md`
- Create: security-related runbooks and Chapter 9 security expansions.

**Interfaces:**
- Consumes: current official OWASP and NIST sources verified during this task.
- Produces: unique `SEC-*` controls, standards mappings, security checklists, threat-model examples, and incident response procedures.

- [ ] **Step 1: Verify official standards versions and URLs**

  Record source title, edition, official URL, retrieval date, and scope. Use only official OWASP and NIST sources for normative mappings.

- [ ] **Step 2: Author security control families**

  Cover architecture, authentication, session, authorization, validation, cryptography, secrets, logging, data protection, API security, supply chain, deployment, and incident readiness.

- [ ] **Step 3: Author threat-model and security-incident examples**

  Include asset inventory, trust boundaries, abuse cases, controls, detection, containment, evidence preservation, recovery, and disclosure decision points.

- [ ] **Step 4: Validate mappings and commit**

  Run identifier, citation, and link validation. Commit with message `docs: add security controls and incident operations`.

### Task 8: Author database migration, release, chaos, and production operations assets

**Files:**
- Create: Chapters 12, 15, 16, 19, and 20.
- Create: migration SQL examples, release runbooks, rollback, hotfix, failed migration, data recovery, provider outage, and observability examples.

**Interfaces:**
- Consumes: governance, controls, and build tooling.
- Produces: operational SOPs and executable examples for release and recovery decisions.

- [ ] **Step 1: Author expand-and-contract migration examples**

  Include additive schema, dual read/write, backfill, validation, cutover, cleanup, interruption recovery, and rollback or roll-forward criteria.

- [ ] **Step 2: Author release and rollback runbooks**

  Include triggers, roles, artifacts, canary thresholds, commands, migration sequencing, abort conditions, communication, recovery verification, and evidence packets.

- [ ] **Step 3: Author chaos and observability examples**

  Include provider latency, rate limit, malformed response, storage exhaustion, worker crash, Prometheus alerts, SLOs, error budgets, correlation, and runbook linkage.

- [ ] **Step 4: Author continuous verification automation templates**

  Include GitHub Actions examples for validation, contracts, Playwright, security, performance budgets, artifact upload, canary gates, and release evidence.

- [ ] **Step 5: Validate and commit operations volume**

  Commit with message `docs: add release data and production operations manual`.

### Task 9: Author AI systems engineering and executable evaluation assets

**Files:**
- Create: Chapters 13 and 17.
- Create: AI dataset, rubric, evaluator, prompt families, AI scorecard, and evaluation report template.

**Interfaces:**
- Consumes: JSONL dataset records with `id`, `task`, `input`, `expected`, `tags`, and `risk`; YAML rubric criteria with weights.
- Produces: evaluation JSON and Markdown reports containing quality, cost, latency, safety, tool, and routing metrics.

- [ ] **Step 1: Author task taxonomy and dataset guidance**

  Cover representative sampling, leakage, versioning, golden answers, property checks, human review, privacy, and retention.

- [ ] **Step 2: Implement the evaluation example**

  Implement deterministic checks, weighted rubric scoring, pairwise comparison input, judge calibration fields, cost and latency calculations, and routing-policy comparison.

- [ ] **Step 3: Author Opus, Sonnet, and Haiku prompt libraries**

  Create architecture, threat, release, focused review, test design, evidence analysis, inventory, normalization, and regression-triage prompts with explicit schemas and escalation rules.

- [ ] **Step 4: Run evaluation example tests**

  Run the evaluator against the bundled dataset and assert stable metric calculations without requiring paid model calls.

- [ ] **Step 5: Validate and commit AI volume**

  Commit with message `docs: add AI systems evaluation manual`.

### Task 10: Author API compatibility, commercial readiness, and competitive benchmarking

**Files:**
- Create: Chapters 11 and 18.
- Create: API contract test example, commercial-readiness scorecard, competitive-benchmarking appendix, and benchmark report template.

**Interfaces:**
- Consumes: versioned API schema, SDK support matrix, comparable benchmark workloads, and evidence standards.
- Produces: compatibility procedures, benchmark protocol, buyer-evidence framework, and measured-claim review process.

- [ ] **Step 1: Author API and SDK compatibility procedures**

  Cover request and response schemas, streaming events, errors, pagination, retries, idempotency, old-client/new-server matrices, deprecation, and breaking-change communication.

- [ ] **Step 2: Implement contract-test example**

  Provide an executable Python example that validates documented requests and responses against a local schema fixture.

- [ ] **Step 3: Author commercial-readiness and benchmark framework**

  Separate measured facts, controlled observations, analyst judgment, and vendor claims. Define environment controls, workload parity, quality rubrics, cost, performance, reliability, review dates, and public-claim approval.

- [ ] **Step 4: Validate and commit compatibility and commercial assets**

  Commit with message `docs: add compatibility and benchmarking manual`.

### Task 11: Complete all scorecards, KPIs, checklists, and report templates

**Files:**
- Create or complete all files under `engineering-handbook/checklists/`, `scorecards/`, `templates/`, and `appendices/kpi-catalog.md`.

**Interfaces:**
- Consumes: controls and metrics defined by Chapters 1–20.
- Produces: complete catalogs and report assets with unique IDs and calculation details.

- [ ] **Step 1: Reconcile every chapter control and checklist**

  Ensure each workflow step maps to a control, evidence artifact, owner, frequency, and failure action.

- [ ] **Step 2: Complete KPI definitions**

  Define numerator, denominator or calculation, data source, target, warning, owner, frequency, distortion risks, and interpretation for every KPI.

- [ ] **Step 3: Complete scorecards and worked reports**

  Provide scoring rules, gates, weighting, non-compensating critical controls, and a completed fictional-product example for every scorecard and report template.

- [ ] **Step 4: Export and inspect catalogs**

  Run: `rtk proxy python3 engineering-handbook/automation/export_catalogs.py engineering-handbook dist`

  Expected: control and KPI CSV files contain unique IDs and all required columns.

- [ ] **Step 5: Commit reusable asset library**

  Commit with message `docs: complete handbook checklists scorecards and reports`.

### Task 12: Integrate, compile, render, and verify the full manual

**Files:**
- Modify: `engineering-handbook/SUMMARY.md`
- Modify: `ENGINEERING_HANDBOOK.md`
- Generate: `dist/Enterprise_Engineering_Manual.md`
- Generate: `dist/Enterprise_Engineering_Manual.docx`
- Generate: `dist/Enterprise_Engineering_Manual.pdf`
- Generate: `dist/control-catalog.csv`
- Generate: `dist/kpi-catalog.csv`

**Interfaces:**
- Consumes: all canonical source files and automation.
- Produces: final publication artifacts and verification evidence.

- [ ] **Step 1: Run the full automated test suite**

  Run: `rtk pytest engineering-handbook/automation/tests -q`

  Expected: zero failures.

- [ ] **Step 2: Validate content coverage and examples**

  Run: `rtk proxy python3 engineering-handbook/automation/validate_handbook.py engineering-handbook`

  Run: `rtk proxy python3 engineering-handbook/automation/check_examples.py engineering-handbook`

  Expected: zero errors and complete coverage for all 20 chapters.

- [ ] **Step 3: Build all publication outputs**

  Run: `rtk proxy python3 engineering-handbook/automation/build_handbook.py engineering-handbook dist`

  Expected: Markdown, DOCX, PDF, control CSV, KPI CSV, and coverage report are generated.

- [ ] **Step 4: Verify page count and document structure**

  Confirm the PDF page count is between 200 and 300, the DOCX opens without repair warnings, volume and chapter headings appear in the table of contents, code blocks remain legible, tables fit page width, and page numbers render.

- [ ] **Step 5: Render representative pages for visual QA**

  Inspect the title page, contents, one chapter opener per volume, security tables, Playwright code, migration SQL, scorecards, runbooks, and report templates. Correct clipping, orphan headings, broken tables, and unreadable code.

- [ ] **Step 6: Update the root entry point**

  Replace the compact root handbook with a concise overview, source-tree link, build instructions, and links to generated outputs.

- [ ] **Step 7: Run final repository-scoped verification**

  Review `rtk git diff -- engineering-handbook ENGINEERING_HANDBOOK.md dist` and confirm unrelated worktree changes remain untouched.

- [ ] **Step 8: Commit final integration**

  Commit only handbook source, automation, root entry point, and approved generated artifacts with message `docs: publish enterprise engineering manual`.

---

## Review gates

1. **Foundation gate:** schema, validation, and build tests pass.
2. **Volume gate:** each volume satisfies the chapter contract and has no unresolved P0 or P1 editorial findings.
3. **Executable-example gate:** Playwright, contract, migration validation, and AI evaluation examples run in documented fixtures.
4. **Standards gate:** OWASP and NIST mappings cite official current sources and pass link review.
5. **Publication gate:** Markdown, DOCX, and PDF build from canonical source and pass visual sampling.
6. **Completion gate:** the final PDF contains 200–300 substantive pages and all 20 chapters meet coverage requirements.

## Plan self-review result

- All 22 design-specification sections map to at least one task.
- The 20 chapters map to Tasks 4–10.
- Playwright scripts map to Task 6.
- Security standards and controls map to Task 7.
- Database, release, incident, chaos, and observability assets map to Task 8.
- AI prompts and evaluation map to Task 9.
- Competitive benchmarking and API compatibility map to Task 10.
- Checklists, scorecards, KPIs, automation templates, and report templates map to Task 11.
- PDF, DOCX, page-count, visual, and clean-build verification map to Task 12.
