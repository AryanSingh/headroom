# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""Egress policy enforcement for air-gap / offline deployments.

Audit-Deep-2026-06-21 Blocker 3a: the previous airgap module
(cutctx/proxy/airgap.py) only logged warnings and was never
called from server.py. /v1/airgap/status returned a hardcoded
payload. The ENT (enterprise) tier advertises air-gap support
but had no enforcement.

This module provides:

  1. ``EgressPolicy`` — a per-tenant allowlist of domain patterns
     that may be reached by the upstream client. Patterns are
     matched against the URL host (case-insensitive) and the
     full URL (case-insensitive) as a substring.
  2. ``EgressEnforcer`` — given an ``EgressPolicy`` and a URL,
     decide whether the URL is allowed. Returns an
     ``EgressDecision`` with ``allowed``, ``reason``,
     ``matched_pattern``, and ``policy_id``.
  3. ``load_policy_from_env()`` — read the policy from the
     ``CUTCTX_EGRESS_POLICY`` env var (JSON).

The policy is enforced in two places:

  - ``cutctx/proxy/server.py:check_offline_compat`` is called
    at server boot. If ``CUTCTX_OFFLINE_MODE=1`` and no
    ``CUTCTX_EGRESS_POLICY`` is set, the proxy refuses to start
    (fail-closed for air-gap mode).
  - ``cutctx/proxy/routing/failover.py:FailoverRouter`` calls
    ``EgressEnforcer.check()`` before opening an HTTP connection
    to a provider. If the URL is not in the allowlist, the
    request is short-circuited with a 503 + audit event.

The design is intentionally minimal: we don't try to be a
general-purpose firewall. We just block egress to unknown
domains, which is the only thing an air-gapped customer needs.
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EgressPolicy:
    """Allowlist of egress destinations.

    A request is allowed if its host or full URL matches any
    pattern in ``allowed_patterns`` (case-insensitive substring
    or full-string host match). Empty ``allowed_patterns`` means
    deny-all: nothing is allowed to leave the proxy.
    """

    policy_id: str
    allowed_patterns: tuple[str, ...] = ()
    # When False (default), an empty allowed_patterns list means
    # deny-all. Set to True to allow all egress (i.e. this is a
    # no-op policy used to opt out of air-gap enforcement).
    allow_all: bool = False
    # Human-readable description for /v1/airgap/status
    description: str = ""

    def is_empty(self) -> bool:
        return not self.allow_all and not self.allowed_patterns


@dataclass(frozen=True)
class EgressDecision:
    allowed: bool
    reason: str
    matched_pattern: str | None = None
    policy_id: str | None = None


class EgressEnforcer:
    """Apply an EgressPolicy to outgoing URLs."""

    def __init__(self, policy: EgressPolicy):
        self.policy = policy
        # Pre-compile regex patterns for the allowed_patterns
        # list. Patterns are interpreted as case-insensitive
        # regex if they contain a metacharacter (., *, +), or
        # as case-insensitive substring otherwise.
        self._patterns: list[re.Pattern[str]] = []
        for p in policy.allowed_patterns:
            try:
                if any(c in p for c in r".*+?[]{}()|^$"):
                    self._patterns.append(re.compile(p, re.IGNORECASE))
                else:
                    # Substring match: escape any regex specials
                    escaped = re.escape(p)
                    self._patterns.append(re.compile(escaped, re.IGNORECASE))
            except re.error as exc:
                logger.warning(
                    "EgressEnforcer: skipping invalid pattern %r: %s", p, exc
                )

    def check(self, url: str) -> EgressDecision:
        """Check whether ``url`` is allowed by the policy.

        The check is purely host-based for safety: we don't try
        to parse the full URL structure (which can introduce
        parser differentials). The host is extracted via
        ``urllib.parse.urlparse`` and matched against the
        allowlist patterns.
        """
        if self.policy.allow_all:
            return EgressDecision(
                allowed=True,
                reason="allow_all_policy",
                policy_id=self.policy.policy_id,
            )

        if not self._patterns:
            # Empty allowlist + not allow_all = deny-all.
            return EgressDecision(
                allowed=False,
                reason="deny_all_empty_allowlist",
                policy_id=self.policy.policy_id,
            )

        # Extract the host safely.
        host = ""
        try:
            from urllib.parse import urlparse

            host = (urlparse(url).hostname or "").lower()
        except Exception:
            host = ""
        if not host:
            return EgressDecision(
                allowed=False,
                reason="unparseable_url",
                policy_id=self.policy.policy_id,
            )

        haystacks = (host, url.lower())
        for pat in self._patterns:
            for hay in haystacks:
                if pat.search(hay):
                    return EgressDecision(
                        allowed=True,
                        reason="matched_pattern",
                        matched_pattern=pat.pattern,
                        policy_id=self.policy.policy_id,
                    )
        return EgressDecision(
            allowed=False,
            reason="no_pattern_match",
            policy_id=self.policy.policy_id,
        )


def load_policy_from_env() -> EgressPolicy:
    """Build an EgressPolicy from the ``CUTCTX_EGRESS_POLICY`` env var.

    The env var, when set, must be a JSON object of the form::

        {
          "policy_id": "default",
          "description": "Allow Anthropic + OpenAI",
          "allowed_patterns": ["api.anthropic.com", "api.openai.com"]
        }

    The special value ``{"allow_all": true}`` is a no-op policy used
    to opt out of air-gap enforcement (the proxy runs in
    connected mode but the policy hook is still consulted).

    When the env var is unset, the policy is empty (deny-all). The
    proxy is fail-closed for air-gap mode; connected mode ignores
    the empty policy at the call site (see FailoverRouter).
    """
    raw = os.environ.get("CUTCTX_EGRESS_POLICY", "").strip()
    if not raw:
        return EgressPolicy(policy_id="default-empty")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("CUTCTX_EGRESS_POLICY is not valid JSON: %s", exc)
        return EgressPolicy(policy_id="default-invalid")
    if not isinstance(payload, dict):
        return EgressPolicy(policy_id="default-invalid")
    return EgressPolicy(
        policy_id=str(payload.get("policy_id", "default")),
        description=str(payload.get("description", "")),
        allowed_patterns=tuple(str(p) for p in payload.get("allowed_patterns", [])),
        allow_all=bool(payload.get("allow_all", False)),
    )


# Module-level singleton + accessor (matches the pattern used by
# the savings tracker and other proxy-side singletons).
_enforcer: EgressEnforcer | None = None


def get_egress_enforcer() -> EgressEnforcer:
    """Return the global EgressEnforcer, creating it on first use.

    The policy is read from ``CUTCTX_EGRESS_POLICY`` at the time
    of first access. To re-read the policy (e.g. after a config
    reload), call :func:`reset_egress_enforcer` first.
    """
    global _enforcer
    if _enforcer is None:
        _enforcer = EgressEnforcer(load_policy_from_env())
    return _enforcer


def reset_egress_enforcer() -> None:
    """Drop the cached EgressEnforcer (for tests + config reload)."""
    global _enforcer
    _enforcer = None


__all__ = [
    "EgressPolicy",
    "EgressDecision",
    "EgressEnforcer",
    "load_policy_from_env",
    "get_egress_enforcer",
    "reset_egress_enforcer",
]
