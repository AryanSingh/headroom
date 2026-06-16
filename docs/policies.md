# Policy Engine

The Headroom Policy Engine allows you to enforce centralized controls on AI usage across your entire infrastructure.

## Configuration
Policies are defined at the Organization level and can be overridden per-Workspace.
They support the following constraints:
- `require_compression`: Force context compression on all eligible requests.
- `budget_limit_usd` and `budget_period`: Cap monetary spend.
- `rpm_limit` / `tpm_limit`: Set request and token rate limits.
- `allowed_models`: Restrict the suite of models that can be used.

## Enforcement Mechanism
1. **Background Refresh**: The proxy asynchronously polls the policy service (using a stale-while-revalidate pattern) to fetch the latest signed policies.
2. **In-Path Evaluation**: As requests pass through, the Rust proxy evaluates them against the cached policies.
3. **Fail-Safe**: If the policy service is unreachable, the proxy relies on its local cache. If the cache expires, it defaults to a fail-open or last-known-good state depending on configuration.
