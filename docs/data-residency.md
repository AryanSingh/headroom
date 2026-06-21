# Data Residency & No-Egress Attestation

CutCtx can produce a **cryptographically verifiable snapshot** that proves
what data regions are configured, which egress domains the firewall is
blocking, and what the current tail hash of the tamper-evident audit chain is.

This document explains the attestation format, how to verify it offline, and
what every field means.

---

## Quick start

```bash
# Unsigned (informational)
curl http://localhost:4000/v1/residency/proof?tenant_id=acme-corp

# Signed (requires cutctx_ee + CUTCTX_LICENSE_* env vars)
curl "http://localhost:4000/v1/residency/proof?tenant_id=acme-corp&sign=true"
```

---

## Attestation JSON format

```jsonc
{
  "tenant_id": "acme-corp",               // tenant this attestation is for
  "proxy_version": "0.25.0",             // running proxy semver
  "timestamp_iso": "2026-06-16T11:00:00.000000+00:00",  // UTC ISO-8601
  "attested_at_ts": 1750071600.0,        // same instant as Unix epoch (float)
  "audit_chain_tail_hash": "a3f9…",      // SHA-256 tail of the audit chain, or null
  "data_regions": ["eu-west-1"],         // operator-declared residency regions
  "egress_domains_blocked": [            // domains tracked by the firewall
    "*.unknown-external (url-with-secrets pattern)",
    "sensitive-file-paths (/etc/passwd, ~/.ssh/*)"
  ],
  "signature_hex": "4a7b…",             // Ed25519 signature, or null if unsigned
  "signer_kid": "cutctx-prod-2026"    // key ID used for signing, or null
}
```

### Field reference

| Field | Type | Description |
|---|---|---|
| `tenant_id` | `string` | Tenant identifier. |
| `proxy_version` | `string` | Semver of the running CutCtx proxy. |
| `timestamp_iso` | `string` | ISO-8601 UTC timestamp when the attestation was generated. |
| `attested_at_ts` | `float` | Same instant as `timestamp_iso`, in Unix epoch seconds. |
| `audit_chain_tail_hash` | `string \| null` | SHA-256 (hex) of the most-recent audit event for this tenant. `null` when the EE audit store is not installed or has no events yet. |
| `data_regions` | `string[]` | Cloud/geo region labels declared by the operator in the API call. |
| `egress_domains_blocked` | `string[]` | Egress domains or patterns actively tracked by the firewall scanner. |
| `signature_hex` | `string \| null` | Hex-encoded Ed25519 signature over the canonical JSON payload, or `null`. |
| `signer_kid` | `string \| null` | Key ID (`kid`) of the signing key, or `null`. |

---

## What is the audit chain tail hash?

The **audit chain** is a tamper-evident append-only log stored in the
`cutctx_ee` audit database.  Every event row contains an `event_hash`
computed as:

```
SHA-256(secret_key || previous_hash || tenant_id || actor || action || payload_json || timestamp_iso)
```

The **tail hash** is simply the `event_hash` of the chronologically most-recent
event for the tenant.  By recording it in the attestation you can prove that
the audit log has not been rolled back or truncated since the attestation was
created: any auditor with access to the database can verify that a row with
that exact hash exists.

### Verifying the tail hash manually

```python
import hashlib, json

def verify_tail(secret_key: str, events: list[dict]) -> bool:
    """Re-compute and verify the full chain for a tenant."""
    expected_prev = None
    for e in sorted(events, key=lambda x: x["id"]):
        h = hashlib.sha256()
        h.update(secret_key.encode())
        if expected_prev:
            h.update(expected_prev.encode())
        h.update(e["tenant_id"].encode())
        h.update(e["actor"].encode())
        h.update(e["action"].encode())
        h.update(json.dumps(e["payload"], sort_keys=True).encode())
        h.update(e["timestamp"].encode())
        computed = h.hexdigest()
        if computed != e["event_hash"]:
            return False
        expected_prev = computed
    return True
```

---

## Verifying the Ed25519 signature offline

The signature covers a SHA-256 digest of the **canonical payload**.  The
canonical payload is the attestation JSON serialised with `sort_keys=True`,
with `signature_hex` and `signer_kid` omitted.

### Python example

```python
import hashlib, json
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

# Load the public key (hex-encoded 32 bytes)
pub_hex = "YOUR_PUBLIC_KEY_HEX"
public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(pub_hex))

# Reconstruct the canonical payload
attest = json.loads(open("attestation.json").read())
canonical = {k: v for k, v in attest.items()
             if k not in ("signature_hex", "signer_kid")}
payload_bytes = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
digest = hashlib.sha256(payload_bytes).digest()

# Verify
sig_bytes = bytes.fromhex(attest["signature_hex"])
public_key.verify(sig_bytes, digest)   # raises InvalidSignature on failure
print("✅ Attestation signature is valid")
```

### Shell example (using openssl)

```bash
# Extract canonical JSON (exclude signature fields), hash it
python3 - <<'EOF'
import hashlib, json, sys
a = json.load(sys.stdin)
c = {k: v for k, v in a.items() if k not in ("signature_hex", "signer_kid")}
print(json.dumps(c, sort_keys=True, separators=(",", ":")))
EOF < attestation.json | openssl dgst -sha256 -binary > payload.sha256

# Convert hex sig to binary
python3 -c "import sys; sys.stdout.buffer.write(bytes.fromhex(open('sig.hex').read().strip()))" > sig.bin

# Verify with Ed25519 public key (DER format)
openssl pkeyutl -verify -pubin -inkey pubkey.der \
  -sigfile sig.bin -in payload.sha256 -pkeyopt digest:sha256
```

---

## Generating a key pair (development)

> [!CAUTION]
> Never commit private key material to version control.

```python
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

priv = Ed25519PrivateKey.generate()
pub  = priv.public_key()

priv_hex = priv.private_bytes_raw().hex()
pub_hex  = pub.public_bytes_raw().hex()

print("CUTCTX_LICENSE_KID=my-key-id")
print(f"CUTCTX_LICENSE_PRIVATE_KEY={priv_hex}")
print(f"CUTCTX_LICENSE_PUBLIC_KEY={pub_hex}")
```

Set these three variables in your environment / secret manager before starting
the proxy with `sign=true` attestation support.

---

## Compliance notes

- **No raw content is ever stored** in an attestation — only hashes, region
  labels, domain patterns, and cryptographic signatures.
- The `cutctx/security/` module is **Apache-2.0** open-source.  The signing
  and audit-chain integration lives in `cutctx_ee` (commercial) and is only
  invoked lazily when installed.
- Attestations can be generated without `cutctx_ee`; they will be unsigned
  and the `audit_chain_tail_hash` will be `null`.
