"""License validation and usage reporting for managed/enterprise deployments.

Phone-home module that validates license keys and reports aggregate usage
statistics to the Cutctx cloud for billing. Designed to be non-intrusive:
the proxy works normally even if the cloud API is completely unreachable.

Privacy guarantees:
- Never sends message content, API keys, prompts, tool results, or user data
- Only sends aggregate counts: requests, tokens saved, model distribution
- All communication is over HTTPS

Usage:
    reporter = UsageReporter(license_key="hlk_...")
    license_info = await reporter.validate_license()
    await reporter.start(proxy)  # starts background loop
    ...
    await reporter.stop()
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

from cutctx import paths as _paths

if TYPE_CHECKING:
    from cutctx.proxy.server import CutctxProxy

logger = logging.getLogger("cutctx.telemetry.reporter")

# Grace period: if the cloud API is unreachable, use cached license for up to 7 days
GRACE_PERIOD_SECONDS = 7 * 24 * 3600  # 7 days

# Default cache location (workspace bucket, respects CUTCTX_WORKSPACE_DIR).
LICENSE_CACHE_PATH = _paths.license_cache_path()
#: Supabase edge-function base that actually serves the licence API. The
#: marketing site below never served `/v1/license/*` — it is an SPA, so those
#: paths fell through and answered HTTP 405 on POST.
_SUPABASE_FUNCTIONS_BASE = "https://udeekuvifncmqvoywhlg.supabase.co/functions/v1"

_DEFAULT_LICENSE_API_URL = (
    os.environ.get("PITCHTOSHIP_URL")
    or os.environ.get("CUTCTX_LICENSE_API_URL")
    or "https://pitchtoship.com"
)


@dataclass
class LicenseInfo:
    """Cached license validation result."""

    status: str  # "active", "trial", "expired", "invalid"
    org_id: str | None = None
    org_name: str | None = None
    plan: str | None = None
    quota_tokens: int | None = None  # None = unlimited
    trial_expires_at: datetime | None = None
    validated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON caching."""
        d = asdict(self)
        d["validated_at"] = self.validated_at.isoformat()
        if self.trial_expires_at:
            d["trial_expires_at"] = self.trial_expires_at.isoformat()
        return d

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime | None:
        """Parse ISO-8601 or HTTP-date timestamps from reporter/CLI caches."""
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value
        if not isinstance(value, str):
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            try:
                from email.utils import parsedate_to_datetime

                parsed = parsedate_to_datetime(value)
            except (TypeError, ValueError, IndexError):
                return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LicenseInfo:
        """Deserialize from JSON cache.

        Accepts both the UsageReporter flat shape and the CLI activation cache
        written by ``write_hmac_json`` (``{"payload": {...}}``).
        """
        if not isinstance(data, dict):
            return cls(status="invalid")
        # Bind once: calling data.get("payload") twice leaves the isinstance
        # check unable to narrow the second call, so every payload.get() below
        # reads as possibly-None to mypy.
        nested = data.get("payload")
        payload: dict[str, Any] = nested if isinstance(nested, dict) else data
        validated_at = cls._parse_timestamp(payload.get("validated_at")) or datetime.now(
            timezone.utc
        )
        trial_expires_at = cls._parse_timestamp(payload.get("trial_expires_at"))
        return cls(
            status=str(payload.get("status") or "invalid"),
            org_id=payload.get("org_id"),
            org_name=payload.get("org_name"),
            plan=payload.get("plan") or payload.get("tier"),
            quota_tokens=payload.get("quota_tokens"),
            trial_expires_at=trial_expires_at,
            validated_at=validated_at,
        )


class UsageReporter:
    """Background license validator and aggregate usage reporter.

    Validates the license key on startup, then periodically sends aggregate
    usage stats to the Cutctx cloud. If the cloud is unreachable, the proxy
    continues to operate using cached license info (grace period: 7 days).

    Never sends: message content, API keys, prompts, tool results, user data.
    """

    def __init__(
        self,
        license_key: str,
        cloud_url: str = _DEFAULT_LICENSE_API_URL,
        report_interval: int = 300,
        cache_path: Path | None = None,
        license_api_url: str | None = None,
    ):
        self._license_key = license_key
        self._cloud_url = cloud_url.rstrip("/")
        # Separate from cloud_url: licence validation lives on the Supabase
        # edge-function base, while cloud_url still addresses the portal.
        self._license_api_url_override = license_api_url.rstrip("/") if license_api_url else None
        self._report_interval = report_interval
        self._cache_path = cache_path or LICENSE_CACHE_PATH
        self._license_info: LicenseInfo | None = None
        self._proxy: CutctxProxy | None = None
        self._task: asyncio.Task[None] | None = None
        self._http_client: httpx.AsyncClient | None = None
        self._stopped = False

        # Snapshot of proxy metrics at last report (for computing deltas)
        self._last_report_time: datetime | None = None
        self._last_tokens_saved_by_model: dict[str, int] = {}
        self._last_tokens_sent_by_model: dict[str, int] = {}
        self._last_requests_by_model: dict[str, int] = {}

    @property
    def license_info(self) -> LicenseInfo | None:
        """Most recent validation result (None until validate_license ran)."""
        return self._license_info

    def _license_api_url(self) -> str:
        """Base URL of the licence API (Supabase edge functions).

        Deliberately separate from ``self._cloud_url``, which still addresses
        the PitchToShip site for anything that genuinely lives there.
        Resolution order: constructor argument, ``CUTCTX_LICENSE_API_URL``,
        then the deployed edge-function base.
        """
        if self._license_api_url_override:
            return self._license_api_url_override
        return (os.environ.get("CUTCTX_LICENSE_API_URL") or _SUPABASE_FUNCTIONS_BASE).rstrip("/")

    async def validate_license(self) -> LicenseInfo:
        """Validate the license key against the cloud API.

        On failure, falls back to cached license info if within grace period.
        """
        try:
            client = await self._get_client()
            # `verify-license` on the Supabase edge-function base, NOT
            # `/v1/license/validate` on the marketing site: that host is an SPA
            # and answered HTTP 405 for every POST, so this validation silently
            # never succeeded. The response handling below already tolerates
            # both shapes (it falls back to `valid` and `tier`).
            resp = await client.post(
                f"{self._license_api_url()}/verify-license",
                json={"key": self._license_key},
                timeout=10.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                status = data.get("status")
                if status is None:
                    status = "active" if data.get("valid") is True else "invalid"
                trial_expires_at = data.get("trial_expires_at")
                if isinstance(trial_expires_at, str):
                    trial_expires_at = datetime.fromisoformat(trial_expires_at)

                self._license_info = LicenseInfo(
                    status=status,
                    org_id=data.get("org_id"),
                    org_name=data.get("org_name"),
                    plan=data.get("plan") or data.get("tier"),
                    quota_tokens=data.get("quota_tokens"),
                    trial_expires_at=trial_expires_at,
                    validated_at=datetime.now(timezone.utc),
                )
                self._save_cache()
                logger.info(
                    "License validated: status=%s org=%s plan=%s",
                    self._license_info.status,
                    self._license_info.org_name,
                    self._license_info.plan,
                )
                return self._license_info
            if resp.status_code == 403:
                try:
                    rejection = resp.json().get("detail", {})
                except (json.JSONDecodeError, AttributeError, TypeError):
                    rejection = {}
                if rejection.get("error") != "validation_unavailable":
                    self._license_info = LicenseInfo(
                        status=rejection.get("status") or "invalid",
                        validated_at=datetime.now(timezone.utc),
                    )
                    self._save_cache()
                    logger.warning(
                        "License validation definitively rejected the license: status=%s",
                        self._license_info.status,
                    )
                    return self._license_info
            else:
                logger.warning(
                    "License validation returned status %d, using cached info",
                    resp.status_code,
                )
        except Exception:
            logger.warning(
                "Could not reach license server at %s, using cached info",
                self._cloud_url,
                exc_info=True,
            )

        # Fallback to cache
        return self._load_cache_or_default()

    async def start(self, proxy: CutctxProxy) -> None:
        """Start the background reporting loop. Called during proxy startup."""
        self._proxy = proxy
        self._stopped = False

        # Validate license first
        await self.validate_license()

        # Take initial snapshot of metrics
        self._snapshot_metrics()

        # Start background reporting loop
        self._task = asyncio.create_task(self._report_loop())
        logger.info(
            "Usage reporter started (interval=%ds, cloud=%s)",
            self._report_interval,
            self._cloud_url,
        )

    async def stop(self) -> None:
        """Stop the background reporting loop. Called during proxy shutdown."""
        self._stopped = True
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        logger.info("Usage reporter stopped")

    @property
    def is_active(self) -> bool:
        """Whether the license is valid and usage is within quota."""
        if self._license_info is None:
            return True  # No license info yet = allow (grace)
        return self._license_info.status in ("active", "trial")

    @property
    def should_compress(self) -> bool:
        """Whether compression should be applied. False = passthrough mode.

        Returns True (allow compression) unless the license is definitively expired
        AND outside the grace period.
        """
        if self._license_info is None:
            return True  # No license info yet = allow compression
        if self._license_info.status in ("active", "trial"):
            return True
        if self._license_info.status == "expired":
            # Check grace period
            age = (datetime.now(timezone.utc) - self._license_info.validated_at).total_seconds()
            if age < GRACE_PERIOD_SECONDS:
                return True
            return False
        # "invalid" or unknown status: still allow compression (fail open)
        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(10.0),
                headers={"User-Agent": "cutctx-proxy"},
            )
        return self._http_client

    async def _report_loop(self) -> None:
        """Background loop: report usage every N seconds."""
        while not self._stopped:
            try:
                await asyncio.sleep(self._report_interval)
                if self._stopped:
                    break
                await self._report_usage()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.warning("Usage report failed, will retry next interval", exc_info=True)

    async def _report_usage(self) -> None:
        """Collect aggregate stats from the proxy and send to cloud."""
        if self._proxy is None:
            return

        cost_tracker = self._proxy.cost_tracker
        if cost_tracker is None:
            return

        now = datetime.now(timezone.utc)
        period_start = self._last_report_time or now

        # Compute deltas since last report
        current_saved = dict(cost_tracker._tokens_saved_by_model)
        current_sent = dict(cost_tracker._tokens_sent_by_model)
        current_reqs = dict(cost_tracker._requests_by_model)

        delta_saved_by_model: dict[str, int] = {}
        delta_sent_by_model: dict[str, int] = {}
        delta_reqs_by_model: dict[str, int] = {}

        all_models = set(current_saved) | set(current_sent) | set(current_reqs)
        total_tokens_saved = 0
        total_tokens_before = 0
        total_tokens_after = 0
        total_requests = 0

        for model in all_models:
            saved = current_saved.get(model, 0) - self._last_tokens_saved_by_model.get(model, 0)
            sent = current_sent.get(model, 0) - self._last_tokens_sent_by_model.get(model, 0)
            reqs = current_reqs.get(model, 0) - self._last_requests_by_model.get(model, 0)
            if reqs > 0:
                delta_reqs_by_model[model] = reqs
            if saved > 0:
                delta_saved_by_model[model] = saved
            if sent > 0:
                delta_sent_by_model[model] = sent
            total_tokens_saved += max(0, saved)
            total_tokens_after += max(0, sent)
            total_tokens_before += max(0, saved) + max(0, sent)
            total_requests += max(0, reqs)

        # Skip empty reports
        if total_requests == 0:
            self._last_report_time = now
            return

        payload = {
            "license_key": self._license_key,
            "period_start": period_start.isoformat(),
            "period_end": now.isoformat(),
            "requests": total_requests,
            "tokens_before": total_tokens_before,
            "tokens_after": total_tokens_after,
            "tokens_saved": total_tokens_saved,
            "models": delta_reqs_by_model,
        }

        try:
            client = await self._get_client()
            # NOTE: there is no usage-reporting edge function among the seven
            # deployed (create-order, list-plans, my-licenses,
            # request-license-link, seat-heartbeat, verify-license,
            # verify-payment), so this POST currently 405s and the block below
            # simply does nothing. Left pointing at the portal rather than
            # guessed at: seat occupancy is already tracked by seat-heartbeat,
            # and inventing an endpoint here would repeat the mistake that
            # broke licence activation. Wire it up when the endpoint exists.
            resp = await client.post(
                f"{self._cloud_url}/v1/license/usage",
                json=payload,
                timeout=10.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                status = data.get("status")
                if status == "expired" and self._license_info:
                    self._license_info.status = "expired"
                    self._save_cache()
                    logger.warning("License expired: %s", data.get("message", ""))
                elif status and self._license_info:
                    self._license_info.status = status
                logger.debug(
                    "Usage reported: %d requests, %d tokens saved",
                    total_requests,
                    total_tokens_saved,
                )
            else:
                logger.warning("Usage report returned status %d", resp.status_code)
        except Exception:
            logger.warning("Failed to send usage report", exc_info=True)

        # Update snapshot
        self._snapshot_metrics()
        self._last_report_time = now

    def _snapshot_metrics(self) -> None:
        """Take a snapshot of current proxy metrics for delta computation."""
        if self._proxy is None or self._proxy.cost_tracker is None:
            return
        ct = self._proxy.cost_tracker
        self._last_tokens_saved_by_model = dict(ct._tokens_saved_by_model)
        self._last_tokens_sent_by_model = dict(ct._tokens_sent_by_model)
        self._last_requests_by_model = dict(ct._requests_by_model)
        self._last_report_time = datetime.now(timezone.utc)

    def _save_cache(self) -> None:
        """Save license info to local cache file."""
        if self._license_info is None:
            return
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(
                json.dumps(self._license_info.to_dict(), indent=2), encoding="utf-8"
            )
        except OSError:
            logger.warning("Could not save license cache to %s", self._cache_path)

    def _load_cache_or_default(self) -> LicenseInfo:
        """Load cached license info, or return a default if expired/missing."""
        try:
            if self._cache_path.exists():
                data: dict[str, Any] | None = None
                try:
                    from cutctx.security.state_crypto import read_hmac_json

                    hmac_payload = read_hmac_json(self._cache_path)
                    if isinstance(hmac_payload, dict):
                        data = hmac_payload
                except Exception:
                    data = None
                if data is None:
                    raw = json.loads(self._cache_path.read_text(encoding="utf-8"))
                    if isinstance(raw, dict):
                        data = raw
                if not isinstance(data, dict):
                    raise ValueError("license cache is not an object")
                cached = LicenseInfo.from_dict(data)
                age = (datetime.now(timezone.utc) - cached.validated_at).total_seconds()
                if age < GRACE_PERIOD_SECONDS and cached.status in ("active", "trial"):
                    logger.info(
                        "Using cached license (age=%.1fh, status=%s, plan=%s)",
                        age / 3600,
                        cached.status,
                        cached.plan,
                    )
                    self._license_info = cached
                    return cached
                if age < GRACE_PERIOD_SECONDS:
                    logger.warning(
                        "Cached license status is '%s'; not applying entitlements",
                        cached.status,
                    )
                else:
                    logger.warning(
                        "Cached license expired (age=%.1fd), marking as expired",
                        age / 86400,
                    )
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            logger.warning("Could not read license cache", exc_info=True)

        # No valid cache — return expired but still allow proxy to work
        self._license_info = LicenseInfo(status="expired")
        return self._license_info
