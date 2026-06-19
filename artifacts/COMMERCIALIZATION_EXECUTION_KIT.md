# Headroom Commercialization Execution Kit

**Purpose:** Exact steps to complete the remaining commercialization work after the repo-side implementation is done.

## Current Position

What is done:
- Product packaging is defined in code
- Commercial feature gates are implemented
- Team, Business, and Enterprise admin capabilities exist
- Deployment paths exist for Docker, Kubernetes, Helm, and air-gap scenarios
- Billing and license validation are routed through PitchToShip

What remains:
- final commercial approval
- customer-facing packaging rollout
- legal and procurement readiness
- pilot execution
- support and onboarding operations

## Phase 1: Freeze Commercial Offer

### Step 1
- Approve one pricing table from [artifacts/pricing-sheet.md](/Users/aryansingh/Documents/Claude/Projects/headroom/artifacts/pricing-sheet.md)
- Remove any conflicting numbers from website or deck materials
- Exit criterion: one price per tier

### Step 2
- Approve one packaging matrix from [artifacts/packaging-matrix.md](/Users/aryansingh/Documents/Claude/Projects/headroom/artifacts/packaging-matrix.md)
- Do not sell features that are not in that matrix
- Exit criterion: one source of truth for feature boundaries

### Step 3
- Update customer-facing pages to match the approved matrix
- Exit criterion: no stale "coming soon" claims for already shipped features

## Phase 2: Build Buyer Confidence

### Step 4
- Package the security packet using:
  - [SECURITY.md](/Users/aryansingh/Documents/Claude/Projects/headroom/SECURITY.md)
  - [docs/security-and-privacy.md](/Users/aryansingh/Documents/Claude/Projects/headroom/docs/security-and-privacy.md)
  - [artifacts/security-one-pager.md](/Users/aryansingh/Documents/Claude/Projects/headroom/artifacts/security-one-pager.md)
- Exit criterion: security reviewer can answer data flow, identity, audit, and retention questions

### Step 5
- Create one deployment packet for:
  - Docker
  - Kubernetes
  - Helm
  - air-gap
- Exit criterion: a solutions engineer can onboard a customer without improvising

## Phase 3: Procurement Readiness

### Step 6
- Open the legal workstream using [artifacts/LEGAL_AND_PROCUREMENT_CHECKLIST.md](/Users/aryansingh/Documents/Claude/Projects/headroom/artifacts/LEGAL_AND_PROCUREMENT_CHECKLIST.md)
- Exit criterion: MSA, DPA, privacy terms, and support policy all have owners

### Step 7
- Define support and escalation promises
- Exit criterion: response times are written down and match the tiering story

## Phase 4: Pilot Motion

### Step 8
- Build a 14-day pilot offer
- Start from [artifacts/PILOT_OFFER_TEMPLATE.md](/Users/aryansingh/Documents/Claude/Projects/headroom/artifacts/PILOT_OFFER_TEMPLATE.md)
- Require baseline metrics before pilot start
- Exit criterion: pilot starts with success criteria already defined

### Step 9
- Run onboarding from [artifacts/CUSTOMER_ONBOARDING_RUNBOOK.md](/Users/aryansingh/Documents/Claude/Projects/headroom/artifacts/CUSTOMER_ONBOARDING_RUNBOOK.md)
- Exit criterion: first request, first savings report, and first admin review all completed

### Step 10
- Run weekly pilot review
- Exit criterion: convert pilot to paid contract or close it with a written reason

## Phase 5: Repeatable GTM

### Step 11
- Use [artifacts/SALES_PLAYBOOK.md](/Users/aryansingh/Documents/Claude/Projects/headroom/artifacts/SALES_PLAYBOOK.md) to build pipeline
- Use [artifacts/PROCUREMENT_PACKET_INDEX.md](/Users/aryansingh/Documents/Claude/Projects/headroom/artifacts/PROCUREMENT_PACKET_INDEX.md) and [artifacts/SECURITY_QUESTIONNAIRE_WORKSHEET.md](/Users/aryansingh/Documents/Claude/Projects/headroom/artifacts/SECURITY_QUESTIONNAIRE_WORKSHEET.md) for reviewer workflows
- Exit criterion: target account list, outreach copy, and demo script are all ready

### Step 12
- Use [artifacts/LAUNCH_CHECKLIST.md](/Users/aryansingh/Documents/Claude/Projects/headroom/artifacts/LAUNCH_CHECKLIST.md) to publish the commercial launch
- Exit criterion: pricing, enterprise page, onboarding docs, and security packet are all live

## Highest Priority Order

1. Freeze pricing and packaging
2. Package security and deployment docs
3. Prepare legal and procurement workflow
4. Run 3 design-partner pilots
5. Turn one pilot into a case study
6. Standardize support and onboarding

## Definition Of Completion

Commercialization is complete enough to scale when:
- the product story matches the shipped product
- a buyer can pass a first security review
- a customer can be onboarded without founder-only heroics
- the sales team can quote the product without ambiguity
- procurement has a clear path
