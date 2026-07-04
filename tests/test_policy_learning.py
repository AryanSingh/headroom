from __future__ import annotations

import json
from unittest.mock import patch

from click.testing import CliRunner

from cutctx.cli.main import main
from cutctx.hooks import CompressContext
from cutctx.policy_learning import (
    LearnedPolicyHooks,
    evict_unsafe_policies,
    load_policies,
    reset_policies,
    train_from_events,
)


def test_train_from_events_writes_inspectable_policy_table(tmp_path):
    db_path = tmp_path / "policies.db"
    events = [
        {
            "tool_name": "grep",
            "content_type": "tool_output",
            "repo": "repo-a",
            "original_tokens": 1000,
            "compressed_tokens": 250,
            "retrieved": False,
            "guard_failed": False,
        }
        for _ in range(25)
    ]

    policies = train_from_events(events, db_path)

    assert len(policies) == 1
    assert policies[0].aggressiveness == "aggressive"
    assert policies[0].algorithm_hint == "smart_crusher"
    assert load_policies(db_path)[0].samples == 25


def test_train_from_events_is_conservative_on_retrievals(tmp_path):
    db_path = tmp_path / "policies.db"
    events = [
        {
            "tool_name": "deploy.log",
            "content_type": "log",
            "repo": "repo-a",
            "original_tokens": 1000,
            "compressed_tokens": 300,
            "retrieved": i < 2,
            "guard_failed": False,
        }
        for i in range(20)
    ]

    policy = train_from_events(events, db_path)[0]

    assert policy.aggressiveness == "conservative"
    assert policy.algorithm_hint == "drain3"


def test_reset_policies_restores_empty_table(tmp_path):
    db_path = tmp_path / "policies.db"
    train_from_events(
        [
            {
                "tool_name": "grep",
                "content_type": "tool_output",
                "repo": "repo-a",
                "original_tokens": 10,
                "compressed_tokens": 5,
            }
        ],
        db_path,
    )

    assert reset_policies(db_path) == 1
    assert load_policies(db_path) == []


def test_learned_policy_hooks_cold_start_returns_no_biases(tmp_path):
    hooks = LearnedPolicyHooks(tmp_path / "policies.db", repo="repo-a")

    assert (
        hooks.compute_biases(
            [{"role": "tool", "name": "grep", "content": "result"}],
            CompressContext(tool_calls=["grep"]),
        )
        == {}
    )


def test_learned_policy_hooks_apply_bounded_biases(tmp_path):
    db_path = tmp_path / "policies.db"
    train_from_events(
        [
            {
                "tool_name": "grep",
                "content_type": "tool_output",
                "repo": "repo-a",
                "original_tokens": 1000,
                "compressed_tokens": 250,
                "retrieved": False,
                "guard_failed": False,
            }
            for _ in range(25)
        ],
        db_path,
    )
    hooks = LearnedPolicyHooks(db_path, repo="repo-a")

    biases = hooks.compute_biases(
        [{"role": "tool", "name": "grep", "content": "result"}],
        CompressContext(tool_calls=["grep"]),
    )

    assert biases == {0: 0.75}


def test_evict_unsafe_policies_removes_guard_failure_rows(tmp_path):
    db_path = tmp_path / "policies.db"
    train_from_events(
        [
            {
                "tool_name": "deploy.log",
                "content_type": "log",
                "repo": "repo-a",
                "original_tokens": 1000,
                "compressed_tokens": 900,
                "retrieved": False,
                "guard_failed": True,
            }
        ],
        db_path,
    )

    assert evict_unsafe_policies(db_path) == 1
    assert load_policies(db_path) == []


def test_policies_cli_train_show_reset(tmp_path):
    runner = CliRunner()
    db_path = tmp_path / "policies.db"
    events_path = tmp_path / "events.jsonl"
    events_path.write_text(
        "\n".join(
            json.dumps(
                {
                    "tool_name": "grep",
                    "content_type": "tool_output",
                    "repo": "repo-a",
                    "original_tokens": 1000,
                    "compressed_tokens": 250,
                    "retrieved": False,
                    "guard_failed": False,
                }
            )
            for _ in range(25)
        ),
        encoding="utf-8",
    )

    train_result = runner.invoke(
        main, ["policies", "train", str(events_path), "--db", str(db_path)]
    )
    show_result = runner.invoke(main, ["policies", "show", "--db", str(db_path)])
    json_result = runner.invoke(main, ["policies", "show", "--json", "--db", str(db_path)])
    reset_result = runner.invoke(main, ["policies", "reset", "--db", str(db_path)])

    assert train_result.exit_code == 0
    assert "Learned 1 policy row" in train_result.output
    assert show_result.exit_code == 0
    assert "repo-a / grep / tool_output: aggressive" in show_result.output
    assert json_result.exit_code == 0
    assert json.loads(json_result.output)[0]["aggressiveness"] == "aggressive"
    assert reset_result.exit_code == 0
    assert "Deleted 1 learned policy row" in reset_result.output


def test_policies_train_help_mentions_watch_flag(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["policies", "train", "--help"])

    assert result.exit_code == 0, result.output
    assert "--watch" in result.output
    assert "--poll-interval" in result.output


def test_policies_train_watch_initial_pass(tmp_path):
    """Watch mode runs initial training pass, then handles Ctrl+C."""
    runner = CliRunner()
    db_path = tmp_path / "policies.db"
    events_dir = tmp_path / "events"
    events_dir.mkdir(parents=True)
    batch = events_dir / "batch1.jsonl"
    batch.write_text(
        "\n".join(
            json.dumps(
                {
                    "tool_name": "grep",
                    "content_type": "tool_output",
                    "repo": "repo-a",
                    "original_tokens": 1000,
                    "compressed_tokens": 250,
                    "retrieved": False,
                    "guard_failed": False,
                }
            )
            for _ in range(25)
        ),
        encoding="utf-8",
    )

    with patch("time.sleep", side_effect=KeyboardInterrupt()):
        result = runner.invoke(
            main,
            [
                "policies",
                "train",
                str(batch),
                "--db",
                str(db_path),
                "--watch",
                "--poll-interval",
                "30",
            ],
        )

    assert result.exit_code == 0, result.output
    assert "Watching" in result.output
    assert "Trained 1 policy row" in result.output
    # Verify policies were actually written
    policies = load_policies(db_path)
    assert len(policies) == 1
    assert policies[0].aggressiveness == "aggressive"


def test_policies_cli_evict_unsafe(tmp_path):
    runner = CliRunner()
    db_path = tmp_path / "policies.db"
    events_path = tmp_path / "events.jsonl"
    events_path.write_text(
        json.dumps(
            {
                "tool_name": "deploy.log",
                "content_type": "log",
                "repo": "repo-a",
                "original_tokens": 1000,
                "compressed_tokens": 900,
                "retrieved": False,
                "guard_failed": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    train_result = runner.invoke(
        main, ["policies", "train", str(events_path), "--db", str(db_path)]
    )
    evict_result = runner.invoke(main, ["policies", "evict-unsafe", "--db", str(db_path)])

    assert train_result.exit_code == 0
    assert evict_result.exit_code == 0
    assert "Evicted 1 unsafe learned policy row" in evict_result.output
    assert load_policies(db_path) == []
