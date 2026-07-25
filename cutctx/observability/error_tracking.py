"""Optional error tracking (Sentry-compatible).

The product had Prometheus metrics, OTel wiring, and structured logging, but no
error tracker — so an unhandled exception in a customer deployment left no
aggregated trace anywhere, and operators only learned about failures from logs
they had to go looking for. An audit scored observability 5/10 partly for this.

Design constraints that shaped this module:

* **No new hard dependency.** ``sentry-sdk`` is an optional extra. If it is not
  installed, or no DSN is configured, every function here is a no-op. Importing
  this module must never fail and never slow startup.
* **Off unless explicitly configured.** Nothing is sent anywhere until an
  operator sets ``CUTCTX_SENTRY_DSN``. This is a local-first, privacy-sensitive
  product; silently phoning home would be a violation of that.
* **Scrub by default.** Compression payloads are customer source code, logs,
  and prompts. Request bodies and local variables are never transmitted.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger("cutctx.observability.error_tracking")

_initialised = False


def dsn() -> str | None:
    """Configured DSN, or None when error tracking is disabled."""
    value = os.environ.get("CUTCTX_SENTRY_DSN", "").strip()
    return value or None


def environment() -> str:
    """Deployment environment label, for grouping in the error tracker."""
    return (
        os.environ.get("CUTCTX_SENTRY_ENVIRONMENT")
        or os.environ.get("CUTCTX_DEPLOYMENT_PROFILE")
        or "unknown"
    )


def traces_sample_rate() -> float:
    """Performance-trace sample rate. Defaults to 0 — errors only.

    Tracing every request on a latency-sensitive proxy is a cost the operator
    should opt into deliberately.
    """
    raw = os.environ.get("CUTCTX_SENTRY_TRACES_SAMPLE_RATE", "0").strip()
    try:
        rate = float(raw)
    except ValueError:
        logger.warning("CUTCTX_SENTRY_TRACES_SAMPLE_RATE=%r is not a number; using 0", raw)
        return 0.0
    return min(max(rate, 0.0), 1.0)


def is_enabled() -> bool:
    """Whether error tracking is active in this process."""
    return _initialised


def _scrub(event: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any] | None:
    """Strip payload-bearing fields before an event leaves the process.

    Compressed content is customer code, logs, and prompts. None of it belongs
    in an error report, so request bodies and stack-frame locals are removed
    rather than relied upon to be uninteresting.
    """
    request = event.get("request")
    if isinstance(request, dict):
        request.pop("data", None)
        request.pop("cookies", None)
        headers = request.get("headers")
        if isinstance(headers, dict):
            for key in list(headers):
                if key.lower() in {
                    "authorization",
                    "x-api-key",
                    "x-cutctx-admin-key",
                    "x-cutctx-user-token",
                    "cookie",
                }:
                    headers[key] = "[redacted]"

    for entry in event.get("exception", {}).get("values", []) or []:
        for frame in entry.get("stacktrace", {}).get("frames", []) or []:
            frame.pop("vars", None)

    return event


def init(release: str | None = None) -> bool:
    """Initialise error tracking if configured. Returns True when active.

    Safe to call more than once; subsequent calls are no-ops. Never raises —
    a misconfigured error tracker must not prevent the proxy from starting.
    """
    global _initialised

    if _initialised:
        return True

    configured = dsn()
    if not configured:
        return False

    try:
        import sentry_sdk
    except ImportError:
        # ImportError, not just ModuleNotFoundError: a partially installed or
        # broken sentry_sdk raises the parent class, and that must degrade to
        # "tracking off" rather than taking the proxy down.
        logger.warning(
            "CUTCTX_SENTRY_DSN is set but sentry-sdk could not be imported; "
            "error tracking is disabled. Install with: "
            "pip install 'cutctx-ai[sentry]'"
        )
        return False

    try:
        sentry_sdk.init(
            dsn=configured,
            environment=environment(),
            release=release,
            traces_sample_rate=traces_sample_rate(),
            # Never ship request bodies or PII by default.
            send_default_pii=False,
            max_request_body_size="never",
            before_send=_scrub,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Error tracking failed to initialise (%s); continuing without it", exc)
        return False

    _initialised = True
    logger.info("Error tracking initialised (environment=%s)", environment())
    return True


def capture_exception(exc: BaseException) -> None:
    """Report an exception if tracking is active; otherwise do nothing."""
    if not _initialised:
        return
    try:
        import sentry_sdk

        sentry_sdk.capture_exception(exc)
    except Exception:  # pragma: no cover - never mask the original error
        logger.debug("Failed to report exception to the error tracker", exc_info=True)


def reset_for_tests() -> None:
    """Clear module state. Test-support only."""
    global _initialised
    _initialised = False
