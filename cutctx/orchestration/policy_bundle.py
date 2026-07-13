"""Versioned, signed policy bundles for the orchestration control plane."""

from __future__ import annotations

import base64
import hashlib
import json
import time
from typing import Any

from cryptography.hazmat.primitives.asymmetric import ed25519

from .models import OrchestrationConfig, to_dict


def compile_policy_bundle(config: OrchestrationConfig) -> dict[str, Any]:
    """Compile only enforcement-relevant data into a prompt-free bundle."""
    settings = to_dict(config.settings)
    payload = {
        "bundle_version": 1,
        "policy_version": config.settings.policy_version,
        "issued_at": int(time.time()),
        "settings": settings,
        "providers": [
            {
                "id": account.id,
                "provider": account.provider,
                "enabled": account.enabled,
                "auth_method": account.auth_method,
            }
            for account in config.providers
        ],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return {**payload, "bundle_hash": hashlib.sha256(canonical).hexdigest()}


def sign_policy_bundle(bundle: dict[str, Any], *, kid: str, private_key_hex: str) -> str:
    """Sign a canonical bundle with Ed25519; private keys stay outside config."""
    try:
        private_key = ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_key_hex))
    except ValueError as exc:
        raise ValueError("Invalid Ed25519 private key") from exc
    body = json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode()
    signature = private_key.sign(kid.encode() + b"." + body)
    encoded = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()
    return f"hro1.{kid}.{encoded}"


def verify_policy_bundle(
    bundle: dict[str, Any], *, token: str, public_keys: dict[str, str]
) -> bool:
    """Verify a bundle token against a configured public-key allow-list."""
    try:
        prefix, kid, encoded = token.split(".", 2)
        if prefix != "hro1" or kid not in public_keys:
            return False
        padding = "=" * (-len(encoded) % 4)
        signature = base64.urlsafe_b64decode(encoded + padding)
        public_key = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_keys[kid]))
        body = json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode()
        public_key.verify(signature, kid.encode() + b"." + body)
        return True
    except (ValueError, TypeError):
        return False
    except Exception:  # InvalidSignature must not leak signing details.
        return False


__all__ = ["compile_policy_bundle", "sign_policy_bundle", "verify_policy_bundle"]
