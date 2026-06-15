#!/usr/bin/env python3
import argparse
import sys
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

def generate_keypair():
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    priv_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    pub_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    
    return priv_bytes.hex(), pub_bytes.hex()

def main():
    parser = argparse.ArgumentParser(description="Generate Ed25519 keypair for HRK1 license tokens")
    parser.add_argument("--kid", required=True, help="Key ID (e.g. 1)")
    args = parser.parse_args()

    priv_hex, pub_hex = generate_keypair()
    print("=== Ed25519 License Keypair ===")
    print(f"KID: {args.kid}")
    print(f"Public Key (hex) : {pub_hex}")
    print(f"Private Key (hex): {priv_hex}")
    print("\nRust Proxy Configuration:")
    print(f'export HEADROOM_LICENSE_PUBLIC_KEYS="{args.kid}:{pub_hex}"')
    print("\nPython Issuer Configuration:")
    print(f'export HEADROOM_LICENSE_PRIVATE_KEY="{priv_hex}"')
    print(f'export HEADROOM_LICENSE_KID="{args.kid}"')

if __name__ == "__main__":
    main()
