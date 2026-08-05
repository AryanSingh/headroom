from __future__ import annotations

from unittest.mock import Mock

from click.testing import CliRunner

from cutctx.cli.rbac import rbac


def test_empty_assignment_list_describes_fail_closed_default(monkeypatch) -> None:
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"assignments": {}}
    monkeypatch.setattr("cutctx.cli.rbac.httpx.get", lambda *args, **kwargs: response)

    result = CliRunner().invoke(rbac, ["list"])

    assert result.exit_code == 0
    assert "read-only viewer" in result.output
    assert "default to admin" not in result.output


def test_assign_accepts_memory_curator_role_supported_by_api(monkeypatch) -> None:
    captured: dict[str, object] = {}
    response = Mock()
    response.raise_for_status.return_value = None

    def post(url: str, **kwargs: object) -> Mock:
        captured.update({"url": url, **kwargs})
        return response

    monkeypatch.setattr("cutctx.cli.rbac.httpx.post", post)

    result = CliRunner().invoke(
        rbac,
        ["assign", "curator@example.com", "--role", "memory_curator"],
    )

    assert result.exit_code == 0
    assert captured["json"] == {
        "user_id": "curator@example.com",
        "role": "memory_curator",
    }
    assert "Assigned role 'memory_curator'" in result.output
