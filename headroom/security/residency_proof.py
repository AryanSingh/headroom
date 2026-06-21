# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs contributors.
# Licensed under the Apache License, Version 2.0 — see LICENSE for details.
"""Verifiable data-residency attestation for the Cutctx proxy.

Generates a signed (or unsigned) snapshot that proves:
  - which data regions are configured for this tenant
  - which egress domains the firewall is actively blocking
  - the current tail hash of the tamper-evident audit chain

The attestation is a plain dataclass that can be serialised to JSON and
verified offline with nothing more than the Ed25519 public key.  Commercial
signing (``headroom_ee``) is optional — the module degrades gracefully when
the EE wheel is absent.

Usage::

    from headroom.security.residency_proof import ResidencyProver

    prover = ResidencyProver(tenant_id="acme-corp")
    attest = prover.generate(data_regions=["eu-west-1"], sign=False)
    print(prover.export_json(attest))
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    pass

logger = logging.getLogger("headroom.security.residency_proof")

# ---------------------------------------------------------------------------
# Attestation dataclass
# ---------------------------------------------------------------------------


@dataclass
class ResidencyAttestation:
    """Snapshot of data-residency posture at a point in time.

    Fields
    ------
    tenant_id:
        Identifier of the tenant this attestation is for.
    proxy_version:
        Semver string of the running headroom proxy.
    timestamp_iso:
        ISO-8601 UTC timestamp at which the attestation was generated.
    attested_at_ts:
        Unix epoch (float seconds) — machine-readable alias for timestamp_iso.
    audit_chain_tail_hash:
        The ``event_hash`` of the most-recent row in the EE audit chain for
        this tenant, or ``None`` if the audit store is unavailable.
    data_regions:
        List of cloud/geo regions declared by the operator (e.g. "eu-west-1").
    egress_domains_blocked:
        Domains that the firewall is configured to block outbound.
    signature_hex:
        Hex-encoded Ed25519 signature over the canonical JSON payload, or
        ``None`` when the attestation is unsigned.
    signer_kid:
        Key-ID of the signing key, or ``None`` when unsigned.
    """

    tenant_id: str
    proxy_version: str
    timestamp_iso: str
    attested_at_ts: float
    audit_chain_tail_hash: str | None
    data_regions: list[str] = field(default_factory=list)
    egress_domains_blocked: list[str] = field(default_factory=list)
    signature_hex: str | None = None
    signer_kid: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_proxy_version() -> str:
    """Return the running proxy version, falling back gracefully."""
    try:
        from headroom._version import __version__

        return __version__
    except Exception:  # noqa: BLE001
        return "unknown"


def _canonical_payload(attest: ResidencyAttestation) -> bytes:
    """Return the deterministic bytes signed / verified by Ed25519.

    We exclude ``signature_hex`` and ``signer_kid`` so that the signature
    covers the content, not itself.
    """
    d = asdict(attest)
    d.pop("signature_hex", None)
    d.pop("signer_kid", None)
    return json.dumps(d, sort_keys=True, separators=(",", ":")).encode("utf-8")


# ---------------------------------------------------------------------------
# ResidencyProver
# ---------------------------------------------------------------------------


class ResidencyProver:
    """Generates and verifies ``ResidencyAttestation`` instances.

    Parameters
    ----------
    tenant_id:
        Tenant identifier included in every attestation.
    audit_store:
        Optional EE ``AuditStore`` instance.  If *None* the prover will
        attempt a lazy import of ``headroom_ee.audit.store.AuditStore``
        at ``generate()`` time, and silently skip it when unavailable.
    """

    def __init__(
        self,
        tenant_id: str,
        audit_store: Any = None,
    ) -> None:
        self.tenant_id = tenant_id
        self._audit_store = audit_store  # may be None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        data_regions: list[str] | None = None,
        sign: bool = False,
    ) -> ResidencyAttestation:
        """Generate a new attestation snapshot.

        Parameters
        ----------
        data_regions:
            Cloud/geo region identifiers to record.  Defaults to ``[]``.
        sign:
            When *True*, sign the attestation with the EE Ed25519 key
            configured via ``HEADROOM_LICENSE_KID`` /
            ``HEADROOM_LICENSE_PRIVATE_KEY`` environment variables.
            Raises ``RuntimeError`` if ``headroom_ee`` is not installed.

        Returns
        -------
        ResidencyAttestation
        """
        now = datetime.now(timezone.utc)
        timestamp_iso = now.isoformat()
        attested_at_ts = now.timestamp()

        audit_tail = self._get_audit_chain_tail()
        blocked_domains = self._get_blocked_domains()

        attest = ResidencyAttestation(
            tenant_id=self.tenant_id,
            proxy_version=_get_proxy_version(),
            timestamp_iso=timestamp_iso,
            attested_at_ts=attested_at_ts,
            audit_chain_tail_hash=audit_tail,
            data_regions=list(data_regions or []),
            egress_domains_blocked=blocked_domains,
            signature_hex=None,
            signer_kid=None,
        )

        if sign:
            attest = self._sign(attest)

        return attest

    def verify(self, attestation: ResidencyAttestation) -> bool:
        """Verify the Ed25519 signature on an attestation.

        Returns ``True`` if:
        - the attestation carries a valid signature that verifies against the
          public key obtained from ``HEADROOM_LICENSE_PUBLIC_KEY``; *or*
        - the attestation has no signature (unverified / informational mode).

        Returns ``False`` if a signature is present but verification fails.
        """
        if attestation.signature_hex is None:
            # Unsigned attestation — informational mode, consider valid.
            logger.debug(
                "verify(): attestation for tenant=%r is unsigned; returning True",
                attestation.tenant_id,
            )
            return True

        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                Ed25519PublicKey,
            )
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "cryptography package required for signature verification: %s" % exc
            ) from exc

        import os

        pub_hex = os.environ.get("HEADROOM_LICENSE_PUBLIC_KEY", "")
        if not pub_hex:
            logger.warning(
                "verify(): HEADROOM_LICENSE_PUBLIC_KEY not set; cannot verify signature"
            )
            return False

        try:
            pub_bytes = bytes.fromhex(pub_hex)
            public_key = Ed25519PublicKey.from_public_bytes(pub_bytes)
            sig_bytes = bytes.fromhex(attestation.signature_hex)
            payload = _canonical_payload(attestation)
            # Signer signs SHA-256(payload).digest() (see _sign() below);
            # Ed25519 also accepts raw messages, so the verifier MUST hash
            # the payload to match. Without this, the in-process
            # `prover.verify(prover.sign(attest))` round-trip returns False
            # for a valid signature.
            digest = hashlib.sha256(payload).digest()
            public_key.verify(sig_bytes, digest)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("verify(): signature verification failed: %s", exc)
            return False

    def export_json(self, attestation: ResidencyAttestation) -> str:
        """Serialise the attestation to a compact JSON string.

        The returned string is safe to store, transmit, or embed in logs.
        No raw content (only hashes and metadata) is included.
        """
        d: dict[str, Any] = asdict(attestation)
        return json.dumps(d, sort_keys=True, indent=2)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_audit_chain_tail(self) -> str | None:
        """Return the tail ``event_hash`` from the EE audit store."""
        store = self._audit_store
        if store is None:
            try:
                from headroom_ee.audit.store import AuditStore  # type: ignore[import]

                import os

                db_url = os.environ.get(
                    "HEADROOM_AUDIT_DB_URL",
                    "sqlite:///headroom_audit.db",
                )
                store = AuditStore(db_url=db_url)
            except ImportError:
                logger.debug(
                    "_get_audit_chain_tail(): headroom_ee not available; "
                    "audit_chain_tail_hash will be None"
                )
                return None
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "_get_audit_chain_tail(): could not connect to audit store: %s", exc
                )
                return None

        try:
            events = store.get_events(self.tenant_id, limit=1)
            if events:
                tail_hash: str | None = events[0].get("event_hash")
                return tail_hash
            return None
        except Exception as exc:  # noqa: BLE001
            logger.warning("_get_audit_chain_tail(): query failed: %s", exc)
            return None

    @staticmethod
    def _get_blocked_domains() -> list[str]:
        """Return domains tracked/blocked by the firewall scanner."""
        try:
            from headroom.security.firewall import FirewallScanner

            scanner = FirewallScanner()
            return scanner.get_blocked_domains()
        except AttributeError:
            # get_blocked_domains not yet present — return empty list
            return []
        except Exception as exc:  # noqa: BLE001
            logger.debug("_get_blocked_domains(): %s", exc)
            return []

    def _sign(self, attest: ResidencyAttestation) -> ResidencyAttestation:
        """Return a new attestation with Ed25519 signature applied."""
        try:
            from headroom_ee.billing.license_token import (  # type: ignore[import]
                get_default_issuer_config,
            )
            from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                Ed25519PrivateKey,
            )
        except ImportError as exc:
            raise RuntimeError(
                "headroom_ee is required for signed attestations: %s" % exc
            ) from exc

        kid, priv_hex = get_default_issuer_config()
        if not kid or not priv_hex:
            raise RuntimeError(
                "HEADROOM_LICENSE_KID and HEADROOM_LICENSE_PRIVATE_KEY must be set "
                "to generate signed attestations"
            )

        payload = _canonical_payload(attest)
        # Compute a SHA-256 digest so the signed message is fixed-size
        digest = hashlib.sha256(payload).digest()

        try:
            priv_bytes = bytes.fromhex(priv_hex)
            private_key = Ed25519PrivateKey.from_private_bytes(priv_bytes)
            signature = private_key.sign(digest)
        except Exception as exc:
            raise RuntimeError("Ed25519 signing failed: %s" % exc) from exc

        return ResidencyAttestation(
            tenant_id=attest.tenant_id,
            proxy_version=attest.proxy_version,
            timestamp_iso=attest.timestamp_iso,
            attested_at_ts=attest.attested_at_ts,
            audit_chain_tail_hash=attest.audit_chain_tail_hash,
            data_regions=list(attest.data_regions),
            egress_domains_blocked=list(attest.egress_domains_blocked),
            signature_hex=signature.hex(),
            signer_kid=kid,
        )
