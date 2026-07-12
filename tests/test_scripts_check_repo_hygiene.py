from pathlib import Path

from scripts import check_repo_hygiene as hygiene


def test_check_repo_hygiene_flags_disallowed_artifacts(monkeypatch, tmp_path, capsys):
    offenders = [
        tmp_path / "node_modules" / "pkg" / "index.js",
        Path("verify-report.json"),
        Path("verify-report.md"),
        Path("tmp123.txt"),
        Path("cache.db"),
    ]
    for path in offenders:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")

    monkeypatch.setattr(hygiene, "_tracked_files", lambda: [Path(path) for path in offenders])

    assert hygiene.main(["check_repo_hygiene.py"]) == 1
    out = capsys.readouterr().out
    assert "Repo hygiene check failed" in out
    assert "node_modules" in out
    assert "verify-report.json" in out
    assert "verify-report.md" in out
    assert "tmp123.txt" in out
    assert "cache.db" in out


def test_check_repo_hygiene_passes_clean_files(monkeypatch, tmp_path):
    clean = [tmp_path / "docs" / "guide.md", tmp_path / "src" / "module.py"]
    for path in clean:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("ok", encoding="utf-8")

    monkeypatch.setattr(hygiene, "_tracked_files", lambda: [Path(path) for path in clean])

    assert hygiene.main(["check_repo_hygiene.py"]) == 0
