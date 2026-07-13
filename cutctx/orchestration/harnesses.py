"""Public compatibility contracts for coding-harness adapters."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum


class SupportLevel(str, Enum):
    NATIVE = "native"
    CONFIGURED = "configured"
    GATEWAY_MEDIATED = "gateway_mediated"
    EXPERIMENTAL = "experimental"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class HarnessCompatibility:
    id: str
    support_level: SupportLevel
    routing: bool
    artifact_handoffs: bool
    hidden_session_sharing: bool
    notes: str


_COMPATIBILITY = (
    HarnessCompatibility(
        id="codex",
        support_level=SupportLevel.NATIVE,
        routing=True,
        artifact_handoffs=True,
        hidden_session_sharing=False,
        notes="Use native adapter/proxy paths; preserve Codex-specific execution semantics.",
    ),
    HarnessCompatibility(
        id="claude_code",
        support_level=SupportLevel.NATIVE,
        routing=True,
        artifact_handoffs=True,
        hidden_session_sharing=False,
        notes="Use native adapter/MCP paths; preserve Anthropic-specific tool semantics.",
    ),
    HarnessCompatibility(
        id="opencode",
        support_level=SupportLevel.CONFIGURED,
        routing=True,
        artifact_handoffs=True,
        hidden_session_sharing=False,
        notes="Provider/plugin configuration supports explicit task artifacts.",
    ),
)


def compatibility_manifest() -> dict[str, object]:
    return {"manifest_version": 1, "harnesses": [asdict(item) for item in _COMPATIBILITY]}


__all__ = ["HarnessCompatibility", "SupportLevel", "compatibility_manifest"]
