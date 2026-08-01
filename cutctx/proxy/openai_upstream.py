"""Per-request OpenAI upstream override via ``x-cutctx-base-url``.

One proxy process resolves ``CutctxProxy.OPENAI_API_URL`` once at boot, so a
shared listener (127.0.0.1:8787) cannot serve a client that needs a different
OpenAI-compatible upstream — OpenCode's ``https://opencode.ai/zen/go`` being
the motivating case. This module lets such a client name its upstream per
request while keeping every other client byte-identical.

The resolved value is returned to the caller and never written back onto the
proxy instance or class: concurrent requests with and without the header must
stay independent.

Security model. The header is only honoured when *all* of the following hold:

* the connection is trusted local seat traffic (loopback bind, loopback
  ``Host:``, loopback peer) — same gate the local-seat path uses;
* the client supplied its own ``Authorization``. The proxy will not hand a
  process-wide operator credential to a client-named upstream, so an override
  without a caller credential is refused rather than silently billed (and
  leaked) against the operator's OpenAI key;
* the URL is ``https``, with no userinfo, query or fragment;
* the host is on the allowlist (defaults ``opencode.ai`` and
  ``api.deepseek.com``, extended — not replaced — via
  ``CUTCTX_OPENAI_BASE_URL_ALLOWED_HOSTS``);
* an IP-literal host is globally routable (blocks loopback / link-local /
  private metadata endpoints such as ``169.254.169.254``);
* the path matches that host's default prefix (``/zen/go`` for OpenCode,
  root for DeepSeek) or an operator-configured prefix;
* the runtime egress policy allows the resolved URL;
* the request is *not* ChatGPT/OAuth subscription auth — that branch is
  evaluated first and wins, routing to chatgpt.com with the override refused.

Anything else is rejected with a distinct reason rather than silently ignored.
Redirects are not followed: the shared ``httpx.AsyncClient`` keeps httpx's
``follow_redirects=False`` default, so an allowlisted host cannot bounce the
request elsewhere.

The catch-all passthrough route honours the same header against arbitrary
OpenAI-compatible and Azure deployments, so it cannot use the allowlist above.
:func:`validate_passthrough_base_url` applies the host-independent half of the
gate (loopback peer, http(s), no userinfo, globally routable IP literals) and
lives here so both surfaces share one implementation.
"""

from __future__ import annotations

import ipaddress
import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from cutctx.proxy.egress import get_egress_enforcer

logger = logging.getLogger(__name__)

__all__ = [
    "ALLOWED_HOSTS_ENV",
    "ALLOWED_PATH_PREFIXES_ENV",
    "CAPABILITY_FLAG",
    "DEFAULT_ALLOWED_HOSTS",
    "DEFAULT_ALLOWED_PATH_PREFIXES",
    "OVERRIDE_HEADER",
    "OpenAIBaseUrlDecision",
    "override_capability_enabled",
    "override_metrics_snapshot",
    "override_rejection_payload",
    "override_rejection_status_code",
    "passthrough_rejection_payload",
    "reject_openai_base_url_override",
    "reset_override_metrics",
    "resolve_openai_base_url_override",
    "validate_passthrough_base_url",
]

#: Inbound header naming the desired upstream base URL.
OVERRIDE_HEADER = "x-cutctx-base-url"

#: Capability advertised on ``/health`` so clients can probe support before
#: choosing between the shared port and a dedicated private port.
CAPABILITY_FLAG = "per_request_openai_base_url"

DEFAULT_HOST_PATH_PREFIXES: dict[str, tuple[str, ...]] = {
    "opencode.ai": ("/zen/go",),
    "api.deepseek.com": ("/",),
}
DEFAULT_ALLOWED_HOSTS: tuple[str, ...] = tuple(DEFAULT_HOST_PATH_PREFIXES)
DEFAULT_ALLOWED_PATH_PREFIXES: tuple[str, ...] = ("/zen/go",)

ALLOWED_HOSTS_ENV = "CUTCTX_OPENAI_BASE_URL_ALLOWED_HOSTS"
ALLOWED_PATH_PREFIXES_ENV = "CUTCTX_OPENAI_BASE_URL_ALLOWED_PATH_PREFIXES"

#: Refusal reason for the direct-path-only contract: a translated backend
#: (LiteLLM / any-llm) builds its own upstream, so honouring the header would
#: silently send the request somewhere the client did not ask for.
TRANSLATED_BACKEND_REASON = "translated_backend_active"

#: Refusal reason when the client named an upstream but sent no credential of
#: its own. Falling back to the operator's ``OPENAI_API_KEY`` here would ship
#: that key to whatever host the client picked.
MISSING_CLIENT_CREDENTIAL_REASON = "client_credential_required"

_STATUS_ABSENT = "absent"
_STATUS_ACCEPTED = "accepted"
_STATUS_IGNORED = "ignored"
_STATUS_REJECTED = "rejected"


@dataclass(frozen=True)
class OpenAIBaseUrlDecision:
    """Outcome of evaluating ``x-cutctx-base-url`` for one request."""

    status: str
    reason: str
    base_url: str | None = None
    host: str | None = None

    @property
    def active(self) -> bool:
        """True when the caller should send upstream to :attr:`base_url`."""
        return self.status == _STATUS_ACCEPTED

    @property
    def rejected(self) -> bool:
        """True when the caller must fail the request instead of forwarding."""
        return self.status == _STATUS_REJECTED


_ABSENT = OpenAIBaseUrlDecision(status=_STATUS_ABSENT, reason="header_absent")

_metrics: dict[str, int] = {}


def override_metrics_snapshot() -> dict[str, int]:
    """Return per-outcome counters (``accepted`` / ``denied_<reason>``)."""
    return dict(_metrics)


def reset_override_metrics() -> None:
    """Drop the counters (tests + operator reset)."""
    _metrics.clear()


def _count(key: str) -> None:
    _metrics[key] = _metrics.get(key, 0) + 1


def _accepted(base_url: str, host: str) -> OpenAIBaseUrlDecision:
    _count("accepted")
    logger.info("openai base-url override accepted (upstream_host=%s)", host)
    return OpenAIBaseUrlDecision(
        status=_STATUS_ACCEPTED,
        reason="accepted",
        base_url=base_url,
        host=host,
    )


def _denied(status: str, reason: str) -> OpenAIBaseUrlDecision:
    _count(f"denied_{reason}")
    logger.warning("openai base-url override denied (reason=%s)", reason)
    return OpenAIBaseUrlDecision(status=status, reason=reason)


def reject_openai_base_url_override(reason: str) -> OpenAIBaseUrlDecision:
    """Record a call-site refusal (for example a translated backend)."""
    return _denied(_STATUS_REJECTED, reason)


def override_rejection_payload(decision: OpenAIBaseUrlDecision) -> dict[str, Any]:
    """OpenAI-shaped error body naming the refusal reason."""
    if decision.reason == MISSING_CLIENT_CREDENTIAL_REASON:
        return {
            "error": {
                "message": (
                    f"Refused {OVERRIDE_HEADER} upstream override: "
                    f"{MISSING_CLIENT_CREDENTIAL_REASON}. A request that names its "
                    "own upstream must carry its own Authorization header; the "
                    "proxy will not forward its configured OpenAI credential to a "
                    "client-selected host."
                ),
                "type": "invalid_request_error",
                "code": "base_url_override_requires_credential",
            }
        }
    return {
        "error": {
            "message": (
                f"Refused {OVERRIDE_HEADER} upstream override: {decision.reason}. "
                "The override is direct-path only and requires an https URL on a "
                "loopback connection with an allowlisted host and path."
            ),
            "type": "invalid_request_error",
            "code": "base_url_override_rejected",
        }
    }


def override_rejection_status_code(decision: OpenAIBaseUrlDecision) -> int:
    """HTTP status for a refused override.

    A missing caller credential is an authentication failure, not a malformed
    request, so the client gets a 401 it can act on by attaching its own key.
    """
    return 401 if decision.reason == MISSING_CLIENT_CREDENTIAL_REASON else 400


def passthrough_rejection_payload(reason: str) -> dict[str, Any]:
    """OpenAI-shaped 400 body for a refused catch-all passthrough override."""
    return {
        "error": {
            "message": (
                f"Refused {OVERRIDE_HEADER} passthrough upstream: {reason}. "
                "Passthrough overrides accept http(s) URLs without userinfo, "
                "addressed to a globally routable host, from a local client."
            ),
            "type": "invalid_request_error",
            "code": "base_url_passthrough_rejected",
        }
    }


def override_capability_enabled(proxy: Any) -> bool:
    """Whether this runtime could actually honour ``x-cutctx-base-url``.

    Advertised on ``/health`` so a client can choose the shared listener over a
    dedicated private port. It has to mirror the runtime gate rather than the
    presence of the code: on a non-loopback bind every override is refused, and
    a translated backend makes the chat handler refuse them outright, so a
    client that trusted a hardcoded ``true`` would hard-fail on the shared port.
    """
    from cutctx.proxy.loopback_guard import is_loopback_host

    config = getattr(proxy, "config", None)
    bind_host = getattr(config, "host", None)
    if not bind_host or not is_loopback_host(bind_host):
        return False
    return getattr(proxy, "anthropic_backend", None) is None


def resolve_openai_base_url_override(
    proxy: Any,
    connection: Any,
    raw_headers: Mapping[str, str],
    *,
    is_chatgpt_auth: bool,
) -> OpenAIBaseUrlDecision:
    """Evaluate ``x-cutctx-base-url`` against the SSRF gate.

    ``raw_headers`` must be the *inbound* headers, captured before
    ``_strip_internal_headers`` removes the ``x-cutctx-*`` control set.
    """
    lowered = {key.lower(): value for key, value in raw_headers.items()}
    requested = (lowered.get(OVERRIDE_HEADER) or "").strip()
    if not requested:
        return _ABSENT

    # Subscription auth owns routing: chatgpt.com wins and the override is
    # refused (not applied), so the request still reaches the right backend.
    if is_chatgpt_auth or "chatgpt-account-id" in lowered:
        return _denied(_STATUS_IGNORED, "chatgpt_subscription_auth")

    if not _is_trusted_local_connection(proxy, connection, lowered):
        return _denied(_STATUS_REJECTED, "untrusted_connection")

    # The upstream credential must come from the caller. Handlers otherwise
    # fall back to injecting the operator's configured OPENAI_API_KEY, which on
    # a shared listener would ship that key to whichever host the client named.
    if not (lowered.get("authorization") or "").strip():
        return _denied(_STATUS_REJECTED, MISSING_CLIENT_CREDENTIAL_REASON)

    if any(character.isspace() or ord(character) < 0x20 for character in requested):
        return _denied(_STATUS_REJECTED, "malformed_url")

    parsed = urlsplit(requested)
    if parsed.scheme.lower() != "https":
        return _denied(_STATUS_REJECTED, "scheme_not_https")
    if parsed.username is not None or parsed.password is not None or "@" in parsed.netloc:
        return _denied(_STATUS_REJECTED, "userinfo_not_allowed")
    if parsed.query:
        return _denied(_STATUS_REJECTED, "query_not_allowed")
    if parsed.fragment:
        return _denied(_STATUS_REJECTED, "fragment_not_allowed")

    try:
        hostname = parsed.hostname or ""
    except ValueError:
        return _denied(_STATUS_REJECTED, "malformed_url")
    host = _canonical_host(hostname)
    if not host:
        return _denied(_STATUS_REJECTED, "malformed_url")
    if not _is_global_address(host):
        return _denied(_STATUS_REJECTED, "non_global_address")
    if not _host_allowed(host):
        return _denied(_STATUS_REJECTED, "host_not_allowed")

    from cutctx.providers.registry import _normalize_api_url

    base_url = _normalize_api_url(requested, default=requested)
    if not _path_allowed(host, urlsplit(base_url).path):
        return _denied(_STATUS_REJECTED, "path_not_allowed")

    egress_decision = get_egress_enforcer().check(base_url)
    if not egress_decision.allowed:
        return _denied(_STATUS_REJECTED, f"egress_{egress_decision.reason}")

    return _accepted(base_url, host)


def validate_passthrough_base_url(
    connection: Any,
    requested: str,
) -> tuple[str | None, str | None]:
    """Vet an ``x-cutctx-base-url`` used by the catch-all passthrough route.

    Returns ``(base_url, None)`` when the value may be used, or
    ``(None, reason)`` when it must be refused.

    Deliberately looser than :func:`resolve_openai_base_url_override`: Azure
    deployments live on per-tenant hostnames, so no host allowlist can apply
    here. What remains is the host-independent SSRF surface — only a local
    client may name an upstream, only over http(s), with no userinfo, and never
    at a non-globally-routable IP literal such as ``169.254.169.254``.
    """
    from cutctx.auth.local_seat import is_loopback_seat_peer

    client = getattr(connection, "client", None)
    if not is_loopback_seat_peer(getattr(client, "host", None) if client is not None else None):
        return None, _passthrough_denied("untrusted_connection")

    candidate = requested.strip()
    if not candidate or any(
        character.isspace() or ord(character) < 0x20 for character in candidate
    ):
        return None, _passthrough_denied("malformed_url")

    parsed = urlsplit(candidate)
    if parsed.scheme.lower() not in {"http", "https"}:
        return None, _passthrough_denied("scheme_not_http")
    if parsed.username is not None or parsed.password is not None or "@" in parsed.netloc:
        return None, _passthrough_denied("userinfo_not_allowed")

    try:
        hostname = parsed.hostname or ""
    except ValueError:
        return None, _passthrough_denied("malformed_url")
    host = _canonical_host(hostname)
    if not host:
        return None, _passthrough_denied("malformed_url")
    if not _is_global_address(host):
        return None, _passthrough_denied("non_global_address")

    return candidate.rstrip("/"), None


def _passthrough_denied(reason: str) -> str:
    _count(f"passthrough_denied_{reason}")
    logger.warning("passthrough base-url override denied (reason=%s)", reason)
    return reason


def _is_trusted_local_connection(
    proxy: Any,
    connection: Any,
    lowered_headers: Mapping[str, str],
) -> bool:
    from cutctx.auth.local_seat import is_trusted_local_seat_connection

    client = getattr(connection, "client", None)
    client_host = getattr(client, "host", None) if client is not None else None
    config = getattr(proxy, "config", None)
    return is_trusted_local_seat_connection(
        bind_host=getattr(config, "host", None),
        host_header=lowered_headers.get("host"),
        client_host=client_host,
    )


def _canonical_host(host: str) -> str:
    from cutctx.proxy.egress import _normalize_host

    return _normalize_host(host)


def _is_global_address(host: str) -> bool:
    """True unless ``host`` is an IP literal that must never be an upstream.

    DNS names pass here and are gated by the host allowlist instead.
    """
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return True
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    return bool(address.is_global)


def _env_entries(name: str) -> tuple[str, ...]:
    raw = os.environ.get(name, "")
    return tuple(entry.strip() for entry in raw.replace(",", " ").split() if entry.strip())


def _host_allowed(host: str) -> bool:
    for pattern in DEFAULT_ALLOWED_HOSTS + _env_entries(ALLOWED_HOSTS_ENV):
        candidate = pattern.strip().lower()
        if candidate.startswith("*."):
            if host.endswith(f".{_canonical_host(candidate[2:])}"):
                return True
            continue
        if host == _canonical_host(candidate):
            return True
    return False


def _path_allowed(host: str, path: str) -> bool:
    normalized = path or "/"
    if ".." in normalized.split("/"):
        return False
    prefixes = DEFAULT_HOST_PATH_PREFIXES.get(host, ()) + _env_entries(ALLOWED_PATH_PREFIXES_ENV)
    for prefix in prefixes:
        candidate = prefix.rstrip("/")
        if not candidate:
            candidate = "/"
        if not candidate.startswith("/"):
            candidate = f"/{candidate}"
        if candidate == "/":
            return normalized.startswith("/")
        if normalized == candidate or normalized.startswith(f"{candidate}/"):
            return True
    return False
