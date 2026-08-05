# Enterprise Engineering Manual Execution Addendum

This addendum is binding on the implementation plan at
`docs/superpowers/plans/2026-08-03-enterprise-engineering-manual.md`. It resolves
the mandatory revisions from `.slim/deepwork/plan-oracle-review.md`. Where the
original plan conflicts with this addendum, this addendum governs.

## 1. Generated-artifact policy

The repository will use a **source-only publication policy**.

- `engineering-handbook/` source, automation, fixtures, styles, lockfiles, and
  verification schemas are committed.
- `dist/`, rendered page PNGs, browser binaries, traces, screenshots, videos,
  caches, and local publication environments remain ignored.
- PDF, DOCX, assembled Markdown, CSV catalogs, prompt exports, coverage reports,
  checksums, and visual-QA ledgers are generated locally and published as CI or
  release artifacts when an external publication channel is configured.
- The root `ENGINEERING_HANDBOOK.md` links to canonical source and build
  instructions. It does not link to local `dist/` files as if they exist after
  clone.
- Task 12 verifies policy with `git check-ignore dist`,
  `git status --ignored --short dist`, and path-scoped staging of source files.
- The committed source includes `engineering-handbook/build/artifact-manifest.yaml`
  naming every generated output, its media type, and checksum role.

## 2. Authoritative publication architecture

DOCX is the layout authority. PDF is derived from the authoritative DOCX through
the bundled headless LibreOffice `soffice` binary. Direct ReportLab publication
is removed from the required path.

### Pinned runtimes

- Python interpreter:
  `/Users/aryansingh/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3`
- LibreOffice converter:
  `/Users/aryansingh/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override/soffice`
- Node interpreter:
  `/Users/aryansingh/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node`
- Python dependencies are exact-pinned in
  `engineering-handbook/automation/requirements.lock`.
- Node dependencies and browser versions are pinned by
  `engineering-handbook/examples/playwright/package-lock.json`.

### Semantic document model

`engineering-handbook/automation/document_model.py` defines renderer-neutral
nodes for:

- volumes, chapters, sections, and stable anchors;
- paragraphs, ordered and unordered lists, and task checkboxes;
- tables, repeated headers, captions, and source notes;
- code blocks with language and wrap policy;
- callouts, examples, controls, KPIs, prompts, and runbook steps;
- images, alt text, Mermaid diagrams, and captions;
- internal and external links;
- explicit volume and chapter page breaks; and
- publication metadata.

The Markdown parser is `markdown-it-py` with tables and task-list extensions.
Unsupported raw HTML causes a validation error unless a documented exception
suppresses the finding.

### TOC and navigation

The builder uses a deterministic two-pass process:

1. Build an authoritative DOCX with heading bookmarks and a provisional static
   contents table.
2. Convert the DOCX to PDF with headless LibreOffice.
3. Extract heading page numbers from the PDF using `pypdf` and `pdfplumber`.
4. Rebuild the DOCX with a static linked contents table containing page numbers.
5. Convert the final DOCX to the final PDF.
6. Add and verify PDF outlines that match the heading hierarchy.

The build fails if the second-pass heading pages differ from the static TOC.

### Style contract

Create:

- `engineering-handbook/build/styles/publication.yaml`
- `engineering-handbook/build/styles/fonts/README.md`
- `engineering-handbook/build/styles/reference.docx`

The style file defines page size, margins, typography, heading spacing, code
font, table widths, repeated headers, non-splitting rows, landscape sections,
callouts, captions, headers, footers, page numbers, chapter openers, and volume
breaks. Use fonts available in the bundled runtime or repository-approved
redistributable fonts. Record fallback behavior and inspect substitutions.

## 3. Early publication spike

Before bulk chapter authoring, Task 2 creates:

- `engineering-handbook/examples/publication-spike/pilot.md`
- `engineering-handbook/examples/publication-spike/diagram.mmd`
- `engineering-handbook/examples/publication-spike/README.md`
- `engineering-handbook/automation/tests/test_publication_spike.py`

The pilot includes all heading levels, links, a multi-page control table, a wide
KPI table, shell/Python/TypeScript/SQL/YAML/JSON code, lists, checklists,
callouts, source notes, Mermaid, a runbook decision table, page breaks, volume
breaks, and enough text to test TOC pagination.

Task 2 builds DOCX and PDF, renders every pilot page to PNG, records findings in
`dist/visual-qa/pilot-ledger.json`, fixes layout defects, and freezes the style
contract before chapter authoring begins.

Every later chapter work unit runs a publication smoke build. Every completed
volume records a page-count and layout snapshot.

## 4. Quantitative content and page budgets

The publication target is 200–300 substantive PDF pages, including front matter.

| Volume | Target words | Target pages |
| --- | ---: | ---: |
| I. Governance and audit operations | 18,000–24,000 | 30–40 |
| II. Product and platform engineering | 45,000–60,000 | 70–95 |
| III. Security, data, and production operations | 38,000–50,000 | 60–80 |
| IV. AI systems engineering | 24,000–34,000 | 40–55 |
| V. Release and commercial readiness | 18,000–26,000 | 30–45 |
| Front matter and appendices | 10,000–16,000 | 15–30 |

Per chapter target: 5,000–9,000 words and 7–13 pages. Narrow chapters may fall
to 3,500 words when their linked runbooks, examples, and templates carry the
depth. Security, database migrations, Playwright, AI evaluation, release, and
incident operations may reach 12,000 words.

Minimum asset counts:

- at least 20 complete chapter-level worked examples;
- at least 12 executable example packages or scripts;
- at least 8 operational runbooks;
- at least 12 completed report/template examples;
- at least 60 model-specific prompts, one Opus, Sonnet, and Haiku prompt per
  chapter, plus specialized prompts;
- at least 100 stable controls; and
- at least 50 KPIs with calculations and anti-gaming guidance.

A substantive page contains at least 150 extracted words or a complete table,
code example, diagram, checklist, runbook, scorecard, or template that occupies
most of the page. Title, copyright, intentional separators, and blank pages do
not count. Front matter may not exceed 12 pages.

If the manual is under 200 pages, deepen missing procedures and examples. If it
exceeds 300 pages, remove repetition, consolidate shared material, split wide
tables, or move reference catalogs to appendices. Spacing changes and artificial
breaks may not be used to hit the range.

## 5. Specialist work-unit split

Original Tasks 4–10 execute through these smaller work units:

1. Governance and Chapter 1
2. Chapter 2 and capability assets
3. Chapters 3–4
4. Chapters 5–6
5. Chapters 7–8
6. Chapters 9–10
7. Chapter 14 and Playwright package
8. Security standards registry and control catalog
9. Chapters 12 and 20 plus release automation
10. Chapters 15 and 19 plus chaos/observability assets
11. Chapter 16 plus migration harness and recovery runbooks
12. Chapters 13 and 17 plus AI evaluation package
13. Chapters 11 and 18 plus benchmarking and compatibility assets
14. Cross-catalog reconciliation and final templates

Each work unit has an explicit file allowlist, chapter-contract validation,
example execution where applicable, source review, editorial review, domain
review, and publication smoke build. Controls, KPIs, prompts, checklists, and
scorecards are authored with their chapter and reconciled incrementally.

## 6. Full validator and example-runner contract

Task 1 creates:

- `engineering-handbook/automation/schema.py`
- `engineering-handbook/automation/validate_handbook.py`
- `engineering-handbook/automation/check_examples.py`
- `engineering-handbook/automation/tests/fixtures/`
- tests for both false positives and false negatives.

The validator parses Markdown with `markdown-it-py` and checks:

- all 15 chapter-contract elements, including linked split assets;
- purpose, audience, scope, applicability, owners, inputs, outputs, and
  dependencies;
- worked-example preconditions, placement, dependencies, invocation, expected
  and failure output, interpretation, remediation, and cleanup;
- distinct Opus, Sonnet, and Haiku workload and output declarations;
- checklist control fields, evidence, frequency, owner, and failure action;
- runbook triggers, severity, roles, decisions, communication, containment or
  rollback, evidence, recovery, exit, and follow-up;
- KPI calculation, target, warning, source, owner, frequency, distortions, and
  anti-gaming fields;
- template instructions and completed-example markers;
- standards-registry references and uncited normative claims;
- duplicate IDs, malformed metadata, file links, anchors, images, and
  cross-references;
- Mermaid compilation;
- drafting markers and forbidden placeholders;
- complete `SUMMARY.md` coverage and orphan canonical files.

Exit codes: `0` clean, `1` blocking errors, `2` warnings-only, `3` execution or
configuration failure. Output supports human text and JSON. Suppressions require
an ID, reason, owner, and expiry date. Expired suppressions fail validation.

The example runner discovers example manifests, applies declared timeouts, uses
temporary directories, blocks production credentials and mutable network calls,
captures stdout/stderr/exit codes, runs cleanup, and emits JSON plus human
reports. Baseline examples must run offline.

## 7. Standards registry

Task 1 creates `engineering-handbook/standards/registry.yaml` and
`engineering-handbook/standards/README.md` before normative chapter authoring.

Each source record contains stable ID, publisher, exact title, edition/version,
publication date, official URL, immutable URL when available, retrieval date,
scope, normative/informative status, control families, copyright/paraphrase
note, and refresh policy.

The first edition registry includes verified official editions for:

- OWASP ASVS;
- OWASP Top 10;
- OWASP API Security Top 10;
- OWASP WSTG;
- OWASP SAMM;
- NIST SSDF;
- NIST incident response guidance;
- WCAG and relevant accessibility guidance;
- OpenTelemetry semantic conventions;
- NIST AI risk guidance; and
- OWASP AI/LLM security guidance.

Versions are pinned for the manual edition. Offline validation checks registry
references. A separate network-aware command checks official links.

## 8. Prompt-library structure

Task 1 creates:

- `engineering-handbook/prompts/schema.md`
- `engineering-handbook/prompts/opus/`
- `engineering-handbook/prompts/sonnet/`
- `engineering-handbook/prompts/haiku/`
- `engineering-handbook/prompts/prompt-selection-guide.md`

Every chapter work unit creates three prompt files or three uniquely anchored
prompt records. Metadata declares model family, workload type, objective,
inputs, boundaries, evidence, output schema, uncertainty, stop conditions, and
escalation. Validation rejects missing metadata and identical workload/output
declarations across the three families. Editorial review checks substantive
differences.

## 9. Reproducible executable-example packages

Every example package includes a README, manifest, pinned dependencies, fixtures,
non-interactive test command, expected-output fixture, timeout, and cleanup.

### Playwright

Add:

- deterministic local fixture server and static UI;
- `package-lock.json`;
- readiness and teardown through Playwright `webServer`;
- storage-state setup script;
- committed visual baseline policy and baseline images;
- GitHub Actions sharding and artifact-upload example;
- explicit browser installation and cache instructions;
- fixed OS, viewport, fonts, color profile, and browser baseline;
- ignored runtime artifacts; and
- separate verified scripts for aggregate, accessibility, visual, and error
  state tests.

Use `npm ci`, not floating `npm install`.

### API contracts

Add schema fixtures, request/response fixtures, tests, and expected reports.

### Migrations

Use a pinned SQLite baseline for portable offline execution and provide
PostgreSQL production notes separately. Add seed data, transaction assumptions,
interruption fixtures, validation tests, and cleanup.

### Chaos and observability

Use local deterministic fake-provider and metric fixtures. Do not require
production services.

### AI evaluation

Add unit tests, stable expected metrics, versioned token and pricing assumptions,
judge-calibration fixtures, and a no-paid-API baseline mode.

## 10. Final DOCX and PDF QA

The final build renders every DOCX-derived PDF page and the DOCX through the
bundled document renderer. `dist/visual-qa/final-ledger.json` records artifact
checksums, page or batch number, image dimensions, reviewer status, layout
findings, correction cycle, and final status.

Automated checks flag blank pages, dense pages, oversized images, table overflow,
font substitution, clipping candidates, missing headings, and broken links.
Every page receives visual inspection. High-risk pages also receive category
review for code, tables, diagrams, scorecards, runbooks, and templates.

DOCX checks include OOXML ZIP integrity, relationships, headings, repeated table
headers, links, alt text, metadata/privacy, and static TOC consistency.

PDF checks include `pdfinfo`, text extraction, page count, fonts, links, outlines,
and Poppler PNG rendering.

Tagged accessible PDF is outside the first-edition completion gate. The manual
must state that limitation. Accessible source structure, meaningful alt text,
heading hierarchy, link text, table headers, and DOCX accessibility remain in
scope.

## 11. Editorial and domain review gates

Each work unit produces a publication finding ledger using the handbook's own
finding schema. Required reviews:

- editorial: clarity, duplication, active language, product-agnostic framing,
  and consistency;
- domain: security, migrations, reliability, AI evaluation, release, or other
  relevant expertise;
- source: current and normative claims tied to the standards registry;
- executable: commands and code run, or explicitly labeled non-executable;
- Cutctx application note: linked repository evidence exists and remains
  clearly contextual.

Critical and Important findings block the work unit. Minor findings remain in
the deepwork ledger for final review.

## 12. Clean-checkout and branch safety

- Record starting commit and `git status --short --branch` for every work unit.
- Stop if pre-existing changes overlap the file allowlist.
- Stage only explicit paths and print staged paths before commits.
- Never use `git add .`.
- Keep runtime artifacts in ignored directories.
- Final verification uses a second clean worktree at the exact candidate commit.
- Compare filenames, checksums, catalog row counts, coverage, and page counts
  between integration and clean builds.
- Confirm the main checkout's pre-existing status remains untouched.

## Revised execution gate

Task 1 may begin after this addendum is committed. Task 2 publication spike must
pass before chapter authoring begins. No further oracle review is required
unless the canonical source format, source-only artifact policy, DOCX-authority
renderer, or 200–300 page criterion changes.
