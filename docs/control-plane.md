# Hosted Control Plane

The Cutctx proxy includes a hosted control plane for managing Enterprise features such as spend tracking, policy enforcement, audit logs, and licenses.

## Endpoints

### License Management
- `POST /v1/license/activate`: Register proxy instance activations.
- `GET /v1/license/crl`: Retrieve revoked license keys.
- `POST /v1/license/checkout-seat`: Manage user seat leases.
- `POST /v1/license/start-trial`: Initiate a trial.
- `POST /v1/license/check-trial`: Check trial status.

### Spend Ledger
- `POST /v1/spend/events`: Asynchronous ingestion of spend events.
- `GET /v1/spend/query`: Query spend by tenant or date range.
- `GET /v1/spend/export/csv`: Export spend data to CSV.
- `GET /v1/spend/dashboard`: Access the spend monitoring dashboard.

### Policy Enforcement
- `POST /v1/policies`: Create or update tenant policies.
- `GET /v1/policies/{org_id}/signed`: Retrieve signed policies for local proxy cache.

### Tamper-Evident Audit Log
- `POST /v1/audit/events`: Append events to the cryptographic hash chain.
- `GET /v1/audit/events/{tenant_id}`: Retrieve audit logs.
- `GET /v1/audit/verify/{tenant_id}`: Verify the hash chain integrity.

## Architecture

1. **Rust Proxy**: High-performance reverse proxy that fetches cached policies and asynchronously emits spend events.
2. **Python Control Plane**: FastAPI service embedded in the `cutctx/proxy` that exposes management endpoints.
3. **Enterprise Extensions**: The `cutctx_ee` package contains proprietary logic for license, spend, policy, and audit storage and cryptography.

## Self-Hosting
To self-host the control plane, configure your load balancer to route `/v1/*` paths to a dedicated Cutctx proxy instance running with the `--management-only` flag (if available) or simply behind firewall rules restricting access to admin operators.
