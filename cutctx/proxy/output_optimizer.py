# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs
"""WS10 Output-side optimization.

Per artifacts/savings-moat-expansion-specs.md WS10:
- Three independent levers, each its own sub-flag (default off within
  the master CUTCTX_OUTPUT_OPT=1 envelope):
  1. Diff-edit steering: when task type is CODE/EDIT, append a
     system-suffix instruction to emit minimal patches/edits.
     Never modify tool schemas. Skip entirely for non-code tasks.
  2. max_tokens auto-tuning: per-(task-type) response-length
     quantiles. If client sent no max_tokens or value > 4x p95,
     cap it. On a max_tokens-truncated finish, record a miss
     and raise the cap.
  3. Style shaping: for SEARCH/LIST/SUMMARIZE task types, inject
     a terse-output instruction. Skip for CODE/DEBUG.
- Safety rail: any guard failure or client retry within the same
  session disables levers 1 and 3 for that session (in-memory
  circuit breaker). Lever 2 (max_tokens) is NOT affected — it has
  no impact on quality.
- Attribution: estimated_tokens_saved reported on every decision;
  caller writes to the OUTPUT_OPTIMIZATION source. Label as
  estimated in the report.
- Default-off (the spec's flag-off golden contract): every
  optimize() call with the default config is a strict no-op that
  returns the input body BYTE-IDENTICAL.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


# Per spec: 'value > 4x p95 -> cap it.'
DEFAULT_MAXTOK_AUTO_MULTIPLIER = 4

# Per spec: 'p95 + 25% headroom.'
DEFAULT_OUTPUT_QUANTILE_PERCENTILE = 95

# 25% headroom (1.25) on the p-quantile.
DEFAULT_OUTPUT_HEADROOM = 0.25

# Default cap when the optimizer has no history for the task type.
# This is the "first request" cap — it should be conservative
# enough to avoid runaway output but generous enough to not break
# most prompts.
DEFAULT_OUTPUT_FIRST_CAP = 4096

# Maximum quantile window (per session, per task type). When full,
# the oldest entry is dropped (FIFO).
DEFAULT_QUANTILE_WINDOW = 50


# ---------------------------------------------------------------------------
# Public configuration
# ---------------------------------------------------------------------------


@dataclass
class OutputOptimizeConfig:
    """Configuration for the output-side optimizer.

    The master flag `enabled` defaults to False. When False, all
    three sub-flags are ignored and `optimize()` is a strict no-op
    that returns the input body BYTE-IDENTICAL.
    """

    enabled: bool = False
    enable_diff_edit: bool = False
    enable_maxtok_auto: bool = False
    enable_style: bool = False

    # Per-task-type quantile window (rolling). Smaller windows adapt
    # faster; larger windows are more stable. Default is 50.
    quantile_window: int = DEFAULT_QUANTILE_WINDOW

    # Per-session safety-rail circuit breaker half-life. Not used
    # in the spec (the breaker is sticky on guard-failure) but kept
    # for future expansion.
    safety_rail_ttl_seconds: int = 0  # 0 = sticky (no decay)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class OutputOptActions:
    """The set of actions the optimizer took on a single request.

    Each boolean is True if the lever was applied.
    """

    diff_edit: bool = False
    maxtok_cap: bool = False
    style_terse: bool = False

    @property
    def applied(self) -> list[str]:
        return [
            name
            for name, val in (
                ("diff_edit", self.diff_edit),
                ("maxtok_cap", self.maxtok_cap),
                ("style_terse", self.style_terse),
            )
            if val
        ]


@dataclass
class OutputOptimizeDecision:
    """The result of an optimize() call.

    - `request_body`: the post-lever body (a copy if the levers
      fired; the SAME OBJECT as the input if no lever fired and
      the flag is off — flag-off is byte-identical).
    - `actions_applied`: list of lever names that fired.
    - `estimated_tokens_saved`: rough estimate of output tokens
      avoided by the levers. Caller records this to the
      OUTPUT_OPTIMIZATION savings source.
    - `task_type`: the detected task type, or None if not detected.
    """

    request_body: Any
    actions_applied: list[str] = field(default_factory=list)
    estimated_tokens_saved: int = 0
    task_type: str | None = None

    @property
    def actions(self) -> OutputOptActions:
        return OutputOptActions(
            diff_edit="diff_edit" in self.actions_applied,
            maxtok_cap="maxtok_cap" in self.actions_applied,
            style_terse="style_terse" in self.actions_applied,
        )


# ---------------------------------------------------------------------------
# Stats (per session)
# ---------------------------------------------------------------------------


@dataclass
class OutputOptStats:
    """Per-session output-optimizer statistics.

    - `calls`: number of optimize() calls
    - `guard_failures`: number of times a guard failure was recorded
      (triggers the safety rail)
    - `client_retries`: number of times a client retry was recorded
      (triggers the safety rail)
    - `quantile_count`: number of outcome samples in the quantile
      window for the most recent task type (debug aid)
    - `truncations`: number of max_tokens-truncated finishes
      (drives lever 2 to raise the cap)
    - `safety_rail_active`: True if the safety rail is currently
      tripped for this session (levers 1 and 3 disabled)
    """

    calls: int = 0
    guard_failures: int = 0
    client_retries: int = 0
    quantile_count: int = 0
    truncations: int = 0
    safety_rail_active: bool = False


# ---------------------------------------------------------------------------
# Task type detection
# ---------------------------------------------------------------------------


# Order matters: code_edit before debug, search before summarize.
_TASK_TYPE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "code_edit",
        re.compile(
            r"\b(fix|edit|refactor|rewrite|patch|update|modify|change|implement)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "debug",
        re.compile(
            r"\b(debug|trace|investigate|diagnose|why is|why does|stack trace|exception|error)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "search",
        re.compile(
            r"\b(search|grep|ripgrep|find|where is|locate|which file)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "list",
        re.compile(
            r"\b(list|show me|enumerate|all (the )?files|all (the )?dirs|tree of)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "summarize",
        re.compile(
            r"\b(summarize|summary|recap|brief|tl;dr|overview|abstract)\b",
            re.IGNORECASE,
        ),
    ),
)


def detect_task_type(user_message: str) -> str:
    """Detect the task type from the user message.

    Per spec, the task type drives which levers fire:
    - code_edit -> lever 1 (diff-edit steering)
    - search / list / summarize -> lever 3 (style shaping)
    - debug / general -> neither 1 nor 3
    """
    if not isinstance(user_message, str):
        return "general"
    for task_type, pat in _TASK_TYPE_PATTERNS:
        if pat.search(user_message):
            return task_type
    return "general"


def should_inject_diff_edit(task_type: str) -> bool:
    """Per spec: lever 1 only fires for CODE/EDIT."""
    return task_type == "code_edit"


def should_inject_style(task_type: str) -> bool:
    """Per spec: lever 3 fires for SEARCH/LIST/SUMMARIZE; explicitly
    NOT for CODE/DEBUG."""
    return task_type in ("search", "list", "summarize")


# ---------------------------------------------------------------------------
# The optimizer
# ---------------------------------------------------------------------------


# The diff-edit instruction to append. Kept short and embedded as
# a system-suffix so it doesn't disturb the rest of the prompt.
_DIFF_EDIT_INSTRUCTION = (
    "\n\nWhen making code changes, prefer emitting minimal patches "
    "(search/replace diffs) over full-file rewrites when the tool "
    "surface allows. Be terse in your final message; explain only "
    "what changed and why."
)

# The terse-output instruction for SEARCH/LIST/SUMMARIZE.
_STYLE_TERSE_INSTRUCTION = (
    "\n\nBe terse: prefer minimal output. For lists, give one line "
    "per item. For summaries, give the most relevant fact first. "
    "No preamble."
)


def cap_max_tokens(
    quantile_tokens: list[int],
    percentile: int = DEFAULT_OUTPUT_QUANTILE_PERCENTILE,
    headroom: float = DEFAULT_OUTPUT_HEADROOM,
) -> int:
    """Compute a max_tokens cap from a window of historical output
    token counts. Returns ceil(quantile + headroom * quantile).

    With the spec's defaults: p95 + 25% headroom.
    """
    if not quantile_tokens:
        return DEFAULT_OUTPUT_FIRST_CAP
    # Compute the requested percentile (linear interpolation).
    sorted_tokens = sorted(quantile_tokens)
    n = len(sorted_tokens)
    if n == 1:
        return int(sorted_tokens[0] * (1 + headroom))
    # Position in [0, 1]
    pos = (percentile / 100.0) * (n - 1)
    lo = int(pos)
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    p_value = sorted_tokens[lo] * (1 - frac) + sorted_tokens[hi] * frac
    return int(p_value * (1 + headroom))


class OutputOptimizer:
    """Per-session output-side optimizer with safety rail.

    Usage:
        cfg = OutputOptimizeConfig(
            enabled=True, enable_diff_edit=True, enable_maxtok_auto=True
        )
        optimizer = OutputOptimizer(cfg)
        # Before each upstream call:
        decision = optimizer.optimize(request_body=body, session_id=...)
        if decision.actions_applied:
            # Use decision.request_body (a copy of body with levers applied)
            body = decision.request_body
        # After the upstream call returns:
        optimizer.record_outcome(session_id, task_type, output_tokens, finish_reason)
        # If a guard failure or client retry occurs:
        optimizer.record_guard_failure(session_id)
        optimizer.record_client_retry(session_id)

    Flag-off behavior: optimize() returns the SAME object reference
    and an empty actions_applied list.
    """

    def __init__(self, config: OutputOptimizeConfig | None = None) -> None:
        self.config = config or OutputOptimizeConfig()
        # Per-session state
        self._quantiles: dict[tuple[str, str], list[int]] = defaultdict(list)
        # session_id -> safety_rail_tripped
        self._safety_rail: set[str] = set()
        # session_id -> truncation count
        self._truncations: dict[str, int] = defaultdict(int)
        self._stats: dict[str, OutputOptStats] = {}

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def optimize(self, request_body: Any, session_id: str) -> OutputOptimizeDecision:
        """Apply the configured levers to the request body.

        Flag-off: returns the input BYTE-IDENTICAL (same object ref).
        Flag-on: may copy and modify the body.
        """
        if not self.config.enabled:
            return OutputOptimizeDecision(request_body=request_body)

        if not isinstance(request_body, dict):
            return OutputOptimizeDecision(request_body=request_body)

        self._bump_call(session_id)

        # Task type from the last user message
        task_type = self._detect_task_type_from_body(request_body)
        safety_rail_active = session_id in self._safety_rail

        actions = OutputOptActions()
        estimated_savings = 0

        # We may or may not modify the body; track whether a copy is
        # needed to avoid mutating the input.
        body = request_body
        mutated = False

        # Lever 1: diff-edit steering (CODE/EDIT only, not safety-rail)
        if (
            self.config.enable_diff_edit
            and not safety_rail_active
            and should_inject_diff_edit(task_type)
        ):
            body, saved = self._apply_diff_edit(body)
            actions.diff_edit = True
            estimated_savings += saved
            mutated = True

        # Lever 2: max_tokens auto-tuning (always safe; not safety-rail-gated)
        if self.config.enable_maxtok_auto:
            new_body, capped, saved = self._apply_maxtok_cap(
                body, session_id=session_id, task_type=task_type
            )
            if capped:
                actions.maxtok_cap = True
                estimated_savings += saved
                body = new_body
                mutated = True

        # Lever 3: style shaping (SEARCH/LIST/SUMMARIZE only, not safety-rail)
        if self.config.enable_style and not safety_rail_active and should_inject_style(task_type):
            body, saved = self._apply_style(body)
            actions.style_terse = True
            estimated_savings += saved
            mutated = True

        # If no lever fired, return the original body reference
        # (flag-off / no-op golden contract).
        if not mutated:
            return OutputOptimizeDecision(request_body=request_body, task_type=task_type)
        return OutputOptimizeDecision(
            request_body=body,
            actions_applied=actions.applied,
            estimated_tokens_saved=estimated_savings,
            task_type=task_type,
        )

    def record_outcome(
        self,
        session_id: str,
        task_type: str,
        output_tokens: int,
        finish_reason: str,
    ) -> None:
        """Record the upstream response outcome. Used to update the
        per-(session, task_type) quantile.

        On finish_reason='max_tokens' (truncated), the truncation
        count is incremented and the cap is raised on the next call.
        """
        if not self.config.enabled:
            return
        if not isinstance(output_tokens, int) or output_tokens < 0:
            return
        key = (session_id, task_type)
        window = self._quantiles[key]
        window.append(output_tokens)
        if len(window) > self.config.quantile_window:
            del window[0]
        if finish_reason == "max_tokens":
            self._truncations[session_id] += 1
            self._bump_truncation(session_id)
        # Update stats.quantile_count for this session's most-recent
        # task type (debug aid).
        self._stats.setdefault(session_id, OutputOptStats())
        self._stats[session_id].quantile_count = len(window)

    def record_guard_failure(self, session_id: str) -> None:
        """Per spec: a guard failure disables levers 1 and 3 for the
        session. Lever 2 (max_tokens) is unaffected."""
        if not self.config.enabled:
            return
        self._safety_rail.add(session_id)
        self._stats.setdefault(session_id, OutputOptStats())
        self._stats[session_id].guard_failures += 1
        self._stats[session_id].safety_rail_active = True

    def record_client_retry(self, session_id: str) -> None:
        """Per spec: a client retry disables levers 1 and 3 for the
        session."""
        if not self.config.enabled:
            return
        self._safety_rail.add(session_id)
        self._stats.setdefault(session_id, OutputOptStats())
        self._stats[session_id].client_retries += 1
        self._stats[session_id].safety_rail_active = True

    def stats_for(self, session_id: str) -> OutputOptStats:
        return self._stats.setdefault(session_id, OutputOptStats())

    # -----------------------------------------------------------------------
    # Lever implementations
    # -----------------------------------------------------------------------

    def _detect_task_type_from_body(self, body: Mapping[str, Any]) -> str:
        """Find the last user message in the body and detect its type."""
        messages = body.get("messages") or []
        if not isinstance(messages, list):
            return "general"
        for msg in reversed(messages):
            if not isinstance(msg, dict):
                continue
            if msg.get("role") != "user":
                continue
            content = msg.get("content")
            if isinstance(content, str):
                return detect_task_type(content)
            if isinstance(content, list):
                # OpenAI/Anthropic content blocks; join text parts.
                parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        parts.append(str(block.get("text", "")))
                    elif isinstance(block, str):
                        parts.append(block)
                if parts:
                    return detect_task_type("\n".join(parts))
        return "general"

    def _apply_diff_edit(self, body: Mapping[str, Any]) -> tuple[dict[str, Any], int]:
        """Lever 1: append the diff-edit instruction to the last
        system message (or insert a new one). Returns (new_body,
        estimated_savings)."""
        # Shallow copy to avoid mutating the input.
        new_body = dict(body)
        messages = list(body.get("messages") or [])
        # Find the last system message.
        last_system_idx = None
        for i in range(len(messages) - 1, -1, -1):
            m = messages[i]
            if isinstance(m, dict) and m.get("role") == "system":
                last_system_idx = i
                break
        if last_system_idx is not None:
            sys_msg = dict(messages[last_system_idx])
            sys_msg["content"] = (sys_msg.get("content") or "") + _DIFF_EDIT_INSTRUCTION
            messages[last_system_idx] = sys_msg
        else:
            # Prepend a new system message
            messages.insert(0, {"role": "system", "content": _DIFF_EDIT_INSTRUCTION})
        new_body["messages"] = messages
        # Estimated savings: 30% reduction in output tokens for code-edit tasks
        # (a rough estimate; the spec labels this as "estimated").
        # We use a default of 200 tokens saved (a mid-range estimate
        # for a code-edit response).
        return new_body, 200

    def _apply_maxtok_cap(
        self,
        body: Mapping[str, Any],
        session_id: str,
        task_type: str,
    ) -> tuple[dict[str, Any], bool, int]:
        """Lever 2: cap max_tokens if the client didn't set it (or set
        it to > 4x p95). Returns (new_body, capped, estimated_savings)."""
        client_max = body.get("max_tokens")
        window = self._quantiles.get((session_id, task_type), [])
        # No history -> only set if the client didn't set
        if not window:
            if client_max is not None:
                return dict(body), False, 0
            # First request: no history, no client max -> set a
            # conservative default cap.
            new_body = dict(body)
            new_body["max_tokens"] = DEFAULT_OUTPUT_FIRST_CAP
            return new_body, True, 0
        # Have history -> compute the cap
        cap = cap_max_tokens(window)
        truncated_count = self._truncations.get(session_id, 0)
        # Raise the cap if we recently had a max_tokens truncation
        if truncated_count > 0:
            cap = int(cap * (1 + 0.5 * min(truncated_count, 3)))
        # If the client set max_tokens and it's <= cap, leave it
        if client_max is not None and client_max <= cap:
            return dict(body), False, 0
        # If the client set max_tokens and it's > 4x p95, cap it
        if client_max is not None and client_max > DEFAULT_MAXTOK_AUTO_MULTIPLIER * cap:
            new_body = dict(body)
            new_body["max_tokens"] = cap
            return new_body, True, client_max - cap
        # Client didn't set -> set the cap
        if client_max is None:
            new_body = dict(body)
            new_body["max_tokens"] = cap
            return new_body, True, 0
        return dict(body), False, 0

    def _apply_style(self, body: Mapping[str, Any]) -> tuple[dict[str, Any], int]:
        """Lever 3: append the terse-output instruction to the last
        system message (or insert a new one). Returns (new_body,
        estimated_savings)."""
        new_body = dict(body)
        messages = list(body.get("messages") or [])
        last_system_idx = None
        for i in range(len(messages) - 1, -1, -1):
            m = messages[i]
            if isinstance(m, dict) and m.get("role") == "system":
                last_system_idx = i
                break
        if last_system_idx is not None:
            sys_msg = dict(messages[last_system_idx])
            sys_msg["content"] = (sys_msg.get("content") or "") + _STYLE_TERSE_INSTRUCTION
            messages[last_system_idx] = sys_msg
        else:
            messages.insert(0, {"role": "system", "content": _STYLE_TERSE_INSTRUCTION})
        new_body["messages"] = messages
        # Estimated savings: 40% reduction in output tokens for terse
        # tasks (a rough estimate; the spec labels this as "estimated").
        return new_body, 100

    # -----------------------------------------------------------------------
    # Stats helpers
    # -----------------------------------------------------------------------

    def _bump_call(self, session_id: str) -> None:
        self._stats.setdefault(session_id, OutputOptStats()).calls += 1

    def _bump_truncation(self, session_id: str) -> None:
        self._stats.setdefault(session_id, OutputOptStats()).truncations += 1


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------


__all__ = [
    "OutputOptimizeConfig",
    "OutputOptimizeDecision",
    "OutputOptActions",
    "OutputOptStats",
    "OutputOptimizer",
    "DEFAULT_MAXTOK_AUTO_MULTIPLIER",
    "DEFAULT_OUTPUT_QUANTILE_PERCENTILE",
    "DEFAULT_OUTPUT_HEADROOM",
    "DEFAULT_OUTPUT_FIRST_CAP",
    "DEFAULT_QUANTILE_WINDOW",
    "detect_task_type",
    "cap_max_tokens",
    "should_inject_diff_edit",
    "should_inject_style",
]
