I have diagnosed and fixed the "Bad Request" issue in Codex.

### Root Cause
The root cause of the error was our `cutctx` proxy's handling of the `/v1/models` and `/backend-api/models` endpoint for Codex desktop/CLI clients. 

When Codex starts, it fetches the list of available models to populate its UI. Our proxy was capturing the upstream ChatGPT registry response but stripping out almost all fields to strictly match the standard OpenAI `{"id", "object", "created", "owned_by"}` schema.

However, the Codex application expects *undocumented* proprietary fields in the response objects, including:
- `slug`
- `display_name`
- `supported_reasoning_levels`
- `shell_type`

Because our proxy stripped these fields, Codex's internal Rust deserializer (`codex_models_manager`) was throwing strict schema validation errors, causing the model refresh to disconnect and resulting in a "Bad Request" / "Connection Closed" cascade in the application UI whenever it tried to initiate a chat.

### The Fix
I have modified `cutctx/providers/proxy_routes.py`. 
Instead of stripping fields and reconstructing a strict subset, the proxy now fetches the upstream model registry (`_fetch_chatgpt_codex_models_raw`) and passes through **all native fields** as-is. It still wraps them in the `data` and `models` lists so that both the OpenAI format and the proprietary Codex format are satisfied simultaneously.

I've tested this by executing `codex exec` through the proxy with the fix applied, and I can confirm that the parsing errors are completely eliminated and Codex successfully streams back a completion ("Hello."). 

### Verification
The dashboard is also fully up and running at `http://127.0.0.1:8787/dashboard`. Since we previously identified `ENOSPC` (No Space Left on Device) as the cause of proxy instability, ensuring logs are rotated is critical for long-term health. The local dev proxy is currently running and verified healthy!

---

## 2. Dashboard UI and Stat Fixes (July 5, 2026)

I addressed three distinct issues related to the dashboard's display and behavior.

### Issue 1: Dashboard UI filters looked like a gray blob
**Cause:** The CSS classes `.tab-group` and `.tab-button` were missing from the primary `index.css` stylesheet, leaving the React components without styling.
**Fix:** Appended the appropriate CSS to `dashboard/src/index.css`.
**Verification:** Added a regression test `test_dashboard_css_components_regression` in `tests/test_dashboard_regression.py` that verifies the classes remain in the stylesheet.

### Issue 2: Dashboard 404ed on refresh due to bad pathing
**Cause:** A bug in the `Makefile` command `build-dashboard` was incorrectly copying the React dist assets into a nested directory `cutctx/dashboard/assets/assets/`. While the initial load might hit the local index, hard refreshing caused the backend proxy to fail when searching for `cutctx/dashboard/assets/index*.js` (since they were nested).
**Fix:** Fixed the `Makefile` step to accurately copy assets into `cutctx/dashboard/assets/`. Removed the invalid nested directory.
**Verification:** Added regression test `test_dashboard_assets_path_regression` in `tests/test_dashboard_regression.py` that checks the correct placement of files post-build and asserts that the buggy nested path does not exist.

### Issue 3: "Active Compression" exceeded 100% (e.g. 292.8%)
**Cause:** When a request is completely served from the semantic cache, it saves both the input tokens sent to the provider *and* the output tokens the provider would have generated. The calculation mathematically evaluated: `Tokens Saved (Input+Output) / Total Input Tokens * 100`. Because output savings can easily dwarf input size, the percentage soared above 100%. 
**Fix:** Modified the percentage logic across both the Python backend (`savings_tracker.py` and `server.py`) and the React frontend (`Overview.jsx` and `Savings.jsx`). The formula now evaluates savings against the true maximum denominator: `max(Total Input Tokens, Tokens Saved)`, thereby accurately capping the metric at 100%.
**Verification:** Added regression test `test_savings_percent_capped_at_100_when_output_saved` inside `tests/test_savings_percent_cap.py` that mocks a request with 5,000 input tokens and 15,000 saved tokens. The test asserts that `savings_percent` exactly equals 100.0%.
