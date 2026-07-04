"""WS4: Context policy engine MVP.

Declarative redaction/block/allow rules and cumulative per-agent/per-team
budgets. Composes with existing RBAC, audit, and proxy policy scaffolding.

Usage:
    policy = load_context_policy("policy.yaml")
    engine = ContextPolicyEngine(policy)
    result = engine.evaluate(messages, agent_id="agent-1")
    # result.blocked, result.redacted_messages, result.budget_remaining
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RedactRule:
    """A regex-based redaction rule applied to context content.

    Attributes:
        name: Rule identifier for audit/reporting.
        pattern: Compiled regex pattern to match.
        replacement: Replacement string for matched text.
        scope: Where to apply — 'content', 'tool_name', 'content_type', or
            'any'. 'any' searches message text, tool_name, and content_type.
    """

    name: str
    pattern: str
    replacement: str = "[REDACTED]"
    scope: str = "content"

    def compile(self) -> re.Pattern[str]:
        return re.compile(self.pattern)

    def apply(self, text: str, compiled: re.Pattern[str]) -> str:
        return compiled.sub(self.replacement, text)


@dataclass(frozen=True)
class BlockRule:
    """A rule that blocks requests matching a pattern.

    If any block rule matches, the request is rejected with the given reason.
    Block rules are evaluated before redaction (blocked requests are never
    forwarded, so redaction is unnecessary).
    """

    name: str
    pattern: str
    scope: str = "content"
    reason: str = "Blocked by policy"


@dataclass(frozen=True)
class AllowRule:
    """A positive allowlist rule.

    When allow rules are present, ONLY content matching at least one allow
    rule is passed through. When no allow rules are defined, all content is
    accepted (unless blocked by a block rule).
    """

    name: str
    pattern: str
    scope: str = "content"


@dataclass
class BudgetState:
    """Runtime mutable budget tracking for an agent or team."""

    agent_id: str
    tokens_used_hour: int = 0
    requests_hour: int = 0
    tokens_used_day: int = 0
    hour_start: float = field(default_factory=time.time)
    day_start: float = field(default_factory=time.time)

    def reset_if_expired(self) -> None:
        now = time.time()
        if now - self.hour_start > 3600:
            self.tokens_used_hour = 0
            self.requests_hour = 0
            self.hour_start = now
        if now - self.day_start > 86400:
            self.tokens_used_day = 0
            self.day_start = now

    def can_accept(self, tokens: int, max_hour: int, max_day: int) -> bool:
        self.reset_if_expired()
        if max_hour > 0 and self.tokens_used_hour + tokens > max_hour:
            return False
        if max_day > 0 and self.tokens_used_day + tokens > max_day:
            return False
        return True

    def record(self, tokens: int) -> None:
        self.tokens_used_hour += tokens
        self.requests_hour += 1
        self.tokens_used_day += tokens


@dataclass
class AgentBudget:
    """Budget limits for a single agent."""

    agent_id: str
    max_tokens_per_hour: int = 0  # 0 = unlimited
    max_requests_per_hour: int = 0
    max_tokens_per_day: int = 0


@dataclass
class TeamBudget:
    """Budget limits for an entire team (sum of all agents in the team)."""

    team_id: str
    max_tokens_per_day: int = 0
    max_usd_per_month: float = 0.0


@dataclass
class ContextPolicy:
    """Complete context policy configuration."""

    version: str = "1"
    redact_rules: list[RedactRule] = field(default_factory=list)
    block_rules: list[BlockRule] = field(default_factory=list)
    allow_rules: list[AllowRule] = field(default_factory=list)
    agent_budgets: list[AgentBudget] = field(default_factory=list)
    team_budgets: list[TeamBudget] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


@dataclass
class EvaluationResult:
    """Result of evaluating a policy against a set of messages."""

    blocked: bool = False
    block_reason: str = ""
    redacted_messages: list[dict[str, Any]] = field(default_factory=list)
    matched_redact_rules: list[str] = field(default_factory=list)
    matched_block_rules: list[str] = field(default_factory=list)
    budget_allowed: bool = True
    budget_remaining_tokens: int = 0
    budget_reason: str = ""


class ContextPolicyEngine:
    """Evaluates context policy rules against messages.

    The engine supports three rule types plus budget enforcement:
    1. Block rules (highest priority — blocked requests never proceed)
    2. Redact rules (applied to allowed requests)
    3. Allow rules (when present, create an implicit deny-all default)
    4. Budget checks (per-agent and per-team cumulative tracking)
    """

    def __init__(
        self,
        policy: ContextPolicy | None = None,
    ) -> None:
        self.policy = policy or ContextPolicy()
        self._budget_states: dict[str, BudgetState] = {}
        self._team_states: dict[str, BudgetState] = {}
        self._compile_rules()

    def _compile_rules(self) -> None:
        """Pre-compile all regex patterns for fast evaluation."""
        self._compiled_redact: list[tuple[RedactRule, re.Pattern[str]]] = [
            (rule, rule.compile()) for rule in self.policy.redact_rules
        ]
        self._compiled_block: list[tuple[BlockRule, re.Pattern[str]]] = [
            (rule, re.compile(rule.pattern)) for rule in self.policy.block_rules
        ]
        self._compiled_allow: list[tuple[AllowRule, re.Pattern[str]]] = [
            (rule, re.compile(rule.pattern)) for rule in self.policy.allow_rules
        ]
        self._has_allow_rules = len(self._compiled_allow) > 0

    def _get_text_for_scope(self, message: dict[str, Any], scope: str) -> list[str]:
        """Extract target text from a message based on scope."""
        texts: list[str] = []
        content = message.get("content")
        if scope in ("content", "any") and isinstance(content, str):
            texts.append(content)
        if scope in ("tool_name", "any"):
            for key in ("tool_name", "name"):
                value = message.get(key)
                if isinstance(value, str):
                    texts.append(value)
        if scope in ("content_type", "any"):
            value = message.get("content_type")
            if isinstance(value, str):
                texts.append(value)
        return texts

    def _match_any_scope(self, texts: list[str], compiled: re.Pattern[str]) -> bool:
        for text in texts:
            if compiled.search(text):
                return True
        return False

    def _check_block(self, messages: list[dict[str, Any]]) -> EvaluationResult:
        """Check if any block rule matches. Returns blocked result or None."""
        for rule, compiled in self._compiled_block:
            for msg in messages:
                texts = self._get_text_for_scope(msg, rule.scope)
                if self._match_any_scope(texts, compiled):
                    return EvaluationResult(
                        blocked=True,
                        block_reason=rule.reason,
                        matched_block_rules=[rule.name],
                    )
        return EvaluationResult()

    def _apply_redactions(self, messages: list[dict[str, Any]]) -> EvaluationResult:
        """Apply redact rules and check allow-rule gates."""
        redacted = [dict(msg) for msg in messages]
        matched_redact: list[str] = []
        has_allow = self._has_allow_rules

        for i, msg in enumerate(redacted):
            # Check allow rules first — when present, only pass through
            # content that matches at least one allow rule
            if has_allow:
                allowed = False
                for _, compiled in self._compiled_allow:
                    texts = self._get_text_for_scope(msg, "any")
                    if self._match_any_scope(texts, compiled):
                        allowed = True
                        break
                if not allowed:
                    redacted[i] = {
                        "_policy_dropped": True,
                        "_policy_reason": "Not matched by any allow rule",
                    }
                    continue

            # Apply redaction rules
            for rule, compiled in self._compiled_redact:
                targets: list[tuple[str, str]] = []  # (key, value)
                base = msg.get("content", "")
                if isinstance(base, str):
                    targets.append(("content", base))
                if rule.scope in ("tool_name", "any"):
                    for kn in ("name", "tool_name"):
                        v = msg.get(kn)
                        if isinstance(v, str):
                            targets.append((kn, v))
                if rule.scope in ("content_type", "any"):
                    v = msg.get("content_type")
                    if isinstance(v, str):
                        targets.append(("content_type", v))

                for key, value in targets:
                    if compiled.search(value):
                        new_value = compiled.sub(rule.replacement, value)
                        redacted[i][key] = new_value
                        if rule.name not in matched_redact:
                            matched_redact.append(rule.name)

        return EvaluationResult(
            redacted_messages=redacted,
            matched_redact_rules=matched_redact,
        )

    def _check_budget(
        self,
        agent_id: str | None,
        team_id: str | None,
        tokens: int,
    ) -> EvaluationResult:
        """Check per-agent and per-team budget limits."""
        if agent_id is None and team_id is None:
            return EvaluationResult(budget_allowed=True)

        # Per-agent budget check
        if agent_id is not None:
            budget = self._find_agent_budget(agent_id)
            state = self._budget_states.setdefault(agent_id, BudgetState(agent_id=agent_id))
            if not state.can_accept(
                tokens,
                max_hour=budget.max_tokens_per_hour if budget else 0,
                max_day=budget.max_tokens_per_day if budget else 0,
            ):
                return EvaluationResult(
                    budget_allowed=False,
                    budget_reason=(f"Agent {agent_id} budget exceeded"),
                    budget_remaining_tokens=0,
                )

        if team_id is not None:
            budget = self._find_team_budget(team_id)
            state = self._team_states.setdefault(team_id, BudgetState(agent_id=team_id))
            if not state.can_accept(
                tokens,
                max_hour=0,
                max_day=budget.max_tokens_per_day if budget else 0,
            ):
                return EvaluationResult(
                    blocked=True,
                    budget_allowed=False,
                    budget_reason=f"Team {team_id} budget exceeded",
                    budget_remaining_tokens=0,
                )

        return EvaluationResult(budget_allowed=True)

    def _find_agent_budget(self, agent_id: str) -> AgentBudget | None:
        for budget in self.policy.agent_budgets:
            if budget.agent_id == agent_id:
                return budget
        return None

    def _find_team_budget(self, team_id: str) -> TeamBudget | None:
        for budget in self.policy.team_budgets:
            if budget.team_id == team_id:
                return budget
        return None

    def record_usage(
        self,
        agent_id: str | None = None,
        team_id: str | None = None,
        tokens: int = 0,
    ) -> None:
        """Record token usage for budget tracking after request completes."""
        if agent_id is not None:
            state = self._budget_states.setdefault(agent_id, BudgetState(agent_id=agent_id))
            state.record(tokens)
        if team_id is not None:
            state = self._team_states.setdefault(team_id, BudgetState(agent_id=team_id))
            state.record(tokens)

    def evaluate(
        self,
        messages: list[dict[str, Any]],
        *,
        agent_id: str | None = None,
        team_id: str | None = None,
        estimate_tokens: int = 0,
    ) -> EvaluationResult:
        """Evaluate all policy rules against a batch of messages.

        Processing order:
        1. Block rules (if any match → blocked, no further processing)
        2. Budget check (if exceeded → blocked)
        3. Redaction + allow rules (transform messages in place)

        Returns an EvaluationResult with the combined outcome.
        """
        # Step 1: Block rules
        block_result = self._check_block(messages)
        if block_result.blocked:
            return block_result

        # Step 2: Budget check
        budget_result = self._check_budget(
            agent_id,
            team_id,
            estimate_tokens or sum(len(str(msg.get("content", ""))) for msg in messages),
        )
        if not budget_result.budget_allowed:
            return budget_result

        # Step 3: Apply redactions and allow rules
        redact_result = self._apply_redactions(messages)

        return EvaluationResult(
            blocked=False,
            redacted_messages=redact_result.redacted_messages,
            matched_redact_rules=redact_result.matched_redact_rules,
            budget_allowed=True,
        )


# ---------------------------------------------------------------------------
# Policy loading
# ---------------------------------------------------------------------------


def _parse_redact_rules(data: list[dict[str, Any]]) -> list[RedactRule]:
    return [
        RedactRule(
            name=str(rule.get("name", f"redact-{i}")),
            pattern=str(rule["pattern"]),
            replacement=str(rule.get("replacement", "[REDACTED]")),
            scope=str(rule.get("scope", "content")),
        )
        for i, rule in enumerate(data)
    ]


def _parse_block_rules(data: list[dict[str, Any]]) -> list[BlockRule]:
    return [
        BlockRule(
            name=str(rule.get("name", f"block-{i}")),
            pattern=str(rule["pattern"]),
            scope=str(rule.get("scope", "content")),
            reason=str(rule.get("reason", "Blocked by policy")),
        )
        for i, rule in enumerate(data)
    ]


def _parse_allow_rules(data: list[dict[str, Any]]) -> list[AllowRule]:
    return [
        AllowRule(
            name=str(rule.get("name", f"allow-{i}")),
            pattern=str(rule["pattern"]),
            scope=str(rule.get("scope", "content")),
        )
        for i, rule in enumerate(data)
    ]


def _parse_agent_budgets(data: list[dict[str, Any]]) -> list[AgentBudget]:
    return [
        AgentBudget(
            agent_id=str(budget["agent_id"]),
            max_tokens_per_hour=int(budget.get("max_tokens_per_hour", 0)),
            max_requests_per_hour=int(budget.get("max_requests_per_hour", 0)),
            max_tokens_per_day=int(budget.get("max_tokens_per_day", 0)),
        )
        for budget in data
    ]


def _parse_team_budgets(data: list[dict[str, Any]]) -> list[TeamBudget]:
    return [
        TeamBudget(
            team_id=str(budget["team_id"]),
            max_tokens_per_day=int(budget.get("max_tokens_per_day", 0)),
            max_usd_per_month=float(budget.get("max_usd_per_month", 0.0)),
        )
        for budget in data
    ]


def load_context_policy_from_dict(data: dict[str, Any]) -> ContextPolicy:
    """Load a context policy from a dictionary (e.g., parsed YAML or JSON)."""
    return ContextPolicy(
        version=str(data.get("version", "1")),
        redact_rules=_parse_redact_rules(data.get("redact_rules", [])),
        block_rules=_parse_block_rules(data.get("block_rules", [])),
        allow_rules=_parse_allow_rules(data.get("allow_rules", [])),
        agent_budgets=_parse_agent_budgets(data.get("agent_budgets", [])),
        team_budgets=_parse_team_budgets(data.get("team_budgets", [])),
    )


def load_context_policy(path: Path | str) -> ContextPolicy:
    """Load a context policy from a YAML file.

    Falls back to JSON if PyYAML is not available.
    """
    path = Path(path)
    raw = path.read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        try:
            import yaml as _yaml  # type: ignore[import-untyped]

            data = _yaml.safe_load(raw)
        except ImportError:
            import json

            data = json.loads(raw)
    else:
        import json

        data = json.loads(raw)
    return load_context_policy_from_dict(data)


# ---------------------------------------------------------------------------
# Convenience: default policy file
# ---------------------------------------------------------------------------

_DEFAULT_POLICY_ENV = "CUTCTX_CONTEXT_POLICY"


def default_policy_path() -> Path | None:
    """Return the default context policy file path from env or None."""
    env_path = os.environ.get(_DEFAULT_POLICY_ENV)
    if env_path:
        return Path(env_path).expanduser()
    return None
