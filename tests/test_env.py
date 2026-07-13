from __future__ import annotations

from pathlib import Path

from cutctx.env import load_local_env


def test_local_env_prefers_dotenv_local_without_overriding_exported_values(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("OPENAI_API_KEY=base\nBASE_ONLY=yes\n")
    (tmp_path / ".env.local").write_text("OPENAI_API_KEY=local\nLOCAL_ONLY=yes\n")
    environ = {"OPENAI_API_KEY": "exported"}

    loaded = load_local_env(cwd=tmp_path, environ=environ)

    assert loaded == (tmp_path / ".env.local", tmp_path / ".env")
    assert environ == {
        "OPENAI_API_KEY": "exported",
        "LOCAL_ONLY": "yes",
        "BASE_ONLY": "yes",
    }


def test_local_env_supports_an_explicit_env_file(tmp_path: Path) -> None:
    custom = tmp_path / "custom.env"
    custom.write_text("CUTCTX_UPSTREAM_OPENAI_API_KEY=example\n")
    environ = {"CUTCTX_ENV_FILE": str(custom)}

    loaded = load_local_env(cwd=tmp_path, environ=environ)

    assert loaded == (custom,)
    assert environ["CUTCTX_UPSTREAM_OPENAI_API_KEY"] == "example"
