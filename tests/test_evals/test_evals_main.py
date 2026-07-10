from __future__ import annotations

from types import SimpleNamespace


def test_cmd_suite_passes_compression_only_filters(monkeypatch, tmp_path, capsys) -> None:
    import cutctx.evals.__main__ as evals_main

    captured = {}

    class FakeSuiteRunner:
        def __init__(self, **kwargs):  # noqa: ANN003
            captured.update(kwargs)

        def run(self):
            return SimpleNamespace(all_passed=True, benchmarks=[])

    def fake_save_reports(result, output_dir):  # noqa: ANN001
        return {"markdown": tmp_path / "report_card.md"}

    monkeypatch.setattr("cutctx.evals.suite_runner.SuiteRunner", FakeSuiteRunner)
    monkeypatch.setattr("cutctx.evals.reports.report_card.save_reports", fake_save_reports)

    args = SimpleNamespace(
        tier=2,
        model="gpt-5.4-mini",
        budget=0.0,
        port=8787,
        ci=False,
        no_proxy=True,
        compression_only=True,
        benchmark_name=["Verbatim Compaction", "Tool Schema Compaction"],
        output=str(tmp_path),
    )

    evals_main.cmd_suite(args)

    assert captured["runner_types"] == ["compression_only"]
    assert captured["benchmark_names"] == ["Verbatim Compaction", "Tool Schema Compaction"]
    output = capsys.readouterr().out
    assert "Selection: compression-only benchmarks" in output
    assert "Benchmarks: Verbatim Compaction, Tool Schema Compaction" in output
