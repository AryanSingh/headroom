from __future__ import annotations

from click.testing import CliRunner

from cutctx.cli.main import main


def test_config_doctor_exposes_existing_validation() -> None:
    result = CliRunner().invoke(main, ["config", "doctor", "--port", "0", "--format", "json"])

    assert result.exit_code == 0, result.output
    assert '"valid": true' in result.output
