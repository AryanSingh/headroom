# Audit Compliance

The Cutctx proxy includes a tamper-evident audit log to ensure the integrity of all administrative and system actions.

## Cryptographic Hash Chain
Every audit event is cryptographically linked to the previous event using a
secret-keyed SHA-256 chain value.
The formula for the chain is:
`hash = SHA256(secret || prev_hash || payload)`

This makes it computationally infeasible for a malicious actor to alter, reorder, or delete historical events without invalidating the chain.

## Monitored Actions
The following actions emit audit events:
- License creation, activation, and revocation
- Trial initiation
- Policy creation and updates
- System startup and config reloading

## Verification
You can programmatically verify the integrity of the audit chain using the `/v1/audit/verify/{tenant_id}` endpoint. In the event of a validation failure, the system will alert administrators to potential tampering.
