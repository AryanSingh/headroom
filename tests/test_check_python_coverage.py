"""Tests for package-specific Python coverage gates."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "check_python_coverage", ROOT / "scripts" / "check_python_coverage.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_package_coverage_combines_lines_and_branches() -> None:
    module = _load_script()
    report = {
        "files": {
            "cutctx/a.py": {
                "summary": {
                    "covered_lines": 8,
                    "num_statements": 10,
                    "covered_branches": 3,
                    "num_branches": 5,
                }
            },
            "cutctx_ee/b.py": {
                "summary": {
                    "covered_lines": 2,
                    "num_statements": 10,
                    "covered_branches": 0,
                    "num_branches": 0,
                }
            },
        }
    }

    assert module.package_coverage(report, "cutctx/") == 73.33
    assert module.package_coverage(report, "cutctx_ee/") == 20.0
