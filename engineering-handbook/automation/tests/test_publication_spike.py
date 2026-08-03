import json
from pathlib import Path

from build_handbook import build_full_publication, build_publication_spike, mark_visual_review


def test_publication_spike_builds_docx_pdf_and_visual_ledger(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    destination = tmp_path / "dist"

    artifacts = build_publication_spike(root, destination)

    assert artifacts["docx"].is_file()
    assert artifacts["pdf"].is_file()
    ledger = json.loads(artifacts["ledger"].read_text(encoding="utf-8"))
    assert ledger["status"] == "rendered"
    assert ledger["pages"] >= 2
    assert len(ledger["reviewed_pages"]) == ledger["pages"]

    mark_visual_review(artifacts["ledger"], reviewer="test-reviewer")
    assert json.loads(artifacts["ledger"].read_text(encoding="utf-8"))["status"] == "passed"


def test_full_publication_writes_resolved_contents_and_render_ledger(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    destination = tmp_path / "dist"

    artifacts = build_full_publication(root, destination)

    assert artifacts["docx"].is_file()
    assert artifacts["pdf"].is_file()
    ledger = json.loads(artifacts["ledger"].read_text(encoding="utf-8"))
    assert ledger["status"] == "rendered"
    assert ledger["pages"] >= 100
    assert all(page > 2 for page in ledger["toc_pages"].values())
