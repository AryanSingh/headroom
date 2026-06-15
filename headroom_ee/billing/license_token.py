import base64
import json
import os
from typing import Dict, Any, Optional
from cryptography.hazmat.primitives.asymmetric import ed25519

def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

def sign_license(tier: str, kid: str, private_key_hex: str, extra_payload: Optional[Dict[str, Any]] = None) -> str:
    """
    Generate an hrk1 signed token using Ed25519.
    Format: hrk1.{kid}.{payload_b64url}.{sig_b64url}
    """
    try:
        priv_bytes = bytes.fromhex(private_key_hex)
        private_key = ed25519.Ed25519PrivateKey.from_private_bytes(priv_bytes)
    except Exception as e:
        raise ValueError(f"Invalid private key hex: {e}")

    payload = {"tier": tier}
    if extra_payload:
        payload.update(extra_payload)
        
    payload_json = json.dumps(payload, separators=(',', ':'))
    payload_b64 = b64url_encode(payload_json.encode('utf-8'))
    
    signed_message = f"hrk1.{kid}.{payload_b64}".encode('utf-8')
    signature = private_key.sign(signed_message)
    sig_b64 = b64url_encode(signature)
    
    return f"{signed_message.decode('ascii')}.{sig_b64}"

def get_default_issuer_config():
    """Retrieve the configured Ed25519 Key ID and Private Key (hex) from env."""
    kid = os.environ.get("HEADROOM_LICENSE_KID")
    priv_hex = os.environ.get("HEADROOM_LICENSE_PRIVATE_KEY")
    return kid, priv_hex
