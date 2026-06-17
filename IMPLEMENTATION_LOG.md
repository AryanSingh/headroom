# Headroom — Implementation Log

> **Date:** 2026-06-17
> **Scope:** PitchToShip integration client, Go SDK, ROI Calculator

---

## What Was Built

Headroom's commercialization integration with PitchToShip for centralized license validation, a Go SDK for the Headroom proxy, and a standalone ROI calculator marketing page.

---

## Files Created

| File | Lines | Purpose |
|------|-------|---------|
| `headroom_ee/billing/pitchtoship_client.py` | 72 | PitchToShip integration client (license verify, trial, seat heartbeat) |
| `marketing/roi-calculator/index.html` | 203 | Standalone ROI calculator (HTML/JS/CSS) |
| `sdks/go-headroom/client.go` | 68 | Go client for Headroom proxy |
| `sdks/go-headroom/go.mod` | 3 | Go module definition |
| `sdks/go-headroom/README.md` | ~80 | SDK documentation with examples |

## Files Modified

| File | Changes |
|------|---------|
| `proxy/routes/license_validation.py` | Added PitchToShip-first validation with local fallback |
| `headroom_ee/trial.py` | Added PitchToShip JWT verification as primary path |
| `headroom_ee/seats.py` | Added heartbeat to PitchToShip seat tracking |

---

## PitchToShip Client (`pitchtoship_client.py`)

### Architecture
- **Optional integration** — Headroom works WITHOUT PitchToShip
- Activated by setting `PITCHTOSHIP_URL` env var
- Function-based API (not class-based): `is_configured()`, `_post()`, `verify_license()`, `issue_trial()`, `heartbeat_seat()`
- Graceful fallback: all functions return `None` on failure, callers check and fall back to local logic

### Functions
| Function | Endpoint | Description |
|----------|----------|-------------|
| `is_configured()` | — | Returns True if PITCHTOSHIP_URL is set |
| `verify_license(key, hwid)` | POST /api/licenses/verify | Verify license, returns dict or None |
| `issue_trial(hwid, product)` | POST /api/trials/issue | Issue trial token |
| `verify_trial_token(token)` | POST /api/trials/verify | Verify trial token |
| `heartbeat_seat(key, hwid)` | POST /api/seats/heartbeat | Send seat heartbeat |

### Integration Points
- `proxy/routes/license_validation.py`: Checks PitchToShip first, falls back to local license file
- `headroom_ee/trial.py`: Verifies trial via PitchToShip JWT, falls back to local Fernet-encrypted file
- `headroom_ee/seats.py`: Sends heartbeat to PitchToShip, syncs local seat state

---

## Go SDK (`sdks/go-headroom/`)

### Client API
```go
// Create client
client := headroom.NewClient("http://localhost:8080")

// Use as HTTP client wrapper
resp, err := client.Do(req)

// Use as http.RoundTripper
httpClient := &http.Client{Transport: client}
resp, err := httpClient.Get("https://api.anthropic.com/v1/messages")
```

### Architecture
- `Client` struct with `ProxyURL` and `HTTPClient` fields
- `Do()` method rewrites request URL to go through proxy with `_target` parameter
- `RoundTrip()` implements `http.RoundTripper` for seamless integration
- Module: `github.com/headroom-labs/go-headroom` (Go 1.21+)

---

## ROI Calculator (`marketing/roi-calculator/`)

### Features
- **Inputs:** Monthly prompt tokens, completion tokens, model selector, compression ratio slider (40-90%)
- **Models supported:** Claude 3.5 Sonnet, Claude 3 Opus, GPT-4o, GPT-4o-mini, Gemini 1.5 Pro
- **Outputs:** Cost without/with Headroom, monthly/annual savings, break-even vs Team plan
- **Pricing reference table** for all Headroom tiers
- **CTA** linking to headroom.sh

### Compression Logic
- Prompt compression: slider value (e.g., 65%)
- Completion compression: 30% of prompt ratio (e.g., 19.5%)
- Cost calculation: (tokens / 1M) × price per MTok

### Design
- Single-file HTML/JS/CSS (no dependencies)
- Responsive grid layout (works on mobile)
- Real-time calculation on input change
- Blue/white color scheme matching Headroom branding

---

## Existing Commercialization Assets

These were already present before this implementation:

| File | Purpose |
|------|---------|
| `COMMERCIALIZATION_PLAN.md` | Open-core model, pricing tiers, ICP, 6-month roadmap |
| `pricing-sheet.md` | Builder/Team/Business/Enterprise pricing + add-ons |
| `packaging-matrix.md` | 4-tier feature gating matrix |
| `COMPETITIVE_ANALYSIS.md` | vs LLMLingua-2, CacheBlend, Morph, lean-ctx, RTK |
| `ENTERPRISE.md` | Self-hosted, cross-provider, reversible compression |
| `SECURITY.md` | Vulnerability disclosure policy |
| `security-one-pager.md` | Local-first, SSO, RBAC, audit logging |

---

## License Validation Flow (with PitchToShip)

```
1. Headroom receives license_key + hwid
2. pitchtoship_client.verify_license(key, hwid)
   → POST http://pitchtoship:3001/api/licenses/verify
   → Returns {valid, tier, features, expires_at} or None
3. If PitchToShip unreachable → fallback to local license validation
4. If valid → check tier features against requested operation
5. If HWID mismatch → reject with hwid_mismatch error
6. If first use with HWID → PitchToShip binds HWID to license
```

---

## Testing

### PitchToShip Integration (6/6 pass)
Verified against live PitchToShip server:
- Public key endpoint returns ECDSA P-256 PEM
- Create + verify license (business tier): 13 features returned
- Trial issue: returns token + 14-day expiry
- Seat heartbeat: 3 devices tracked correctly
- HWID lock: binds on first use, rejects mismatch, allows original
- Revoke → verify: returns license_revoked

### Go SDK
- Compiles clean: `go build ./...`
- Module: `github.com/headroom-labs/go-headroom`

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `PITCHTOSHIP_URL` | No | PitchToShip server URL (enables centralized license management) |

When `PITCHTOSHIP_URL` is not set, Headroom operates fully standalone with local license validation.

---

## Known Limitations

1. **PitchToShip client is function-based** — not a class, differs from original PitchToShipClient design
2. **No automatic retry** — PitchToShip client uses simple timeout, no exponential backoff
3. **Go SDK is minimal** — only proxy routing, no compression controls or analytics
4. **ROI calculator is static** — no analytics/tracking for conversion measurement
