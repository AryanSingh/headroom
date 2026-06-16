# SP-8: DMCA Takedown Notice Template

**Use this template as a starting point. Have your attorney review and finalize before use.**

---

## DMCA Takedown Notice — §512(c)(3) Notification

**Date:** [DATE]

**To:** [HOSTING PROVIDER / PLATFORM NAME]
[PLATFORM ADDRESS]
Attn: DMCA Agent / Copyright Agent

**Re:** DMCA Takedown Request — Unauthorized Distribution of Proprietary Software

### 1. Complainant Information

**Name:** [YOUR FULL LEGAL NAME / COMPANY NAME]
**Address:** [YOUR ADDRESS]
**Email:** [YOUR EMAIL]
**Phone:** [YOUR PHONE]

### 2. Identification of Copyrighted Work

The copyrighted work being infringed is the **CutCtx Enterprise Edition** software (formerly "Headroom Enterprise Edition"), including but not limited to:

- The `headroom_ee` Python package and all compiled derivatives (.so, .pyd, .egg)
- Enterprise-only modules: audit, billing, entitlements, organization management, RBAC, retention, SCIM, SSO, trial management, seats, watermark, and abuse detection
- Associated documentation, configuration, and API specifications

This software is protected by copyright under the laws of the United States and international treaties. The copyright owner is **[YOUR COMPANY NAME]**, and the software is distributed under a commercial license (LicenseRef-Headroom-Commercial). It is **not** open-source software.

**Registered copyright (if applicable):** [REGISTRATION NUMBER]

### 3. Identification of Infringing Material

The infringing material is located at the following URL(s):

1. [URL 1]
2. [URL 2]
3. [ADDITIONAL URLs]

**Description of infringing material:** The material consists of unauthorized copies of the CutCtx Enterprise Edition software, including source code, compiled binaries, and/or distribution packages. These copies are being distributed without authorization from the copyright owner and in violation of the commercial license agreement.

**Nature of infringement:** Unauthorized reproduction, distribution, and/or public display of copyrighted proprietary software.

### 4. Statement of Good Faith

I have a good faith belief that the use of the copyrighted materials described above is **not authorized** by the copyright owner, its agent, or the law.

### 5. Statement of Accuracy

I declare, under penalty of perjury, that the information in this notification is accurate and that I am the copyright owner or am authorized to act on behalf of the owner of an exclusive right that is allegedly infringed.

### 6. Signature

**Signature:** ________________________

**Printed Name:** [YOUR NAME / AUTHORIZED REPRESENTATIVE]

**Title:** [YOUR TITLE]

**Date:** [DATE]

---

**Note:** This notice is submitted in accordance with the Digital Millennium Copyright Act, 17 U.S.C. §512(c)(3).

---

## Leak Response Workflow (Internal)

### Step 1: Detection
- Canary token triggered OR
- Customer reports seeing EE code in public OR
- Security researcher reports leak OR
- Automated scan finds EE artifacts on paste sites

### Step 2: Triage (within 4 hours)
- [ ] Identify the leaked artifact type (source, binary, configuration)
- [ ] Extract watermark / canary token to identify the source license
- [ ] Check license database for the identified lic_id
- [ ] Document: screenshot, URL, timestamp, artifact hash

### Step 3: Attribution
- [ ] Look up the license holder associated with the watermark
- [ ] Check activation records: IP addresses, fingerprints, recent activity
- [ ] Determine if this is an authorized leak (e.g., employee) or customer sharing

### Step 4: Customer Notification (within 24 hours)
- [ ] Send formal notification to the license holder
- [ ] Include evidence of the leak (URL, screenshots)
- [ ] Request explanation within 5 business days
- [ ] Remind of contractual obligations (NDA, no redistribution)

### Step 5: Platform Takedown
- [ ] File DMCA takedown with hosting provider (use template above)
- [ ] File takedown with package registries if applicable
- [ ] Submit to Google for de-indexing if necessary

### Step 6: License Action
- [ ] If no satisfactory explanation within 5 business days:
  - [ ] Revoke the license key (CRL update)
  - [ ] Disable all seat leases for the lic_id
  - [ ] Log the action in the audit trail
- [ ] If explanation is satisfactory:
  - [ ] Document the resolution
  - [ ] Consider requiring additional security measures

### Step 7: Post-Incident
- [ ] Update the leak-response log
- [ ] Review and improve watermarking/etection if needed
- [ ] Notify legal counsel if DMCA litigation is contemplated
- [ ] File incident report

---

## Incident Log Template

| Field | Value |
|-------|-------|
| Incident ID | LEAK-YYYY-NNN |
| Date Detected | |
| Detected By | (canary / manual / automated scan) |
| Artifact Type | (source / binary / config) |
| Watermark lic_id | |
| License Holder | |
| Platform/URL | |
| Takedown Filed | (date) |
| Resolution | (recovered / revoked / legal / closed) |
| Resolved Date | |
| Notes | |
