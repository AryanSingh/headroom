# CutCtx — Agent Implementation Task List

> All tasks below are fully implementable by an AI agent with file system and bash access.
> Each task includes exact file paths, commands, and acceptance criteria.
> Tasks marked **🔴 BLOCKING** must be done before a public release.
> Tasks marked **🟡 PRE-REVENUE** must be done before charging customers.
> Tasks marked **🟢 ENHANCEMENT** improve the product but are not blockers.

---

## TASK 1 — 🔴 BLOCKING: Fix release.yml and publish.yml for CutCtx package names

**Why:** CI/CD still references `headroom-ai` everywhere. Publishing will create the wrong packages.

**Files to edit:**
- `.github/workflows/release.yml`
- `.github/workflows/publish.yml`

**Exact changes in `release.yml`:**
```
Line ~8:  PYPI_PACKAGE: headroom-ai        → PYPI_PACKAGE: cutctx-ai
Line ~13: NPM_SDK_PACKAGE: headroom-ai     → NPM_SDK_PACKAGE: cutctx-ai
```
Also replace every occurrence of:
- `headroom_ai-*` wheel glob → `cutctx_ai-*`
- `headroom-ai-${{ ... }}.tgz` → `cutctx-ai-${{ ... }}.tgz`
- `@.../headroom-ai` scoped package → `@.../cutctx-ai`

**Command to verify after edit:**
```bash
grep -n "headroom-ai\|headroom_ai" .github/workflows/release.yml
# Should return 0 matches
grep -n "headroom-ai\|headroom_ai" .github/workflows/publish.yml
# Should return 0 matches
```

**Acceptance criteria:** No occurrences of `headroom-ai` or `headroom_ai` in either workflow file.

---

## TASK 2 — 🔴 BLOCKING: Update Dockerfile to use `cutctx` binary name

**Why:** Docker image entrypoint still calls `headroom proxy`, which won't exist once the package is published as `cutctx-ai`.

**File to edit:** `Dockerfile`

**Exact changes:**
```
Line 74: COPY --from=builder /usr/local/bin/headroom /usr/local/bin/headroom
       → COPY --from=builder /usr/local/bin/cutctx /usr/local/bin/cutctx

Line 80: mkdir -p /home/nonroot/.headroom
       → mkdir -p /home/nonroot/.cutctx

Line 83: mkdir -p /root/.headroom
       → mkdir -p /root/.cutctx

Line 98: ENTRYPOINT ["headroom", "proxy"]
       → ENTRYPOINT ["cutctx", "proxy"]

Line 121: ENTRYPOINT ["python3", "-m", "headroom.cli", "proxy"]
        → ENTRYPOINT ["python3", "-m", "headroom.cli", "proxy"]   # keep as-is (internal module)
```

Also update `docker-compose.yml` and `docker-bake.hcl`:
```bash
grep -n "headroom" docker-compose.yml docker-bake.hcl
# Fix any image names: headroom-proxy → cutctx-proxy
#                      headroom:latest → cutctx:latest
```

**Acceptance criteria:** `docker build .` succeeds; container runs `cutctx proxy` on start.

---

## TASK 3 — 🔴 BLOCKING: Update Kubernetes and Helm manifests

**Why:** K8s deployment.yaml and Helm chart still use `headroom-proxy` as app name and image.

**Files to edit:**
- `k8s/deployment.yaml`
- `k8s/configmap.yaml`
- `k8s/ingress.yaml`
- `k8s/hpa.yaml`
- All files under `helm/headroom/` — rename the directory to `helm/cutctx/` and update `Chart.yaml`

**Exact changes in `k8s/deployment.yaml`:**
```yaml
# Replace all occurrences:
app.kubernetes.io/name: headroom-proxy  →  app.kubernetes.io/name: cutctx-proxy
name: headroom-proxy                    →  name: cutctx-proxy
namespace: headroom                     →  namespace: cutctx
serviceAccountName: headroom-proxy      →  serviceAccountName: cutctx-proxy
image: headroom-proxy:latest            →  image: cutctx-proxy:latest
```

**Helm:**
```bash
# Rename directory
mv helm/headroom helm/cutctx

# In helm/cutctx/Chart.yaml:
name: headroom  →  name: cutctx
description: Headroom ...  →  description: CutCtx ...
```

**Command to scan remaining references:**
```bash
grep -rn "headroom" k8s/ helm/
```

**Acceptance criteria:** No `headroom` references in k8s/ or helm/ (except comments that explain the upstream origin).

---

## TASK 4 — 🔴 BLOCKING: Update project URLs in pyproject.toml

**Why:** Homepage and docs URLs still point to `headroom-docs.vercel.app`.

**File:** `pyproject.toml`

**Changes:**
```toml
[project.urls]
Homepage = "https://headroom-docs.vercel.app"         → "https://cutctx.dev"  (or chosen domain)
Documentation = "https://headroom-docs.vercel.app/docs" → "https://cutctx.dev/docs"
Repository = "https://github.com/chopratejas/headroom"  → "https://github.com/..."  (update to correct org/repo)
```

Also update `mkdocs.yml` site_url if present:
```bash
grep -n "site_url\|repo_url\|headroom-docs" mkdocs.yml
```

**Acceptance criteria:** All URLs in pyproject.toml point to cutctx domains.

---

## TASK 5 — 🟡 PRE-REVENUE: Align pricing between pitchtoship and CutCtx

**Why:** Pitchtoship has starter=$49/mo and studio=$149/mo, but the CutCtx pricing sheet has Team=$1,500/mo and Business=$3,500/mo. These need to be consistent before any customer pays.

**Decision to implement (confirm with user first):**
Option A: Use pitchtoship prices ($49/$149) — lower, faster to close deals
Option B: Use CutCtx standalone prices ($1,500/$3,500) — higher, update pitchtoship

**If Option A (update CutCtx to match pitchtoship):**

File: `artifacts/pricing-sheet.md`
```
Team: $1,500/mo  →  $49/mo
Business: $3,500/mo  →  $149/mo
```

File: `headroom/billing.py`
```python
# Update the docstring/comments to reflect $49/$149
```

File: `ENTERPRISE.md` — update pricing table

File: `COMMERCIALIZATION_PLAN.md` — update pricing references

**If Option B (update pitchtoship to match CutCtx):**

File: `/Users/aryansingh/Documents/Claude/Projects/pitchtoship/functions/_shared/pricing.js`
```javascript
// Update Starter: $49 → $1500 (or create new plan_id: 'headroom_team')
// Update Studio:  $149 → $3500 (or create new plan_id: 'headroom_business')
```

File: `/Users/aryansingh/Documents/Claude/Projects/pitchtoship/src/data/billing.ts`
```typescript
// Update plan prices to match CutCtx pricing sheet
```

**Acceptance criteria:** Price shown in the CutCtx license portal matches what Stripe charges. No mismatch between what a user sees and what they're billed.

---

## TASK 6 — 🟡 PRE-REVENUE: Add pitchtoship product entry for CutCtx

**Why:** Pitchtoship's product catalog lists "Headroom" as the product name. It needs to show "CutCtx".

**File:** `/Users/aryansingh/Documents/Claude/Projects/pitchtoship/src/data/products.ts`

**Steps:**
1. Read the file to see the current product entry for Headroom
2. Update: `name: "Headroom"` → `name: "CutCtx"`
3. Update description, logo path, and any links
4. Update status from whatever it is to "Live"

**File:** `/Users/aryansingh/Documents/Claude/Projects/pitchtoship/functions/_shared/pricing.js`
```javascript
// Update any reference to "Headroom" → "CutCtx" in plan descriptions
```

**Acceptance criteria:** pitchtoship's product page shows "CutCtx" not "Headroom".

---

## TASK 7 — 🟡 PRE-REVENUE: Add post-payment license key delivery webhook handler

**Why:** When a user pays on pitchtoship, they need to automatically receive a CutCtx license key. Currently there is no bridge between Stripe webhook → license key generation.

**How pitchtoship webhooks work:**
- `server/server.js` in pitchtoship handles `checkout.session.completed`
- It validates the Stripe webhook signature then fires a completion handler

**What to build:**

**File 1: `scripts/issue_license_from_webhook.py`** (in the headroom/CutCtx project)
```python
"""
Called by pitchtoship webhook when payment completes.
Input: JSON with {email, plan, billing, stripe_customer_id}
Output: Generates a license key and sends it to the customer email via resend/sendgrid
"""
```

Logic:
- Map `starter` plan → `team` tier, `studio` plan → `business` tier
- Call the license generator (`scripts/generate_license.py` logic) with a 1-year expiry
- Send the key via email (use `RESEND_API_KEY` or `SENDGRID_API_KEY` env var)
- Log to a local SQLite DB: `~/.cutctx/licenses_issued.db`

**File 2: Add to pitchtoship's `server/server.js`:**
```javascript
// In the checkout.session.completed handler, after validation:
// POST to CutCtx license service (or call a shared webhook endpoint)
// Or: write to a shared JSON file / database that CutCtx reads
```

**Acceptance criteria:**
- `python scripts/issue_license_from_webhook.py --dry-run --plan starter --email test@example.com` prints a valid team license key
- Key format matches `team-{base64_payload}.{hmac_hex}` from `scripts/generate_license.py`

---

## TASK 8 — 🟡 PRE-REVENUE: Write the MSA (Master Service Agreement) template

**Why:** Enterprise customers require a signed contract before payment. Without an MSA template, deals stall at legal review.

**File to create:** `docs/legal/MSA_TEMPLATE.md`

**Sections to include:**
1. Definitions (CutCtx, Customer, Authorized Users, Subscription Term)
2. Grant of License (tier-specific, non-transferable, non-sublicensable)
3. Restrictions (no reverse engineering, no competitive use)
4. Payment Terms (annual default, monthly at 20% premium, auto-renewal)
5. Data Processing (local-first, no prompt data leaves customer infra)
6. Confidentiality
7. Warranties and Disclaimers
8. Indemnification
9. Limitation of Liability (cap at 12 months of fees paid)
10. Term and Termination
11. Governing Law (specify jurisdiction)

Also create: `docs/legal/DPA_TEMPLATE.md` (Data Processing Addendum for GDPR/CCPA compliance)

**Acceptance criteria:** A lawyer can review and sign off on both documents. Placeholders like `[CUSTOMER_NAME]`, `[EFFECTIVE_DATE]`, `[JURISDICTION]` are clearly marked.

---

## TASK 9 — 🟡 PRE-REVENUE: Write design partner outreach email templates

**Why:** The GTM plan calls for 3–5 design partners. An agent can draft the outreach templates.

**File to create:** `docs/gtm/DESIGN_PARTNER_OUTREACH.md`

**Include:**
1. Cold outreach email (subject line + body, 150 words max) targeting engineering leads at AI-heavy startups
2. Follow-up email (day 7, if no response)
3. Calendly-style intro deck talking points (5 bullet points)
4. Design partner agreement terms (what they get: free Team tier + direct roadmap input; what we get: weekly 30-min feedback call, public case study rights)

**Target persona:** VP Engineering or Staff Engineer at a company with 5–50 engineers actively using Claude Code, Codex, or Cursor. Monthly LLM bill > $2,000.

---

## TASK 10 — 🟢 ENHANCEMENT: Add Go SDK scaffold

**Why:** Enterprise backend stacks often run Go. A Go SDK increases stickiness and reduces integration time.

**Directory to create:** `sdk/go/`

**Files:**
```
sdk/go/
├── go.mod              (module: github.com/cutctx/cutctx-go)
├── cutctx.go           (main client: Compress, Retrieve, Stats)
├── cutctx_test.go      (unit tests, no external deps)
├── options.go          (functional options pattern: WithModel, WithProxyURL, WithAPIKey)
└── README.md
```

**`cutctx.go` API surface (match the Python SDK):**
```go
type Client struct { ... }
func New(opts ...Option) *Client
func (c *Client) Compress(ctx context.Context, messages []Message) ([]Message, error)
func (c *Client) Retrieve(ctx context.Context, ref string) (string, error)
func (c *Client) Stats() Stats
```

The implementation should call the CutCtx proxy HTTP API (`http://localhost:8787`) — no native bindings needed.

**Acceptance criteria:** `go test ./sdk/go/...` passes; `go vet ./sdk/go/...` passes; README has a 5-line quickstart example.

---

## TASK 11 — 🟢 ENHANCEMENT: Add SOC 2 readiness checklist and security policy docs

**Why:** SOC 2 Type II takes 6–9 months. Starting the documentation now unblocks the audit. An agent can create the policy scaffolds that a human auditor will review.

**Files to create:**

`docs/security/SECURITY_POLICY.md` — covers:
- Data classification (none stored server-side; all local-first)
- Access control policy (license key management, admin CLI)
- Incident response procedure
- Vulnerability disclosure process (already have SECURITY.md — expand it)
- Encryption standards (Fernet for state, HMAC-SHA256 for licenses, TLS 1.2+ for proxy)

`docs/security/SOC2_CONTROLS.md` — maps CutCtx features to SOC 2 Trust Service Criteria:
- CC6 (Logical Access): RBAC, SSO, SCIM, audit logs → already implemented
- CC7 (System Operations): Helm/K8s health checks, observability → already implemented
- CC8 (Change Management): CI/CD pipeline, release.yml → already exists
- CC9 (Risk Mitigation): License encryption, no PII stored server-side → already implemented

`docs/security/VENDOR_SECURITY_QUESTIONNAIRE.md` — pre-filled answers to the 50 most common enterprise security questionnaire questions.

**Acceptance criteria:** A security officer can read all three docs in under 30 minutes and understand CutCtx's security posture.

---

## TASK 12 — 🟢 ENHANCEMENT: Update docs site config for CutCtx branding

**Why:** The mkdocs.yml and docs/content still reference headroom-docs.vercel.app and old branding.

**Files to edit:**
```bash
# Find all branding references in docs
grep -rn "headroom-docs.vercel.app\|Headroom\|headroom-ai" docs/ mkdocs.yml
```

**Key changes:**
- `mkdocs.yml`: `site_name`, `site_url`, `repo_url`, `repo_name`
- `docs/content/docs/meta.json`: Any title/description fields
- `docs/index.md` or equivalent homepage

**Do NOT change:**
- Python import paths (`from headroom import compress`) — these are code, not branding
- MCP tool names (`headroom_compress`, `headroom_retrieve`) — changing these breaks existing integrations

**Acceptance criteria:** `mkdocs build` succeeds with no broken internal links; rendered site shows "CutCtx" in nav and title.

---

## TASK 13 — 🟢 ENHANCEMENT: Add upgrade prompt to CLI when usage exceeds free tier

**Why:** Users on the free Builder tier who hit limits should be nudged to upgrade. This is the primary in-product growth loop.

**File to create/modify:** `headroom/cli/upgrade_prompt.py`

**Logic:**
```python
def maybe_show_upgrade_prompt(tokens_compressed: int, tier: str):
    """
    Show an upgrade prompt if:
    - tier == 'builder' AND tokens_compressed > 500_000 this month
    - OR if the compression fails due to entitlement check
    Print a one-line message:
      "💡 You've compressed 500K+ tokens this month.
       Upgrade to CutCtx Team for unlimited compression + analytics.
       → cutctx billing checkout --tier team"
    """
```

Hook into: `headroom/compress.py` at the end of `compress()` — check `TrialManager` usage and call `maybe_show_upgrade_prompt`.

**Acceptance criteria:** Running `cutctx wrap claude` for a session that hits 500K tokens prints the upgrade prompt exactly once (not on every call — use a daily flag in `~/.cutctx/prompted_today`).

---

## TASK 14 — 🟢 ENHANCEMENT: Write integration test for billing → license flow

**Why:** The billing→license bridge (Task 7) needs an end-to-end test before it can be trusted in production.

**File to create:** `headroom/tests/test_billing_integration.py`

**Tests:**
```python
def test_tier_mapping_starter_to_team()
def test_tier_mapping_studio_to_business()
def test_tier_mapping_portfolio_to_enterprise()
def test_get_checkout_url_returns_fallback_on_timeout()
def test_get_portal_url_returns_fallback_on_timeout()
def test_license_key_issued_for_starter_plan()
def test_license_key_issued_for_studio_plan()
def test_issued_key_validates_against_rust_format()
```

All tests should mock the pitchtoship HTTP API (no live calls). Use `pytest` and `unittest.mock`.

**Acceptance criteria:** `pytest headroom/tests/test_billing_integration.py` passes with 100% of tests green.

---

## TASK 15 — ✅ DONE: `cutctx savings` dashboard command

**Status:** Implemented — `headroom/cli/savings.py` (595 lines), registered in `main.py`.

**What was built:**
- `cutctx savings` — reads local SQLite/JSONL session DB, prints terminal summary, generates self-contained HTML report, opens in browser
- `cutctx savings --stats-only` — terminal only, no HTML
- `cutctx savings --days 7 --no-browser --output /tmp/report.html` — all flags supported
- HTML report: 4 stat cards (tokens saved, cost saved, sessions, ROI), daily bar chart (14 days, pure canvas), recent sessions table, break-even analysis
- Storage: tries `~/.headroom/headroom.db` (SQLite), falls back to `~/.headroom/sessions/` (JSONL), then `~/.cutctx/`
- Pricing: uses `MODEL_PRICING` from `cost_forecast.py` (claude-sonnet-4-5 = $3/M input tokens)

**No further work needed.**

---

## Summary Table

| # | Task | Priority | Estimated effort |
|---|------|----------|------------------|
| 1 | Fix release.yml/publish.yml package names | 🔴 BLOCKING | 15 min |
| 2 | Update Dockerfile binary name | 🔴 BLOCKING | 10 min |
| 3 | Update K8s and Helm manifests | 🔴 BLOCKING | 20 min |
| 4 | Update pyproject.toml URLs | 🔴 BLOCKING | 5 min |
| 5 | Align pricing pitchtoship ↔ CutCtx | 🟡 PRE-REVENUE | 20 min (needs decision) |
| 6 | Update pitchtoship product name → CutCtx | 🟡 PRE-REVENUE | 10 min |
| 7 | Post-payment license key delivery webhook | 🟡 PRE-REVENUE | 60 min |
| 8 | MSA + DPA legal template | 🟡 PRE-REVENUE | 45 min |
| 9 | Design partner outreach email templates | 🟡 PRE-REVENUE | 30 min |
| 10 | Go SDK scaffold | 🟢 ENHANCEMENT | 90 min |
| 11 | SOC 2 readiness docs | 🟢 ENHANCEMENT | 60 min |
| 12 | Docs site branding update | 🟢 ENHANCEMENT | 20 min |
| 13 | In-CLI upgrade prompt | 🟢 ENHANCEMENT | 30 min |
| 14 | Billing integration tests | 🟢 ENHANCEMENT | 45 min |
| 15 | `cutctx savings` dashboard command | ✅ DONE | — |

---

## How to run all blocking tasks

```bash
# Clone and run an agent session pointing at this file:
# "Read AGENT_TASKS.md and implement all tasks marked 🔴 BLOCKING"
# Then a second pass:
# "Implement all tasks marked 🟡 PRE-REVENUE — ask me about pricing alignment first (Task 5)"
```

## What an agent CANNOT do (requires human)

- Actually publish to PyPI / npm (needs `PYPI_API_TOKEN`, `NPM_TOKEN` secrets)
- Start the SOC 2 audit (requires hiring an auditor: Vanta, Drata, or Secureframe)
- Recruit design partners (requires human outreach)
- Sign an MSA (requires legal review and authorized signatory)
- Rename the GitHub repository (requires GitHub org admin access)
- Set `STRIPE_PRICE_*` environment variables in Cloudflare/Render (requires dashboard access)
