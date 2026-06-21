# SPDX-License-Identifier: LicenseRef-Headroom-Commercial
# Copyright (c) 2025-2026 Cutctx Labs.

"""SP-6: Server-side abuse detection (privacy-respecting).

Detects shared-key abuse, impossible travel, seat overuse, and activation
storms from activation/heartbeat metadata only — never inspects prompt content.

All detection is advisory: flags generate alerts but require admin action
to revoke. This avoids false-positive lockouts from legitimate use cases
(IP changes, corporate proxies, travel).
"""

import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class AbuseFlag(str, Enum):
    """Types of abuse that can be detected."""
    IMPOSSIBLE_TRAVEL = "impossible_travel"
    TOO_MANY_FINGERPRINTS = "too_many_fingerprints"
    TOO_MANY_IPS = "too_many_ips"
    ACTIVATION_STORM = "activation_storm"
    SEAT_OVERUSE = "seat_overuse"


class Severity(str, Enum):
    """Severity of detected abuse."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AbuseAlert:
    """An abuse detection alert."""
    lic_id: str
    flag: AbuseFlag
    severity: Severity
    description: str
    detected_at: float = field(default_factory=time.time)
    fingerprint: Optional[str] = None
    ip_address: Optional[str] = None
    geo: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "lic_id": self.lic_id,
            "flag": self.flag.value,
            "severity": self.severity.value,
            "description": self.description,
            "detected_at": self.detected_at,
            "fingerprint": self.fingerprint,
            "ip_address": self.ip_address,
            "geo": self.geo,
        }


@dataclass
class ActivationRecord:
    """A single activation or heartbeat event for analysis."""
    lic_id: str
    fingerprint: str
    ip_address: str
    geo: Optional[str] = None  # Country/region code (e.g., "US", "EU")
    timestamp: float = field(default_factory=time.time)
    event_type: str = "heartbeat"  # "activation" or "heartbeat"


# --- Configuration thresholds (conservative defaults) ---

# Maximum distinct fingerprints per license before flagging
MAX_FINGERPRINTS_PER_LICENSE = 5

# Maximum distinct IP addresses per license within the detection window
MAX_IPS_PER_LICENSE = 10

# Maximum activations per license within this window (seconds)
ACTIVATION_STORM_WINDOW_SECS = 3600  # 1 hour
ACTIVATION_STORM_MAX_COUNT = 10

# Impossible travel: minimum distance (km) to flag
IMPOSSIBLE_TRAVEL_MIN_KM = 500

# Impossible travel: maximum time between events (seconds) to flag
IMPOSSIBLE_TRAVEL_MAX_SECS = 600  # 10 minutes

# Geo coordinates for common regions (approximate centers)
GEO_COORDS: dict[str, tuple[float, float]] = {
    "US": (39.8, -98.6),
    "EU": (50.1, 10.5),
    "APAC": (30.0, 105.0),
    "LATAM": (-15.0, -55.0),
    "AF": (2.0, 22.0),
    "MEA": (25.0, 45.0),
}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute distance between two lat/lon points using the haversine formula."""
    R = 6371.0  # Earth radius in km
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return R * c


class AbuseDetector:
    """Server-side abuse detection engine.

    Processes activation/heartbeat events and flags suspicious patterns.
    All analysis is on metadata only (fingerprint, IP, geo, timestamp).
    """

    def __init__(
        self,
        max_fingerprints: int = MAX_FINGERPRINTS_PER_LICENSE,
        max_ips: int = MAX_IPS_PER_LICENSE,
        storm_window_secs: int = ACTIVATION_STORM_WINDOW_SECS,
        storm_max_count: int = ACTIVATION_STORM_MAX_COUNT,
    ):
        self.max_fingerprints = max_fingerprints
        self.max_ips = max_ips
        self.storm_window_secs = storm_window_secs
        self.storm_max_count = storm_max_count
        # Per-license event history: lic_id -> list of records
        self._events: dict[str, list[ActivationRecord]] = defaultdict(list)
        # Generated alerts
        self._alerts: list[AbuseAlert] = []

    def process_event(self, record: ActivationRecord) -> list[AbuseAlert]:
        """Process a single activation/heartbeat event and return any alerts."""
        self._events[record.lic_id].append(record)
        alerts: list[AbuseAlert] = []

        # Check impossible travel
        alert = self._check_impossible_travel(record)
        if alert:
            alerts.append(alert)

        # Check too many fingerprints
        alert = self._check_fingerprint_count(record)
        if alert:
            alerts.append(alert)

        # Check too many IPs
        alert = self._check_ip_count(record)
        if alert:
            alerts.append(alert)

        # Check activation storm
        alert = self._check_activation_storm(record)
        if alert:
            alerts.append(alert)

        self._alerts.extend(alerts)
        return alerts

    def _check_impossible_travel(self, record: ActivationRecord) -> Optional[AbuseAlert]:
        """Detect impossible travel: same key from distant geos within minutes."""
        if not record.geo:
            return None

        recent_cutoff = record.timestamp - IMPOSSIBLE_TRAVEL_MAX_SECS
        recent_events = [
            e for e in self._events[record.lic_id]
            if e.timestamp >= recent_cutoff
            and e.geo
            and e.fingerprint != record.fingerprint  # Different machine
        ]

        current_coords = GEO_COORDS.get(record.geo)
        if not current_coords:
            return None

        for event in recent_events:
            event_coords = GEO_COORDS.get(event.geo)
            if not event_coords:
                continue

            distance = _haversine_km(
                current_coords[0], current_coords[1],
                event_coords[0], event_coords[1],
            )
            time_diff = abs(record.timestamp - event.timestamp)

            if distance > IMPOSSIBLE_TRAVEL_MIN_KM and time_diff < IMPOSSIBLE_TRAVEL_MAX_SECS:
                speed_kmh = distance / (time_diff / 3600) if time_diff > 0 else float("inf")
                return AbuseAlert(
                    lic_id=record.lic_id,
                    flag=AbuseFlag.IMPOSSIBLE_TRAVEL,
                    severity=Severity.HIGH,
                    description=(
                        f"Impossible travel detected: {record.geo} ({distance:.0f}km from "
                        f"{event.geo}) within {time_diff:.0f}s (speed: {speed_kmh:.0f} km/h)"
                    ),
                    fingerprint=record.fingerprint,
                    ip_address=record.ip_address,
                    geo=record.geo,
                )

        return None

    def _check_fingerprint_count(self, record: ActivationRecord) -> Optional[AbuseAlert]:
        """Detect too many distinct fingerprints for one license."""
        fingerprints = set()
        for e in self._events[record.lic_id]:
            fingerprints.add(e.fingerprint)

        if len(fingerprints) > self.max_fingerprints:
            return AbuseAlert(
                lic_id=record.lic_id,
                flag=AbuseFlag.TOO_MANY_FINGERPRINTS,
                severity=Severity.MEDIUM,
                description=(
                    f"License has {len(fingerprints)} distinct fingerprints "
                    f"(limit: {self.max_fingerprints})"
                ),
                fingerprint=record.fingerprint,
                ip_address=record.ip_address,
            )
        return None

    def _check_ip_count(self, record: ActivationRecord) -> Optional[AbuseAlert]:
        """Detect too many distinct IPs for one license."""
        ips = set()
        for e in self._events[record.lic_id]:
            ips.add(e.ip_address)

        if len(ips) > self.max_ips:
            return AbuseAlert(
                lic_id=record.lic_id,
                flag=AbuseFlag.TOO_MANY_IPS,
                severity=Severity.MEDIUM,
                description=(
                    f"License has {len(ips)} distinct IP addresses "
                    f"(limit: {self.max_ips})"
                ),
                fingerprint=record.fingerprint,
                ip_address=record.ip_address,
            )
        return None

    def _check_activation_storm(self, record: ActivationRecord) -> Optional[AbuseAlert]:
        """Detect activation storms: too many activations in a short window."""
        if record.event_type != "activation":
            return None

        window_cutoff = record.timestamp - self.storm_window_secs
        recent_activations = [
            e for e in self._events[record.lic_id]
            if e.event_type == "activation" and e.timestamp >= window_cutoff
        ]

        if len(recent_activations) > self.storm_max_count:
            return AbuseAlert(
                lic_id=record.lic_id,
                flag=AbuseFlag.ACTIVATION_STORM,
                severity=Severity.HIGH,
                description=(
                    f"Activation storm: {len(recent_activations)} activations "
                    f"in {self.storm_window_secs}s window (limit: {self.storm_max_count})"
                ),
                fingerprint=record.fingerprint,
                ip_address=record.ip_address,
            )
        return None

    def get_alerts(
        self,
        lic_id: Optional[str] = None,
        min_severity: Optional[Severity] = None,
    ) -> list[AbuseAlert]:
        """Retrieve alerts, optionally filtered."""
        severity_order = {Severity.LOW: 0, Severity.MEDIUM: 1, Severity.HIGH: 2, Severity.CRITICAL: 3}
        alerts = self._alerts
        if lic_id:
            alerts = [a for a in alerts if a.lic_id == lic_id]
        if min_severity:
            min_ord = severity_order.get(min_severity, 0)
            alerts = [a for a in alerts if severity_order.get(a.severity, 0) >= min_ord]
        return alerts

    def get_event_count(self, lic_id: str) -> int:
        """Count events for a license."""
        return len(self._events.get(lic_id, []))

    def clear_history(self, lic_id: Optional[str] = None):
        """Clear event history (for testing or periodic cleanup)."""
        if lic_id:
            self._events.pop(lic_id, None)
        else:
            self._events.clear()
        self._alerts.clear()


def check_seat_overuse(
    current_seats: int,
    max_seats: int,
    lic_id: str,
) -> Optional[AbuseAlert]:
    """Check if seat count exceeds the license limit."""
    if current_seats > max_seats:
        return AbuseAlert(
            lic_id=lic_id,
            flag=AbuseFlag.SEAT_OVERUSE,
            severity=Severity.HIGH,
            description=(
                f"Seat overuse: {current_seats} active seats "
                f"(licensed for {max_seats})"
            ),
        )
    return None
