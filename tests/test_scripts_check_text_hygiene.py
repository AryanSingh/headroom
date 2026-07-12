from pathlib import Path

from scripts import check_text_hygiene as hygiene


def test_check_text_hygiene_flags_collapsed_python_and_markdown(monkeypatch, tmp_path, capsys):
    py_path = tmp_path / "bad.py"
    py_path.write_text("x = 1; y = 2\n", encoding="utf-8")
    md_path = tmp_path / "bad.md"
    md_path.write_text("a" * 221 + "\n", encoding="utf-8")

    monkeypatch.setattr(hygiene, "_tracked_files", lambda: [Path(py_path), Path(md_path)])

    assert hygiene.main(["check_text_hygiene.py"]) == 1
    out = capsys.readouterr().out
    assert "avoid semicolon-collapsed Python statements" in out
    assert "line looks collapsed" in out


def test_check_text_hygiene_passes_clean_files(monkeypatch, tmp_path):
    py_path = tmp_path / "good.py"
    py_path.write_text("x = 1\nprint(x)\n", encoding="utf-8")
    md_path = tmp_path / "good.md"
    md_path.write_text("# Heading\n\nThis is fine.\n", encoding="utf-8")

    monkeypatch.setattr(hygiene, "_tracked_files", lambda: [Path(py_path), Path(md_path)])

    assert hygiene.main(["check_text_hygiene.py"]) == 0
