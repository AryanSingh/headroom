# Bug Report — Dashboard "Money Saved" Shows $0 for Current Session

**Date:** 2026-07-06
**Reported by:** QA Engineer
**Version:** cutctx v0.31.0 (bugfix/audit-issues)
**Severity:** High

---

## Bug 1: Dashboard Session Savings Always $0

### Severity
**High** — The primary "Money saved" metric on the dashboard is always $0 for the current session, making the dashboard's core value proposition invisible to users.

### Reproduction Steps

1. Start the proxy: `cutctx proxy`
2. Send a few requests through the proxy (e.g., via any AI agent)
3. Open the dashboard at `http://localhost:8787/dashboard`
4. Observe the "Money saved" figure in the session/current period view

### Expected vs Actual Behavior

| | Expected | Actual |
|---|---|---|
| Session "Money saved" | Shows real compression savings (e.g., $1.39) | Shows $0.00 |
| Session per-source USD | Shows breakdown across all 11 sources | All sources show $0.00 |

### Root Cause

The dashboard reads session savings from `stats.cost.compression_savings_usd`, which is populated by `merge_cost_stats()` (`cutctx/proxy/cost.py:520`):

```python
compression_savings = cost_stats.get("savings_usd", 0.0)
```

This reads from `CostTracker.stats()` which **always returns $0** — it only computes non-zero values when there are cache-read tokens with provider discounts (`cost.py:1012-1015`). The CostTracker does NOT track compression savings.

The actual session savings are computed by the **SavingsTracker** and available at `stats.display_session.compression_savings_usd`, but this data was never passed to `merge_cost_stats()`.

### Evidence

Before the fix:
```
cost.compression_savings_usd: 0.0       ← shown on dashboard
cost.savings_usd: 0.0                    ← shown on dashboard
display_session.compression_savings_usd: 1.12  ← real data, not used
```

After the fix:
```
cost.compression_savings_usd: 1.3915    ← correct!
cost.savings_usd: 1.3915                 ← correct!
display_session.compression_savings_usd: 1.39  ← matches
```

### Fix Applied

**Files changed:**
1. `cutctx/proxy/cost.py:490` — `merge_cost_stats()` now accepts optional `display_session` parameter; prefers `display_session.compression_savings_usd` over `cost_stats.savings_usd`
2. `cutctx/proxy/server.py:4375` — passes `display_session` to first call site
3. `cutctx/proxy/server.py:5421` — passes `display_session` to second call site

**Diff:**
```python
# Before
compression_savings = cost_stats.get("savings_usd", 0.0)

# After
compression_savings = (
    float(display_session.get("compression_savings_usd", 0.0) or 0.0)
    if display_session
    else cost_stats.get("savings_usd", 0.0)
)
```

### Verification
- `cost.compression_savings_usd` now correctly shows $1.39 after recording a request
- All savings tests pass (37/38, 1 pre-existing unrelated failure)

---

## Bug 2: Dashboard Uses Wrong Data Source for Session Savings

### Severity
**Medium** — Architectural coupling between CostTracker and dashboard display.

### Root Cause
The dashboard (`Overview.jsx`) reads the "current session" savings from `stats.cost.*`, a namespace designed for CostTracker data (provider-pricing perspective with cache discounts). The real session savings live in `stats.display_session.*` (SavingsTracker data with 11-source attribution).

This architectural mismatch means any dashboard view that reads from `cost` will show $0 unless cache-read discounts exist.

### Recommended Follow-up
The dashboard should be updated to read from `display_session` directly for the session savings view, rather than relying on the backend to duplicate data into `cost`. This is a frontend-only change that requires rebuilding the dashboard bundle.

---

## Verification Checklist

- [x] Bug 1 root cause identified and fixed
- [x] Fix verified with real request data (savings now shows $1.39)
- [x] All related tests pass (37/38, 1 pre-existing unrelated failure)
- [x] No regressions in auth, savings history, or dashboard API endpoints
