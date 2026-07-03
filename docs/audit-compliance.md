# Audit Compliance

The Cutctx proxy includes a tamper-evident audit log to ensure the integrity of all administrative and system actions.

## Cryptographic Hash Chain
Every audit event is cryptographically linked to the previous event using an
HMAC-SHA256 chain value over a canonical length-prefixed message.
The formula for the chain is:
`hash = HMAC-SHA256(secret, prev_hash || len(tenant) || tenant || len(actor) || actor || len(action) || action || len(payload) || payload || len(timestamp) || timestamp)`

Genesis events use `32` zero bytes in place of `prev_hash`.

This makes it computationally infeasible for a malicious actor to alter, reorder, or delete historical events without invalidating the chain or relying on ambiguous field boundaries.

## Monitored Actions
The following actions emit audit events:
- License creation, activation, and revocation
- Trial initiation
- Policy creation and updates
- System startup and config reloading

## Verification
You can programmatically verify the integrity of the audit chain using the `/v1/audit/verify/{tenant_id}` endpoint. In the event of a validation failure, the system will alert administrators to potential tampering.
