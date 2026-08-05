"""H12 regression: CLI commands must exit non-zero when they fail.

The audit found ~10 commands that printed an error and exited 0:
  * ``cutctx audit list|stats|export``, ``orgs list``, ``rbac list`` all
    caught the auth 401, printed ``Error: ...`` and returned success.
  * ``cutctx verify`` printed ``Status: FAIL`` and exited 0 unless ``--ci``
    was passed, so the "CI-friendly" gate could not fail a build.

Exit code 0 means success. A command that printed an error and exited 0 is
invisible to ``set -e``, to CI, and to any caller that checks ``$?``.
"""

from __future__ import annotations

import httpx
import pytest
from click.testing import CliRunner

from cutctx.cli.main import main


@pytest.fixture
def runner():
    return CliRunner()


def _raise_401(*_args, **_kwargs):
    request = httpx.Request("GET", "http://127.0.0.1:8787/audit/events")
    response = httpx.Response(401, request=request, text="Unauthorized")
    raise httpx.HTTPStatusError("401 Unauthorized", request=request, response=response)


# --------------------------------------------------------------------------
# Auth failures across the admin-facing command groups
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("argv", "module"),
    [
        (["audit", "list", "--admin-key", "wrong"], "cutctx.cli.audit"),
        (["audit", "stats", "--admin-key", "wrong"], "cutctx.cli.audit"),
        (["audit", "export", "--admin-key", "wrong"], "cutctx.cli.audit"),
        (["orgs", "list", "--admin-key", "wrong"], "cutctx.cli.orgs"),
        (["rbac", "list", "--admin-key", "wrong"], "cutctx.cli.rbac"),
    ],
)
def test_admin_commands_exit_nonzero_on_auth_failure(runner, monkeypatch, argv, module):
    """A 401 must not be reported as success."""
    import importlib

    mod = importlib.import_module(module)
    monkeypatch.setattr(mod.httpx, "get", _raise_401, raising=False)

    result = runner.invoke(main, argv)

    assert result.exit_code != 0, (
        f"{' '.join(argv)} printed an error but exited 0:\n{result.output}"
    )
    assert "401" in result.output or "Error" in result.output


def test_error_message_is_still_shown(runner, monkeypatch):
    """Non-zero exit must not come at the cost of the diagnostic."""
    import cutctx.cli.audit as audit_mod

    monkeypatch.setattr(audit_mod.httpx, "get", _raise_401, raising=False)
    result = runner.invoke(main, ["audit", "list", "--admin-key", "wrong"])

    assert result.exit_code == 1
    assert "401" in result.output


def test_connection_error_also_exits_nonzero(runner, monkeypatch):
    import cutctx.cli.audit as audit_mod

    def _boom(*_args, **_kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(audit_mod.httpx, "get", _boom, raising=False)
    result = runner.invoke(main, ["audit", "stats"])

    assert result.exit_code != 0


# --------------------------------------------------------------------------
# verify: the CI gate
# --------------------------------------------------------------------------


FAILING_REPORT = {
    "git_sha": "deadbeef",
    "generated_at": "2026-08-04T00:00:00+00:00",
    "dataset": "tool_outputs",
    "datasets": ["tool_outputs"],
    "compressors": ["content_router"],
    "thresholds": {},
    "summary": {
        "datasets": 1,
        "compressors": 1,
        "rows": 1,
        "passed": 0,
        "failed": 1,
        "skipped": 0,
        "duration_ms": 1.0,
        "tokens_saved": 0,
    },
    "results": [],
    "skipped_compressors": [],
    "pass": False,
}

PASSING_REPORT = {**FAILING_REPORT, "pass": True}
PASSING_REPORT["summary"] = {**FAILING_REPORT["summary"], "passed": 1, "failed": 0}


def test_verify_exits_nonzero_on_fail_without_ci_flag(runner, monkeypatch):
    """The core H12 case: Status: FAIL must fail the build by default."""
    import cutctx.cli.evals as cli_evals

    monkeypatch.setattr(cli_evals, "_run_verify", lambda **_kw: FAILING_REPORT)
    result = runner.invoke(main, ["verify"])

    assert result.exit_code == 1, result.output
    assert "FAIL" in result.output


def test_verify_exits_zero_on_pass(runner, monkeypatch):
    """A passing verdict must still be a success exit."""
    import cutctx.cli.evals as cli_evals

    monkeypatch.setattr(cli_evals, "_run_verify", lambda **_kw: PASSING_REPORT)
    result = runner.invoke(main, ["verify"])

    assert result.exit_code == 0, result.output


def test_verify_json_format_still_emits_report_on_failure(runner, monkeypatch):
    """Non-zero exit must not suppress the machine-readable report."""
    import json

    import cutctx.cli.evals as cli_evals

    monkeypatch.setattr(cli_evals, "_run_verify", lambda **_kw: FAILING_REPORT)
    result = runner.invoke(main, ["verify", "--format", "json"])

    assert result.exit_code == 1
    assert json.loads(result.output)["git_sha"] == "deadbeef"


def test_verify_ci_flag_remains_backwards_compatible(runner, monkeypatch):
    import cutctx.cli.evals as cli_evals

    monkeypatch.setattr(cli_evals, "_run_verify", lambda **_kw: FAILING_REPORT)
    assert runner.invoke(main, ["verify", "--ci"]).exit_code == 1

    monkeypatch.setattr(cli_evals, "_run_verify", lambda **_kw: PASSING_REPORT)
    assert runner.invoke(main, ["verify", "--ci"]).exit_code == 0


# --------------------------------------------------------------------------
# H11 b-e — broken CLI commands
# --------------------------------------------------------------------------


def test_config_check_rejects_out_of_range_port(runner):
    """H11e: --port 99999 used to raise an unhandled OverflowError."""
    result = runner.invoke(main, ["config-check", "--port", "99999"])

    assert result.exit_code != 0
    assert result.exception is None or isinstance(result.exception, SystemExit), (
        f"unhandled traceback: {result.exception!r}"
    )
    assert "65535" in result.output or "range" in result.output.lower()


def test_config_check_accepts_valid_port(runner):
    result = runner.invoke(main, ["config-check", "--port", "8788", "--format", "json"])
    assert not isinstance(result.exception, OverflowError)


@pytest.mark.parametrize("bad_ttl", ["-3", "0"])
def test_license_token_rejects_non_positive_ttl(runner, bad_ttl):
    """H11d: --ttl-hours -3 minted an already-expired token."""
    result = runner.invoke(main, ["license", "token", "--ttl-hours", bad_ttl])

    assert result.exit_code != 0
    assert "range" in result.output.lower() or "invalid" in result.output.lower()


def test_memory_purge_confirm_flag_does_not_prompt(runner, tmp_path, monkeypatch):
    """H11b: --confirm prompted anyway and hung forever under CI."""
    import cutctx.cli.memory as memory_cli

    db_path = tmp_path / "memories.db"

    class _FakeStore:
        async def clear_all(self):
            return 3

    monkeypatch.setattr(memory_cli, "get_store", lambda _p: _FakeStore())
    monkeypatch.setattr(memory_cli, "_get_stats", lambda _s: {"total_count": 3})

    def _explode(*_a, **_k):
        raise AssertionError("click.confirm was called despite --confirm")

    monkeypatch.setattr(memory_cli.click, "confirm", _explode)

    # Empty stdin models a non-interactive caller: the old code hung here.
    result = runner.invoke(
        main, ["memory", "purge", "--db-path", str(db_path), "--confirm"], input=""
    )

    assert result.exit_code == 0, result.output
    assert "3" in result.output


def test_memory_purge_without_confirm_still_refuses(runner, tmp_path):
    result = runner.invoke(main, ["memory", "purge", "--db-path", str(tmp_path / "m.db")])
    assert result.exit_code == 1


def test_memory_stats_does_not_create_a_database(runner, tmp_path, monkeypatch):
    """H11c: `cutctx memory stats` silently created an empty DB in the cwd."""
    monkeypatch.chdir(tmp_path)
    missing = tmp_path / "nope.db"

    result = runner.invoke(main, ["memory", "stats", "--db-path", str(missing)])

    assert result.exit_code != 0
    assert not missing.exists(), "stats created a database as a side effect"
    assert not (tmp_path / "cutctx_memory.db").exists()


def test_memory_db_path_defaults_to_workspace_not_cwd():
    """H11c root cause: the default was a bare relative filename."""
    from cutctx.cli.memory import default_db_path

    resolved = default_db_path()
    assert resolved != "cutctx_memory.db"
    assert "/" in resolved, f"default must be an absolute workspace path, got {resolved!r}"


# --------------------------------------------------------------------------
# H11a — the orgs group was non-functional (response-envelope mismatch)
# --------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_orgs_list_reads_the_orgs_envelope(runner, monkeypatch):
    """H11a: CLI read 'organizations'; the API returns 'orgs'."""
    import cutctx.cli.orgs as orgs_cli

    payload = {
        "orgs": [
            {"id": "org-1", "name": "Acme", "slug": "acme"},
            {"id": "org-2", "name": "Globex", "slug": "globex"},
        ]
    }
    monkeypatch.setattr(orgs_cli.httpx, "get", lambda *a, **k: _FakeResponse(payload))

    result = runner.invoke(main, ["orgs", "list", "--admin-key", "k"])

    assert result.exit_code == 0, result.output
    assert "No organizations found" not in result.output
    assert "Acme" in result.output
    assert "org-1" in result.output
    assert "Globex" in result.output


def test_orgs_create_prints_the_real_id(runner, monkeypatch):
    """H11a: create printed id=? because the id sits under the 'org' envelope."""
    import cutctx.cli.orgs as orgs_cli

    payload = {"org": {"id": "org-42", "name": "Acme", "slug": "acme"}}
    monkeypatch.setattr(orgs_cli.httpx, "post", lambda *a, **k: _FakeResponse(payload))

    result = runner.invoke(
        main, ["orgs", "create", "--name", "Acme", "--email", "a@b.com", "--admin-key", "k"]
    )

    assert result.exit_code == 0, result.output
    assert "id=org-42" in result.output
    assert "id=?" not in result.output


def test_orgs_show_prints_real_fields(runner, monkeypatch):
    """H11a: show printed ?/?/? for name, id and slug."""
    import cutctx.cli.orgs as orgs_cli

    payload = {
        "org": {
            "id": "org-7",
            "name": "Acme",
            "slug": "acme",
            "workspaces": [{"name": "ws-1", "projects": [{"name": "proj-1"}]}],
        }
    }
    monkeypatch.setattr(orgs_cli.httpx, "get", lambda *a, **k: _FakeResponse(payload))

    result = runner.invoke(main, ["orgs", "show", "org-7", "--admin-key", "k"])

    assert result.exit_code == 0, result.output
    assert "?" not in result.output
    assert "Acme" in result.output
    assert "org-7" in result.output
    assert "ws-1" in result.output
    assert "proj-1" in result.output


def test_orgs_list_tolerates_a_bare_list(runner, monkeypatch):
    import cutctx.cli.orgs as orgs_cli

    payload = [{"id": "org-1", "name": "Acme", "slug": "acme"}]
    monkeypatch.setattr(orgs_cli.httpx, "get", lambda *a, **k: _FakeResponse(payload))

    result = runner.invoke(main, ["orgs", "list", "--admin-key", "k"])
    assert result.exit_code == 0
    assert "Acme" in result.output
