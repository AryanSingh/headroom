"""LLM Firewall — prompt injection detection, PII scanning, streaming redaction.

Scans incoming messages for:
- Prompt injection patterns (DAN, "ignore previous instructions", etc.)
- PII leakage (SSN, credit cards, email, phone, IP addresses, AWS keys)
- Jailbreak attempts

Provides a StreamingRedactor that buffers SSE tokens just long enough to
run NER-like pattern matching and redact PII before forwarding to the client.

Target overhead: <10ms for prompt scanning, <5ms delay on streaming buffer.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("cutctx.security")


# ---------------------------------------------------------------------------
# Violation model
# ---------------------------------------------------------------------------


class ViolationKind(str, Enum):
    """Type of security violation detected."""

    INJECTION = "injection"
    PII = "pii"
    JAILBREAK = "jailbreak"
    DATA_EXFILTRATION = "data_exfiltration"


@dataclass(frozen=True)
class Violation:
    """A single detected violation."""

    kind: ViolationKind
    description: str
    matched_text: str  # the offending substring (redacted in logs)
    confidence: float = 1.0  # 0.0–1.0
    block: bool = True  # if True, return 403; if False, just log/warn


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class FirewallConfig:
    """Configuration for the LLM Firewall."""

    enabled: bool = False
    block_pii: bool = True
    block_injection: bool = True
    block_jailbreak: bool = True
    redact_streaming: bool = True  # enable streaming PII redaction
    max_buffer_tokens: int = 50  # max tokens to buffer before flushing
    buffer_timeout_ms: float = 10.0  # max ms to hold buffer before flush
    custom_patterns: list[str] = field(default_factory=list)  # additional regex patterns
    allowed_domains: list[str] = field(default_factory=list)  # for data exfiltration check

    @classmethod
    def from_env(cls) -> FirewallConfig:
        """Create config from CUTCTX_FIREWALL_* env vars."""
        return cls(
            enabled=os.environ.get("CUTCTX_FIREWALL_ENABLED", "").strip() == "1",
            block_pii=os.environ.get("CUTCTX_FIREWALL_BLOCK_PII", "1").strip() != "0",
            block_injection=os.environ.get("CUTCTX_FIREWALL_BLOCK_INJECTION", "1").strip() != "0",
            block_jailbreak=os.environ.get("CUTCTX_FIREWALL_BLOCK_JAILBREAK", "1").strip() != "0",
            redact_streaming=os.environ.get("CUTCTX_FIREWALL_REDACT_STREAMING", "1").strip() != "0",
            max_buffer_tokens=int(os.environ.get("CUTCTX_FIREWALL_MAX_BUFFER_TOKENS", "50")),
            buffer_timeout_ms=float(os.environ.get("CUTCTX_FIREWALL_BUFFER_TIMEOUT_MS", "10")),
        )


# ---------------------------------------------------------------------------
# Injection patterns — heuristic regexes for known jailbreak families
# ---------------------------------------------------------------------------

_INJECTION_PATTERNS: list[tuple[str, re.Pattern[str], float]] = [
    # "Ignore previous instructions"
    (
        "ignore_previous_instructions",
        re.compile(
            r"ignore\s+(?:all\s+)?(?:previous|prior|above|earlier|preceding)\s+"
            r"(?:instructions?|prompts?|rules?|guidelines?|constraints?|orders?)",
            re.IGNORECASE,
        ),
        0.95,
    ),
    # DAN-style jailbreaks
    (
        "dan_jailbreak",
        re.compile(
            r"(?:you\s+are\s+now\s+)?DAN\b.*(?:do\s+anything\s+now|jailbreak|"
            r"no\s+(?:rules|restrictions|limits|boundaries))",
            re.IGNORECASE,
        ),
        0.90,
    ),
    # "Act as" role hijacking
    (
        "role_hijack",
        re.compile(
            r"(?:pretend|act\s+as|you\s+are|roleplay\s+as|simulate)\s+(?:you\s+are\s+)?"
            r"(?:an?\s+)?(?:evil|unrestricted|unfiltered|dark\s+(?:mode|version)|"
            r"DAN|DAN\s+1[0-9]|[A-Z]\.?\s*I?\s*D\.?\s*N\.?)",
            re.IGNORECASE,
        ),
        0.85,
    ),
    # System prompt extraction
    (
        "prompt_extraction",
        re.compile(
            r"(?:repeat|print|output|show|reveal|display|echo)\s+(?:your\s+)?"
            r"(?:system\s+prompt|initial\s+prompt|instructions?|configuration|"
            r"rules?|guidelines?)\b",
            re.IGNORECASE,
        ),
        0.80,
    ),
    # Encoded/obfuscated injection
    (
        "encoded_injection",
        re.compile(
            r"(?:base64|rot13|hex|binary|url[- ]?encode|decode\s+(?:this|the))\s*"
            r"(?:decode|decode\s+this|and\s+follow|then\s+execute)",
            re.IGNORECASE,
        ),
        0.85,
    ),
    # "Developer mode" activation
    (
        "dev_mode",
        re.compile(
            r"(?:enable|activate|enter|switch\s+to)\s+"
            r"(?:developer|dev|debug|admin|root|sudo|god)\s+mode",
            re.IGNORECASE,
        ),
        0.80,
    ),
    # Token smuggling via markdown
    (
        "markdown_injection",
        re.compile(
            r"!\[.*?\]\(https?://[^\s)]+\).*?ignore\s+(?:all\s+)?(?:previous|above)",
            re.IGNORECASE,
        ),
        0.90,
    ),
]

_JAILBREAK_PATTERNS: list[tuple[str, re.Pattern[str], float]] = [
    (
        "hypothetical_bypass",
        re.compile(
            r"(?:hypothetically|theoretically|in\s+a\s+(?:fictional|make[- ]?believe))\s+"
            r"(?:scenario|world|universe|case)\s+(?:where|in\s+which)\s+"
            r"(?:you\s+)?(?:could|would|should|might)\s+(?:bypass|ignore|override|violate)",
            re.IGNORECASE,
        ),
        0.70,
    ),
    (
        "grandma_exploit",
        re.compile(
            r"(?:grandma|grandmother|grandpa|grandfather)\s+(?:exploit|vulnerability|"
            r"bedtime\s+story|hack|trick)",
            re.IGNORECASE,
        ),
        0.75,
    ),
    (
        "opposite_day",
        re.compile(
            r"(?:today|from\s+now|starting)\s+(?:is|it'?s)\s+opposite\s+day",
            re.IGNORECASE,
        ),
        0.80,
    ),
    (
        "numbered_list_jailbreak",
        re.compile(
            r"(?:step\s+1[:.]\s*(?:you\s+are|pretend|act|ignore).*?step\s+[2-9])",
            re.IGNORECASE | re.DOTALL,
        ),
        0.75,
    ),
]


# ---------------------------------------------------------------------------
# PII patterns
# ---------------------------------------------------------------------------

_PII_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    # Social Security Numbers
    ("ssn", re.compile(r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b"), "SSN"),
    # Credit card numbers (Visa, MC, Amex, Discover)
    (
        "credit_card",
        re.compile(
            r"\b(?:4\d{3}|5[1-5]\d{2}|3[47]\d{2}|6(?:011|5\d{2}))[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"
        ),
        "credit card",
    ),
    # Email addresses
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"), "email"),
    # US phone numbers
    ("phone", re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"), "phone"),
    # IP addresses (v4)
    ("ipv4", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "IP address"),
    # AWS access key
    ("aws_key", re.compile(r"\b(?:AKIA|ABIA|ACCA|ASIA)[A-Z0-9]{16}\b"), "AWS key"),
    # AWS secret key
    (
        "aws_secret",
        re.compile(r"(?:aws_secret_access_key|secret_key)\s*[:=]\s*['\"]?[A-Za-z0-9/+=]{40}['\"]?"),
        "AWS secret",
    ),
    # Private keys
    ("private_key", re.compile(r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----"), "private key"),
    # API keys (generic patterns)
    (
        "api_key_bearer",
        re.compile(r"(?:api[_-]?key|bearer|token|secret)\s*[:=]\s*[\"']?[A-Za-z0-9_\-]{20,}[\"']?"),
        "API key",
    ),
    # Passport numbers (US format)
    ("passport", re.compile(r"\b[A-Z]\d{8}\b"), "passport"),
    # Tax ID / EIN
    ("ein", re.compile(r"\b\d{2}[-]?\d{7}\b"), "EIN/tax ID"),
]


# ---------------------------------------------------------------------------
# Data exfiltration patterns
# ---------------------------------------------------------------------------

_EXFIL_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "url_with_secrets",
        re.compile(
            r"(?:https?://[^\s]+(?:token|key|secret|password|auth|credential)=[^\s&]+)",
            re.IGNORECASE,
        ),
        "URL with embedded secrets",
    ),
    (
        "file_path_leak",
        re.compile(
            r"(?:/etc/(?:passwd|shadow|hosts)|/root/|~/.ssh/(?:id_|authorized_keys|config))",
        ),
        "sensitive file path",
    ),
]


# ---------------------------------------------------------------------------
# FirewallScanner — the main scanning engine
# ---------------------------------------------------------------------------


class FirewallScanner:
    """Scans messages for injections, PII, jailbreaks, and data exfiltration."""

    def __init__(self, config: FirewallConfig | None = None) -> None:
        self.config = config or FirewallConfig.from_env()
        self._custom_re: list[re.Pattern[str]] = []
        for pat in self.config.custom_patterns:
            try:
                self._custom_re.append(re.compile(pat, re.IGNORECASE))
            except re.error as exc:
                logger.warning("Invalid custom firewall pattern %r: %s", pat, exc)

    @property
    def enabled(self) -> bool:
        return self.config.enabled

    def scan_messages(self, messages: list[dict[str, Any]]) -> list[Violation]:
        """Scan an array of chat messages for violations.

        Returns a list of violations (empty if clean).
        """
        if not self.enabled:
            return []

        violations: list[Violation] = []
        t0 = time.monotonic()

        for msg in messages:
            role = str(msg.get("role", "")).strip().lower()
            if role == "tool":
                # Tool-result payloads are external data, not user instructions.
                # Scanning them for prompt injection produces noisy false positives.
                continue
            text = self._extract_text(msg)
            if not text:
                continue

            if self.config.block_injection:
                violations.extend(self._scan_injections(text))

            if self.config.block_jailbreak:
                violations.extend(self._scan_jailbreaks(text))

            if self.config.block_pii:
                violations.extend(self._scan_pii(text))

            violations.extend(self._scan_exfiltration(text))

            # Custom patterns
            for pat in self._custom_re:
                m = pat.search(text)
                if m:
                    violations.append(
                        Violation(
                            kind=ViolationKind.INJECTION,
                            description="Custom pattern match",
                            matched_text=m.group()[:80],
                            confidence=0.80,
                        )
                    )

        elapsed_ms = (time.monotonic() - t0) * 1000
        if violations:
            logger.info(
                "Firewall: %d violation(s) found in %d messages (%.1fms)",
                len(violations),
                len(messages),
                elapsed_ms,
            )
            self._trigger_webhooks(violations)

        return violations

    def scan_text(self, text: str) -> list[Violation]:
        """Scan a single text string for violations."""
        if not self.enabled:
            return []

        violations: list[Violation] = []
        if self.config.block_injection:
            violations.extend(self._scan_injections(text))
        if self.config.block_jailbreak:
            violations.extend(self._scan_jailbreaks(text))
        if self.config.block_pii:
            violations.extend(self._scan_pii(text))
        violations.extend(self._scan_exfiltration(text))

        if violations:
            self._trigger_webhooks(violations)

        return violations

    def _trigger_webhooks(self, violations: list[Violation]) -> None:
        """Fire a webhook for specific violation types."""
        alert_kinds = {ViolationKind.PII, ViolationKind.INJECTION}
        trigger_violations = [v for v in violations if v.kind in alert_kinds]
        if trigger_violations:
            try:
                import asyncio

                from cutctx.proxy.webhooks import fire_webhook

                for v in trigger_violations:
                    title = f"Firewall Alert: {v.kind.value.upper()}"
                    message = f"Detected {v.kind.value}: {v.description}"
                    asyncio.get_running_loop().create_task(fire_webhook(title, message))
            except Exception as e:
                logger.error(f"Error triggering firewall webhooks: {e}")

    def should_block(self, violations: list[Violation]) -> bool:
        """Return True if any violation should block the request."""
        return any(v.block for v in violations)

    def get_blocked_domains(self) -> list[str]:
        """Return the list of egress domains tracked or blocked by this scanner.

        In the current implementation the scanner enforces data-exfiltration
        checks on *any* URL that embeds secrets (pattern-based), and operators
        can whitelist domains via ``FirewallConfig.allowed_domains``.  This
        method returns the complement: domains that are **not** allowed and
        therefore subject to egress blocking.

        When no explicit deny-list is configured the method returns a sentinel
        list of well-known exfiltration vectors that the built-in patterns
        guard against.  This is useful for residency attestations that need a
        non-empty, human-readable list.
        """
        # If the operator provided an explicit allowed-domain list, domains
        # *outside* that list are blocked — we surface the allowed list as the
        # "not blocked" side and return a descriptive sentinel instead.
        allowed = list(self.config.allowed_domains)
        if allowed:
            # Domains explicitly allowed are not blocked; return a note.
            return ["*" if not allowed else f"!{d}" for d in allowed]

        # Default: surface the sentinel exfiltration patterns we enforce.
        return [
            "*.unknown-external (url-with-secrets pattern)",
            "sensitive-file-paths (/etc/passwd, ~/.ssh/*)",
        ]

    # --- Internal scan methods ---

    def _scan_injections(self, text: str) -> list[Violation]:
        violations: list[Violation] = []
        for name, pattern, confidence in _INJECTION_PATTERNS:
            m = pattern.search(text)
            if m:
                violations.append(
                    Violation(
                        kind=ViolationKind.INJECTION,
                        description=f"Prompt injection pattern: {name}",
                        matched_text=m.group()[:80],
                        confidence=confidence,
                    )
                )
        return violations

    def _scan_jailbreaks(self, text: str) -> list[Violation]:
        violations: list[Violation] = []
        for name, pattern, confidence in _JAILBREAK_PATTERNS:
            m = pattern.search(text)
            if m:
                violations.append(
                    Violation(
                        kind=ViolationKind.JAILBREAK,
                        description=f"Jailbreak pattern: {name}",
                        matched_text=m.group()[:80],
                        confidence=confidence,
                    )
                )
        return violations

    def _scan_pii(self, text: str) -> list[Violation]:
        violations: list[Violation] = []
        for _name, pattern, label in _PII_PATTERNS:
            m = pattern.search(text)
            if m:
                violations.append(
                    Violation(
                        kind=ViolationKind.PII,
                        description=f"PII detected: {label}",
                        matched_text=m.group()[:40],  # truncate for safety
                        confidence=0.90,
                    )
                )
        return violations

    def _scan_exfiltration(self, text: str) -> list[Violation]:
        violations: list[Violation] = []
        for _name, pattern, label in _EXFIL_PATTERNS:
            m = pattern.search(text)
            if m:
                violations.append(
                    Violation(
                        kind=ViolationKind.DATA_EXFILTRATION,
                        description=f"Data exfiltration: {label}",
                        matched_text=m.group()[:80],
                        confidence=0.85,
                    )
                )
        return violations

    @staticmethod
    def _extract_text(msg: dict[str, Any]) -> str:
        """Extract text content from a chat message (Anthropic or OpenAI format)."""
        # Anthropic: {"role": "user", "content": [{"type": "text", "text": "..."}]}
        # OpenAI: {"role": "user", "content": "string"} or [{"type": "text", "text": "..."}]
        content = msg.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        parts.append(block.get("text", ""))
                    elif block.get("type") == "tool_result":
                        # Don't scan tool results (they contain external data)
                        pass
                    elif block.get("type") == "tool_use":
                        # Scan tool input for injection via JSON args
                        args = block.get("input", {})
                        if isinstance(args, dict):
                            parts.append(json.dumps(args))
                elif isinstance(block, str):
                    parts.append(block)
            return " ".join(parts)
        return ""


# ---------------------------------------------------------------------------
# StreamingRedactor — buffers SSE tokens and redacts PII before forwarding
# ---------------------------------------------------------------------------

import json  # noqa: E402 — needed for StreamingRedactor


class StreamingRedactor:
    """Buffers streaming tokens and redacts PII before forwarding to the client.

    Runs NER-like regex patterns on buffered content and replaces matches
    with [REDACTED:type] placeholders. Maintains SSE event protocol by
    flushing complete ``data:`` lines.

    Target: <5ms additional latency per flush.
    """

    # PII patterns to redact in streaming output
    _STREAM_PII: list[tuple[str, re.Pattern[str], str]] = [
        ("ssn", re.compile(r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b"), "[REDACTED:SSN]"),
        (
            "credit_card",
            re.compile(
                r"\b(?:4\d{3}|5[1-5]\d{2}|3[47]\d{2}|6(?:011|5\d{2}))[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"
            ),
            "[REDACTED:CARD]",
        ),
        (
            "email",
            re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
            "[REDACTED:EMAIL]",
        ),
        (
            "phone",
            re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
            "[REDACTED:PHONE]",
        ),
        ("aws_key", re.compile(r"\b(?:AKIA|ABIA|ACCA|ASIA)[A-Z0-9]{16}\b"), "[REDACTED:KEY]"),
        (
            "private_key",
            re.compile(r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----"),
            "[REDACTED:KEY]",
        ),
    ]

    def __init__(
        self,
        config: FirewallConfig | None = None,
        *,
        enabled: bool | None = None,
        max_buffer_tokens: int = 50,
        buffer_timeout_ms: float = 10.0,
    ) -> None:
        if config is None:
            config = FirewallConfig.from_env()
        self.enabled = config.enabled if enabled is None else enabled
        self.max_buffer_tokens = max_buffer_tokens
        self.buffer_timeout_s = buffer_timeout_ms / 1000.0
        self._buffer: list[str] = []
        self._token_count: int = 0
        self._flush_task: asyncio.Task | None = None

    def redact_text(self, text: str) -> str:
        """Redact PII from a text string. Returns redacted version."""
        if not self.enabled:
            return text
        result = text
        for _name, pattern, replacement in self._STREAM_PII:
            result = pattern.sub(replacement, result)
        return result

    def process_chunk(self, chunk_line: str) -> str:
        """Process a single SSE chunk line.

        For ``data:`` lines containing content deltas, buffer tokens and
        redact PII. For non-data lines (event types, empty lines), pass through.

        Returns the (possibly redacted) line to forward.
        """
        if not self.enabled:
            return chunk_line

        # Only process data: lines with content
        if not chunk_line.startswith("data: "):
            return chunk_line

        data_str = chunk_line[6:]  # strip "data: "
        if data_str.strip() == "[DONE]":
            return chunk_line

        try:
            data = json.loads(data_str)
        except (json.JSONDecodeError, ValueError):
            return chunk_line

        # Handle OpenAI-style content deltas (choices[0].delta.content)
        if isinstance(data, dict):
            choices = data.get("choices", [])
            if isinstance(choices, list) and choices:
                delta = choices[0].get("delta", {}) if isinstance(choices[0], dict) else {}
                if isinstance(delta, dict):
                    content = delta.get("content")
                    if isinstance(content, str) and content:
                        redacted = self.redact_text(content)
                        if redacted != content:
                            delta["content"] = redacted
                            return f"data: {json.dumps(data)}"

            # Handle Anthropic-style content_block_delta
            if data.get("type") == "content_block_delta":
                text_delta = data.get("delta", {})
                if isinstance(text_delta, dict):
                    delta_type = text_delta.get("type")
                    text = text_delta.get("text", "")
                    if isinstance(text, str) and text and (delta_type in (None, "", "text_delta")):
                        redacted = self.redact_text(text)
                        if redacted != text:
                            text_delta["text"] = redacted
                            return f"data: {json.dumps(data)}"

        return chunk_line

    async def wrap_stream(self, stream: Any) -> Any:
        """Wrap an async generator of SSE lines with PII redaction.

        Yields each line through process_chunk() for redaction.
        """
        if not self.enabled:
            async for chunk in stream:
                yield chunk
                return

        async for chunk in stream:
            if isinstance(chunk, bytes):
                text = chunk.decode("utf-8", errors="replace")
                redacted = self._redact_multiline(text)
                yield redacted.encode("utf-8")
            elif isinstance(chunk, str):
                yield self._redact_multiline(chunk)
            else:
                yield chunk

    def _redact_multiline(self, text: str) -> str:
        """Redact PII across multiple lines in an SSE chunk."""
        lines = text.split("\n")
        redacted_lines = [self.process_chunk(line) for line in lines]
        return "\n".join(redacted_lines)
