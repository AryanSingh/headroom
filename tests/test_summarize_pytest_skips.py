import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).parents[1] / "scripts" / "summarize_pytest_skips.py"
_SPEC = importlib.util.spec_from_file_location("summarize_pytest_skips", _SCRIPT)
assert _SPEC and _SPEC.loader
skip_report = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(skip_report)


def test_classify_skip_reasons() -> None:
    assert skip_report.classify_reason("OPENAI_API_KEY not set") == "external-credential"
    assert skip_report.classify_reason("spaCy not installed") == "optional-extra"
    assert skip_report.classify_reason("Ollama not running") == "network-service"
    assert skip_report.classify_reason("Kompress requires GPU") == "platform-or-hardware"
    assert skip_report.classify_reason("PR-B5: endpoint retired") == "intentional-deprecation"


def test_summarize_includes_categories(tmp_path) -> None:
    report = tmp_path / "pytest.xml"
    report.write_text(
        "<testsuite><testcase classname='suite' name='live'><skipped message='OPENAI_API_KEY not set' />"
        "</testcase><testcase classname='suite' name='retired'><skipped message='endpoint retired' />"
        "</testcase></testsuite>",
        encoding="utf-8",
    )

    payload = skip_report.summarize(report)

    assert payload["total_skipped"] == 2
    assert payload["category_totals"] == {
        "external-credential": 1,
        "intentional-deprecation": 1,
    }
