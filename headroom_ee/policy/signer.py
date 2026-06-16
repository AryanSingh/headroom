import base64
import json
import os
import time
from typing import Any

from cryptography.hazmat.primitives.asymmetric import ed25519


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def sign_policy(
    policy_payload: dict[str, Any],
    kid: str | None = None,
    private_key_hex: str | None = None,
) -> str:
    """
    Generate an hrp1 signed policy token using Ed25519.
    Format: hrp1.{kid}.{payload_b64url}.{sig_b64url}
    """
    kid = kid or os.environ.get("HEADROOM_POLICY_KID") or os.environ.get("HEADROOM_LICENSE_KID")
    private_key_hex = (
        private_key_hex
        or os.environ.get("HEADROOM_POLICY_PRIVATE_KEY")
        or os.environ.get("HEADROOM_LICENSE_PRIVATE_KEY")
    )

    if not kid or not private_key_hex:
        raise ValueError(
            "Policy signing keys not configured. Set HEADROOM_POLICY_PRIVATE_KEY and HEADROOM_POLICY_KID."
        )

    try:
        priv_bytes = bytes.fromhex(private_key_hex)
        private_key = ed25519.Ed25519PrivateKey.from_private_bytes(priv_bytes)
    except Exception as e:
        raise ValueError(f"Invalid private key hex: {e}") from e

    # Ensure timestamp
    if "ts" not in policy_payload:
        policy_payload["ts"] = int(time.time())

    payload_json = json.dumps(policy_payload, separators=(",", ":"))
    payload_b64 = b64url_encode(payload_json.encode("utf-8"))

    signed_message = f"hrp1.{kid}.{payload_b64}".encode()
    signature = private_key.sign(signed_message)
    sig_b64 = b64url_encode(signature)

    return f"{signed_message.decode('ascii')}.{sig_b64}"
