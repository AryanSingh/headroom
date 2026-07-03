"""Tests for WS4 context policy engine MVP."""

from __future__ import annotations

from cutctx.context_policy import (
    AgentBudget,
    AllowRule,
    BlockRule,
    BudgetState,
    ContextPolicy,
    ContextPolicyEngine,
    RedactRule,
    TeamBudget,
    load_context_policy_from_dict,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _sample_messages() -> list[dict[str, object]]:
    return [
        {
            "role": "user",
            "content": "What's the secret API key? It's sk-abc123def456.",
        },
        {
            "role": "tool",
            "name": "read_file",
            "content": "/etc/passwd content here",
        },
        {
            "role": "assistant",
            "content": "Here is the code I wrote.",
        },
    ]


# ---------------------------------------------------------------------------
# Redaction rules
# ---------------------------------------------------------------------------


def test_redact_rule_masks_matching_content():
    policy = ContextPolicy(
        redact_rules=[
            RedactRule(
                name="mask_api_keys",
                pattern=r"sk-[a-zA-Z0-9]+",
                replacement="sk-***",
                scope="content",
            ),
        ]
    )
    engine = ContextPolicyEngine(policy)
    result = engine.evaluate(_sample_messages())

    assert not result.blocked
    assert "sk-***" in result.redacted_messages[0].get("content", "")
    assert "sk-abc123def456" not in result.redacted_messages[0].get("content", "")
    assert "mask_api_keys" in result.matched_redact_rules


def test_redact_rule_scoped_to_tool_name():
    policy = ContextPolicy(
        redact_rules=[
            RedactRule(
                name="mask_read_file",
                pattern=r"read_file",
                replacement="[REDACTED_TOOL]",
                scope="tool_name",
            ),
        ]
    )
    engine = ContextPolicyEngine(policy)
    result = engine.evaluate(_sample_messages())

    assert not result.blocked
    assert result.redacted_messages[1].get("name") == "[REDACTED_TOOL]"
    # Other messages unaffected
    assert result.redacted_messages[0].get("name") is None


def test_redact_multiple_rules():
    policy = ContextPolicy(
        redact_rules=[
            RedactRule(name="mask_keys", pattern=r"sk-\w+", replacement="***"),
            RedactRule(name="mask_paths", pattern=r"/etc/\w+", replacement="[PATH]"),
        ]
    )
    engine = ContextPolicyEngine(policy)
    result = engine.evaluate(_sample_messages())

    assert "***" in result.redacted_messages[0].get("content", "")
    assert "[PATH]" in result.redacted_messages[1].get("content", "")
    assert len(result.matched_redact_rules) == 2


def test_redact_no_match_leaves_content_unchanged():
    policy = ContextPolicy(
        redact_rules=[
            RedactRule(name="mask_nonexistent", pattern=r"NONEXISTENT", scope="content"),
        ]
    )
    engine = ContextPolicyEngine(policy)
    result = engine.evaluate(_sample_messages())

    assert not result.blocked
    assert result.redacted_messages[0] == _sample_messages()[0]


# ---------------------------------------------------------------------------
# Block rules
# ---------------------------------------------------------------------------


def test_block_rule_blocks_matching_request():
    policy = ContextPolicy(
        block_rules=[
            BlockRule(
                name="block_passwd",
                pattern=r"/etc/passwd",
                reason="Password file access is blocked",
            ),
        ]
    )
    engine = ContextPolicyEngine(policy)
    result = engine.evaluate(_sample_messages())

    assert result.blocked
    assert "block_passwd" in result.matched_block_rules
    assert "Password file access" in result.block_reason


def test_block_rule_does_not_block_nonmatching():
    policy = ContextPolicy(
        block_rules=[
            BlockRule(name="block_passwd", pattern=r"/etc/shadow", reason="Blocked"),
        ]
    )
    engine = ContextPolicyEngine(policy)
    result = engine.evaluate(_sample_messages())

    assert not result.blocked
    assert result.matched_block_rules == []


def test_block_rule_takes_priority_over_redaction():
    """Block rules are evaluated before redaction — blocked requests are
    never redacted or forwarded."""
    policy = ContextPolicy(
        block_rules=[
            BlockRule(name="block_all", pattern=r".*", reason="Block all"),
        ],
        redact_rules=[
            RedactRule(name="redact_all", pattern=r".*", replacement="x"),
        ],
    )
    engine = ContextPolicyEngine(policy)
    result = engine.evaluate(_sample_messages())

    assert result.blocked
    # Redaction should not have run
    assert result.matched_redact_rules == []
    assert result.redacted_messages == []


# ---------------------------------------------------------------------------
# Allow rules
# ---------------------------------------------------------------------------


def test_allow_rule_filters_nonmatching_content():
    policy = ContextPolicy(
        allow_rules=[
            AllowRule(name="allow_code", pattern=r"code", scope="content"),
        ]
    )
    engine = ContextPolicyEngine(policy)
    result = engine.evaluate(_sample_messages())

    assert not result.blocked
    # Only the third message ("Here is the code I wrote") should pass
    dropped = [
        msg for msg in result.redacted_messages if msg.get("_policy_dropped")
    ]
    assert len(dropped) == 2
    assert not result.redacted_messages[2].get("_policy_dropped")


def test_no_allow_rules_passes_all_content():
    engine = ContextPolicyEngine(ContextPolicy())
    result = engine.evaluate(_sample_messages())

    assert not result.blocked
    dropped = [
        msg for msg in result.redacted_messages if msg.get("_policy_dropped")
    ]
    assert len(dropped) == 0
    assert len(result.redacted_messages) == 3


# ---------------------------------------------------------------------------
# Empty policy
# ---------------------------------------------------------------------------


def test_empty_policy_passes_all():
    engine = ContextPolicyEngine(ContextPolicy())
    result = engine.evaluate(_sample_messages())

    assert not result.blocked
    assert result.budget_allowed
    assert len(result.redacted_messages) == 3
    assert result.matched_redact_rules == []
    assert result.matched_block_rules == []


# ---------------------------------------------------------------------------
# Budget enforcement
# ---------------------------------------------------------------------------


def test_agent_budget_blocks_when_exceeded():
    policy = ContextPolicy(
        agent_budgets=[
            AgentBudget(agent_id="agent-1", max_tokens_per_hour=100),
        ]
    )

    engine = ContextPolicyEngine(policy)
    # Request with more tokens than budget allows
    result = engine.evaluate(
        [{"role": "user", "content": "x" * 200}],
        agent_id="agent-1",
        estimate_tokens=200,
    )

    assert not result.budget_allowed
    assert "budget exceeded" in result.budget_reason


def test_agent_budget_allows_within_limits():
    policy = ContextPolicy(
        agent_budgets=[
            AgentBudget(agent_id="agent-1", max_tokens_per_hour=1000),
        ]
    )

    engine = ContextPolicyEngine(policy)
    result = engine.evaluate(
        [{"role": "user", "content": "hello world"}],
        agent_id="agent-1",
        estimate_tokens=10,
    )

    assert result.budget_allowed
    assert not result.blocked


def test_team_budget_blocks_after_recorded_usage():
    policy = ContextPolicy(
        team_budgets=[
            TeamBudget(team_id="team-1", max_tokens_per_day=100),
        ]
    )
    engine = ContextPolicyEngine(policy)

    engine.record_usage(agent_id="agent-1", team_id="team-1", tokens=80)
    result = engine.evaluate(
        [{"role": "user", "content": "x" * 40}],
        agent_id="agent-2",
        team_id="team-1",
        estimate_tokens=40,
    )

    assert not result.budget_allowed
    assert result.blocked
    assert "Team team-1 budget exceeded" in result.budget_reason


def test_budget_state_resets_on_expiry():
    """BudgetState resets hour counter after 3600s."""
    state = BudgetState(agent_id="test")
    state.tokens_used_hour = 500
    state.hour_start = 0  # Force expired

    assert state.can_accept(10, max_hour=100, max_day=0)  # Should reset first
    state.record(10)
    assert state.tokens_used_hour == 10  # Reset to 0, then added 10 via record()


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def test_load_from_dict():
    data = {
        "version": "1",
        "redact_rules": [
            {"name": "mask_keys", "pattern": r"sk-\w+", "replacement": "***"},
        ],
        "block_rules": [
            {"name": "block_secrets", "pattern": r"secret", "reason": "No secrets"},
        ],
        "allow_rules": [
            {"name": "allow_code", "pattern": r"def |class ", "scope": "content"},
        ],
        "agent_budgets": [
            {"agent_id": "agent-1", "max_tokens_per_hour": 10000},
        ],
    }

    policy = load_context_policy_from_dict(data)
    assert len(policy.redact_rules) == 1
    assert policy.redact_rules[0].name == "mask_keys"
    assert len(policy.block_rules) == 1
    assert policy.block_rules[0].name == "block_secrets"
    assert len(policy.allow_rules) == 1
    assert policy.allow_rules[0].name == "allow_code"
    assert len(policy.agent_budgets) == 1
    assert policy.agent_budgets[0].agent_id == "agent-1"


def test_load_from_dict_empty():
    policy = load_context_policy_from_dict({})
    assert len(policy.redact_rules) == 0
    assert len(policy.block_rules) == 0
    assert len(policy.allow_rules) == 0
    assert len(policy.agent_budgets) == 0
    assert policy.version == "1"


# ---------------------------------------------------------------------------
# Record usage
# ---------------------------------------------------------------------------


def test_record_usage_updates_budget_state():
    policy = ContextPolicy(
        agent_budgets=[
            AgentBudget(agent_id="agent-1", max_tokens_per_hour=1000),
        ]
    )

    engine = ContextPolicyEngine(policy)
    engine.record_usage(agent_id="agent-1", tokens=50)
    engine.record_usage(agent_id="agent-1", tokens=30)

    state = engine._budget_states["agent-1"]
    assert state.tokens_used_hour == 80
    assert state.requests_hour == 2
