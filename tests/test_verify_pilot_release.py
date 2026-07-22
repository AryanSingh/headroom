from __future__ import annotations

import json
from pathlib import Path

from scripts import verify_pilot_release as verifier


def test_build_report_marks_failed_required_command(monkeypatch) -> None:
    check = verifier.Check("unit", ("python", "-V"))
    monkeypatch.setattr(
        verifier,
        "run_check",
        lambda current: {
            "name": current.name,
            "required": current.required,
            "status": "failed",
            "returncode": 1,
        },
    )

    report = verifier.build_report((check,))

    assert report["passed"] is False
    assert report["failed"] == 1
    assert report["passed_count"] == 0


def test_optional_failure_does_not_fail_report(monkeypatch) -> None:
    check = verifier.Check("manual", ("python", "-V"), required=False)
    monkeypatch.setattr(
        verifier,
        "run_check",
        lambda current: {
            "name": current.name,
            "required": current.required,
            "status": "failed",
            "returncode": 1,
        },
    )

    report = verifier.build_report((check,))

    assert report["passed"] is True
    assert report["failed"] == 0
    assert report["optional_failed"] == 1


def test_write_report_emits_json(tmp_path: Path) -> None:
    output = tmp_path / "report.json"

    verifier.write_report(output, {"passed": True, "checks": []})

    assert json.loads(output.read_text(encoding="utf-8"))["passed"] is True


def test_list_mode_prints_checks_without_running(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        verifier,
        "run_check",
        lambda check: (_ for _ in ()).throw(AssertionError("must not execute")),
    )

    exit_code = verifier.main(["--list"])

    assert exit_code == 0
    assert "pilot-doc-contracts" in capsys.readouterr().out
