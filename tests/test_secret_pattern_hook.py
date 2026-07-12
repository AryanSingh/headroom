from __future__ import annotations

from scripts.check_secret_patterns import main


def test_secret_pattern_hook_rejects_project_key(tmp_path) -> None:
    candidate = tmp_path / "settings.txt"
    candidate.write_text("OPENAI_API_KEY=sk-proj-abcdefghijklmnopqrstuvwxyz", encoding="utf-8")

    assert main([str(candidate)]) == 1


def test_secret_pattern_hook_allows_non_secret_text(tmp_path) -> None:
    candidate = tmp_path / "settings.txt"
    candidate.write_text("OPENAI_API_KEY is configured externally", encoding="utf-8")

    assert main([str(candidate)]) == 0
