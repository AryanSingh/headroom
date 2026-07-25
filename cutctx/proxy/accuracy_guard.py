"""Log fidelity verification for accuracy guard.

Implements the CUTCTX_ACCURACY_GUARD feature: verifies that no line at
ERROR severity or above is silently lost during compression.

Modes:
  - ``off``: No checking, zero overhead.
  - ``balanced``: Check; log WARNING on violation, continue with compressed.
  - ``strict``: Check; on violation return ORIGINAL, log WARNING.

Design: pure, unit-testable function + integrator hook in ContentRouter.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger("cutctx.proxy.accuracy_guard")


class LogFidelityViolation:
    """Tracks a fidelity violation with context for logging."""

    def __init__(self, violation_type: str, details: str):
        self.violation_type = violation_type
        self.details = details

    def __repr__(self) -> str:
        return f"LogFidelityViolation(type={self.violation_type}, details={self.details!r})"


def verify_log_fidelity(original: str, compressed: str) -> list[LogFidelityViolation]:
    """Check that no ERROR+ line is silently lost during compression.

    A line is considered "silently lost" if it appears in the original at
    ERROR severity or above, but:
    1. Does NOT appear in the compressed output, AND
    2. Is NOT disclosed by the omission marker's ERROR/FATAL/FAIL counts.

    Pure function: no side effects, unit-testable, and cheap (single pass).
    Runs on the request path so performance is critical.

    Parameters
    ----------
    original
        The original uncompressed log content.
    compressed
        The compressed output.

    Returns
    -------
    list[LogFidelityViolation]
        Empty list if fidelity is maintained. Non-empty list (violations)
        if ERROR+ lines are unaccounted for.
    """
    if not original:
        # No original content to check; no violation possible
        return []

    # Extract all ERROR/FATAL/FAIL lines from original, preserving indices.
    original_high_severity_lines = _extract_high_severity_lines(original)
    if not original_high_severity_lines:
        return []

    # Check if they appear in compressed output.
    high_severity_in_compressed = _extract_high_severity_lines(compressed)
    high_severity_compressed_set = {line.strip() for line in high_severity_in_compressed}

    # Parse the omission marker to see how many ERROR+ lines were declared lost.
    omission_counts = _parse_omission_marker(compressed)

    violations: list[LogFidelityViolation] = []

    for original_line in original_high_severity_lines:
        if original_line.strip() in high_severity_compressed_set:
            # Line is present in compressed output — OK.
            continue

        # Line is not in compressed output. Check if omission marker discloses it.
        # The marker reports counts of omitted lines by level: "count FATAL", "count ERROR", etc.
        # If the marker says ≥1 ERROR/FATAL/FAIL were omitted, we trust the marker's disclosure.
        # If the marker says 0 of each, but we found a missing line, that's a violation.

        if (
            omission_counts["fatal"] > 0
            or omission_counts["error"] > 0
            or omission_counts["fail"] > 0
        ):
            # The marker discloses the loss; not a violation.
            continue

        # Line is missing and not disclosed by the marker.
        violation = LogFidelityViolation(
            violation_type="missing_high_severity_line",
            details=original_line[:100],  # Truncate for logging
        )
        violations.append(violation)

    return violations


def _extract_high_severity_lines(content: str) -> list[str]:
    """Extract lines at ERROR, FATAL, FAIL severity from log content.

    Uses aho-corasick-like keyword matching (word boundary + case variants).
    Mirrors the Rust and Python log compressor's classification.

    Parameters
    ----------
    content
        The log content to scan.

    Returns
    -------
    list[str]
        Lines containing FATAL/CRITICAL, ERROR, or FAIL keywords.
    """
    # Patterns for each severity level. FATAL checked first (highest priority).
    # Mirrors cutctx/transforms/log_compressor.py::_parse_lines
    fatal_pattern = re.compile(r"\b(?:FATAL|fatal|Fatal|CRITICAL|critical|Critical)\b")
    error_pattern = re.compile(r"\b(?:ERROR|error|Error)\b")
    fail_pattern = re.compile(r"\b(?:FAIL|FAILED|fail|failed|Fail|Failed)\b")

    lines = content.splitlines()
    high_severity: list[str] = []

    for line in lines:
        # Check in priority order; first match wins (FATAL > ERROR > FAIL).
        if fatal_pattern.search(line):
            high_severity.append(line)
        elif error_pattern.search(line):
            high_severity.append(line)
        elif fail_pattern.search(line):
            high_severity.append(line)

    return high_severity


def _parse_omission_marker(compressed: str) -> dict[str, int]:
    """Extract counts from the omission marker.

    The marker format (from log_compressor.py) is:
        [N lines omitted: count1 LEVEL1, count2 LEVEL2, ...]

    where LEVEL is one of: FATAL, ERROR, FAIL, WARN, INFO, DEBUG, TRACE, OTHER.

    The marker is NOT necessarily the last line. When CCR is active the
    compressor appends a retrieval line after it, e.g.::

        [1142 lines omitted: 211 ERROR, 200 WARN, 709 INFO, 22 DEBUG]
        [1201 lines compressed to 33. Retrieve more: hash=601157cc…]

    Anchoring the match to end-of-output therefore finds nothing, leaves every
    count at zero, and makes correctly-disclosed omissions look undisclosed —
    which reported hundreds of spurious violations per payload and, in strict
    mode, would have forced uncompressed forwarding on essentially every log
    request. The marker is matched anywhere, taking the last occurrence.

    Parameters
    ----------
    compressed
        The compressed output, which may contain an omission marker.

    Returns
    -------
    dict[str, int]
        Counts keyed by level name (lowercased). All keys present.
        Defaults to 0 for missing levels.
    """
    counts = {
        "fatal": 0,
        "error": 0,
        "fail": 0,
        "warn": 0,
        "info": 0,
        "debug": 0,
        "trace": 0,
        "other": 0,
    }

    # Match the marker on its own line anywhere in the output, and take the
    # last one if somehow repeated. Anchoring to EOF is wrong — see docstring.
    matches = re.findall(r"^\[\d+ lines omitted: (.+?)\]\s*$", compressed, flags=re.MULTILINE)
    if not matches:
        return counts

    marker_content = matches[-1]
    # Format: "1 FATAL, 2 ERROR, 3 FAIL, ..."
    # Parse each "count LEVEL" pair.
    for part in marker_content.split(","):
        part = part.strip()
        tokens = part.split()
        if len(tokens) >= 2:
            try:
                count = int(tokens[0])
                level = tokens[1].lower()
                if level in counts:
                    counts[level] = count
            except (ValueError, IndexError):
                # Malformed marker; skip.
                pass

    return counts


def resolve_accuracy_guard_mode(config_value: str | None, env_var: str | None) -> str:
    """Resolve the accuracy guard mode from config and env var.

    Precedence: env_var > config_value > default ("off").

    Parameters
    ----------
    config_value
        Value from ProxyConfig.accuracy_guard.
    env_var
        Value from CUTCTX_ACCURACY_GUARD environment variable.

    Returns
    -------
    str
        One of: "off", "balanced", "strict".
    """
    # Env var takes precedence over config.
    mode = (env_var or config_value or "off").lower().strip()

    # Validate and normalize.
    if mode not in ("off", "balanced", "strict"):
        logger.warning(
            "Invalid accuracy_guard mode %r; defaulting to 'off'",
            mode,
        )
        return "off"

    return mode


def apply_accuracy_guard(
    original: str,
    compressed: str,
    mode: str,
) -> str:
    """Apply accuracy guard to a compression result.

    Parameters
    ----------
    original
        The original uncompressed content.
    compressed
        The compressed content.
    mode
        One of: "off", "balanced", "strict".

    Returns
    -------
    str
        The payload to use downstream. Either compressed (modes "off" and
        "balanced") or original (mode "strict" on violation).
    """
    if mode == "off":
        return compressed

    violations = verify_log_fidelity(original, compressed)

    if not violations:
        return compressed

    # Violation detected. Log it.
    violation_summary = "; ".join(v.details for v in violations)
    logger.warning(
        "Accuracy guard violation (%s mode): %s",
        mode,
        violation_summary,
    )

    if mode == "strict":
        logger.info("Returning original payload instead of compressed (strict mode)")
        return original

    # balanced mode: continue with compressed
    return compressed


__all__ = [
    "apply_accuracy_guard",
    "LogFidelityViolation",
    "resolve_accuracy_guard_mode",
    "verify_log_fidelity",
]
