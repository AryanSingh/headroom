from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_benchmarks_doc_includes_compressor_task_classes() -> None:
    doc = (ROOT / "docs" / "benchmarks.md").read_text(encoding="utf-8")

    assert "### Compressor Task Classes" in doc
    assert "| Compressor | Intended task class | Strongest when | Weaker when |" in doc
    assert "`content_router`" in doc
    assert "`llmlingua`" in doc
    assert "`verbatim_compactor`" in doc


def test_benchmarks_doc_no_longer_claims_llmlingua_missing_from_env() -> None:
    doc = (ROOT / "docs" / "benchmarks.md").read_text(encoding="utf-8")

    assert "because `llmlingua` is not installed in the current environment" not in doc
    assert "This is a completed live run on 2026-07-10" in doc


def test_benchmarks_doc_reflects_fixed_local_code_path_story() -> None:
    doc = (ROOT / "docs" / "benchmarks.md").read_text(encoding="utf-8")

    assert (
        "| CodeSamples | ContentRouter | 74.8% | 111 | 3,225.8 | 0.823 | 1.000 | 1.000 | 1.000 |"
        in doc
    )
    assert "The previously broken local code-path proof is fixed" in doc
    assert "safe fallback removes low-value comments and redundant whitespace" in doc


def test_benchmarks_doc_records_completed_llmlingua_runs_with_model_identity() -> None:
    doc = (ROOT / "docs" / "benchmarks.md").read_text(encoding="utf-8")

    assert "pending fresh live artifact" not in doc
    assert "metadata.llmlingua_model = microsoft/llmlingua-2-xlm-roberta-large-meetingbank" in doc
    assert "| CodeSamples | 111 | 202 |" in doc
    assert "--disable-hf-xet" in doc
    assert "--hf-download-timeout 600" in doc
    assert "--llmlingua-model microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank" in doc
    assert "### Completed LLMLingua-2 BERT Base Run on 2026-07-10" in doc
    assert "| CodeSamples | 111 | 150 | 1.000 | 0.833 |" in doc
