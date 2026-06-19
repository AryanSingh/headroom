# SP-8: Leak Response Runbook

**Purpose:** Step-by-step procedure for responding to unauthorized distribution of CutCtx Enterprise Edition software.

**Audience:** Engineering leads, security team, legal counsel

**SLA:** Initial triage within 4 hours of detection. Takedown within 24 hours.

---

## Detection Sources

| Source | Signal | Response Time |
|--------|--------|---------------|
| Canary token callback | Automated alert with lic_id | Immediate |
| Customer/support report | "I saw EE code online" | 4 hours |
| Automated paste-site scan | Weekly scan results | 24 hours |
| Security researcher | Responsible disclosure | 4 hours |
| GitHub takedown request | Automated DMCA bot | 24 hours |

---

## Phase 1: Identification (0-4 hours)

### 1.1 Extract the Watermark

```bash
# From compiled binary
python -c "
from pathlib import Path
from headroom_ee.watermark import extract_watermark_from_binary
wms = extract_watermark_from_binary(Path('$BINARY_PATH'))
for wm in wms:
    print(f'lic_id={wm.lic_id} customer={wm.customer_id} canary={wm.canary_token}')
"

# From source (if available)
python -c "
from pathlib import Path
from headroom_ee.watermark import extract_watermark_from_source
wms = extract_watermark_from_source(Path('$SOURCE_DIR'))
for wm in wms:
    print(f'lic_id={wm.lic_id} customer={wm.customer_id} canary={wm.canary_token}')
"
```

### 1.2 Query License Database

```sql
SELECT lic_id, customer_name, customer_email, tier, status,
       activated_at, last_heartbeat
FROM licenses
WHERE lic_id = '$EXTRACTED_LIC_ID';
```

### 1.3 Document the Leak

- [ ] Screenshot the leak (include URL, timestamp, content)
- [ ] Record the artifact hash: `sha256sum $LEAKED_FILE`
- [ ] Save the full URL(s) and platform name
- [ ] Check if the leak is a complete copy or partial

---

## Phase 2: Attribution (4-24 hours)

### 2.1 Correlate with Activation Records

```sql
SELECT fingerprint, ip_address, geo, event_type, timestamp
FROM activations
WHERE lic_id = '$EXTRACTED_LIC_ID'
ORDER BY timestamp DESC
LIMIT 50;
```

### 2.2 Check for Shared Key Indicators

- Multiple distinct fingerprints (>5) → shared key
- Impossible travel (distant geos within minutes) → shared key
- IPs from cloud providers (AWS, GCP, Azure) → automated sharing

### 2.3 Determine Leak Type

| Type | Indicator | Severity |
|------|-----------|----------|
| Full source leak | Complete .py files or .so with source | CRITICAL |
| Partial leak | Single module or config | HIGH |
| Binary-only | Compiled .so without source | MEDIUM |
| Canary trigger | Canary string found publicly | MEDIUM |

---

## Phase 3: Customer Notification (24-48 hours)

### 3.1 Send Formal Notification

```
Subject: Urgent — Unauthorized Distribution of CutCtx Enterprise Edition

Dear [CUSTOMER NAME],

We have identified unauthorized distribution of CutCtx Enterprise Edition
software associated with your license (lic_id: [LIC_ID]).

[Describe what was found and where]

Per your Enterprise License Agreement (Section 4), unauthorized redistribution
results in immediate license termination. We require your written explanation
within 5 business days.

Please confirm:
1. Who had access to this copy of the software
2. How it was distributed without authorization
3. What steps you will take to recover the unauthorized copies

Failure to respond will result in license revocation and seat deactivation.

Regards,
CutCtx Security Team
```

### 3.2 Escalation Path

- **No response in 5 days** → Revoke license + notify legal
- **Denial** → Escalate to legal counsel
- **Acknowledgment + remediation** → Accept remediation plan, monitor

---

## Phase 4: Technical Response

### 4.1 Revoke the License

```bash
# Via admin API
curl -X POST https://pitchtoship.com/v1/admin/revoke \
  -H "Authorization: Bearer $ADMIN_KEY" \
  -d '{"lic_id": "$LIC_ID", "reason": "unauthorized_distribution"}'
```

### 4.2 Update CRL

The CRL (Certificate Revocation List) is pushed to all active proxies on
next heartbeat. Revoked licenses will be downgraded to OpenSource within
the CRL refresh interval (default: 1 hour).

### 4.3 Platform Takedown

1. File DMCA takedown with the hosting provider (use template: `docs/legal/DMCA_TAKEDOWN_TEMPLATE.md`)
2. File with GitHub if applicable (https://github.com/contact/dmca)
3. Submit to Google for de-indexing (https://support.google.com/legal/troubleshooter/1114905)

### 4.4 Canary Monitoring

Check if any additional canary tokens from the same lic_id have been
triggered. This indicates the scope of the leak.

---

## Phase 5: Post-Incident

### 5.1 Incident Report

```markdown
## Incident Report: LEAK-YYYY-NNN

**Date:** [DATE]
**Severity:** [CRITICAL/HIGH/MEDIUM]
**lic_id:** [LICENSE ID]
**Customer:** [CUSTOMER NAME]

### Summary
[1-2 sentence summary]

### Timeline
- [TIME] Leak detected by [SOURCE]
- [TIME] Watermark extracted, lic_id identified
- [TIME] Customer notified
- [TIME] License revoked
- [TIME] Takedown filed with [PLATFORM]
- [TIME] Resolution

### Root Cause
[Why did this happen?]

### Impact
[What was exposed?]

### Remediation
[What was done?]

### Follow-up Actions
- [ ] Review access controls for this customer
- [ ] Update monitoring if needed
- [ ] Consider legal action
```

### 5.2 Metrics to Track

| Metric | Target |
|--------|--------|
| Time to detect | < 24 hours |
| Time to triage | < 4 hours |
| Time to takedown | < 24 hours |
| Time to license action | < 48 hours |
| Total incidents per quarter | < 5 |

---

## Emergency Contacts

| Role | Name | Contact |
|------|------|---------|
| Security Lead | [NAME] | [EMAIL/PHONE] |
| Legal Counsel | [NAME] | [EMAIL/PHONE] |
| Engineering Lead | [NAME] | [EMAIL/PHONE] |
| CEO/CTO | [NAME] | [EMAIL/PHONE] |

---

## Escalation Matrix

| Severity | Who | Timeline |
|----------|-----|----------|
| CRITICAL (full source leak) | Security + Legal + CEO | Immediate |
| HIGH (partial leak) | Security + Legal | 4 hours |
| MEDIUM (binary-only) | Security | 24 hours |
| LOW (canary only) | Security | 48 hours |
