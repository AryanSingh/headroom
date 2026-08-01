from __future__ import annotations

import subprocess

from scripts.check_secret_patterns import main


def test_secret_pattern_hook_rejects_project_key(tmp_path) -> None:
    candidate = tmp_path / "settings.txt"
    candidate.write_text(
        "OPENAI_API_KEY=" + "sk" + "-proj-" + "abcdefghijklmnopqrstuvwxyz", encoding="utf-8"
    )

    assert main([str(candidate)]) == 1


def test_secret_pattern_hook_allows_non_secret_text(tmp_path) -> None:
    candidate = tmp_path / "settings.txt"
    candidate.write_text("OPENAI_API_KEY is configured externally", encoding="utf-8")

    assert main([str(candidate)]) == 0


def test_secret_pattern_hook_without_paths_scans_untracked_nonignored_files(
    tmp_path, monkeypatch
) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    candidate = tmp_path / "untracked-settings.txt"
    candidate.write_text("OPENAI_API_KEY=" + "sk" + "-proj-" + ("a" * 26), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert main([]) == 1
