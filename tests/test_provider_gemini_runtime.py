from __future__ import annotations

from cutctx.providers.gemini import build_launch_env, proxy_base_url
from cutctx.providers.gemini.install import build_install_env


def test_gemini_proxy_base_url_uses_local_proxy_root() -> None:
    assert proxy_base_url(7654) == "http://127.0.0.1:7654"


def test_gemini_build_install_env_routes_all_modes_through_proxy() -> None:
    env = build_install_env(port=7654, backend="ignored")

    assert env == {
        "GOOGLE_GEMINI_BASE_URL": "http://127.0.0.1:7654",
        "GOOGLE_VERTEX_BASE_URL": "http://127.0.0.1:7654",
        "CODE_ASSIST_ENDPOINT": "http://127.0.0.1:7654",
        "GEMINI_API_BASE": "http://127.0.0.1:7654",
        "GEMINI_API_BASE_URL": "http://127.0.0.1:7654",
        "GEMINI_BASE_URL": "http://127.0.0.1:7654",
        "GOOGLE_API_BASE": "http://127.0.0.1:7654",
    }


def test_gemini_build_launch_env_applies_project_prefix() -> None:
    env, lines = build_launch_env(8787, {}, project="frontend")

    expected = "http://127.0.0.1:8787/p/frontend"
    assert env["GOOGLE_GEMINI_BASE_URL"] == expected
    assert env["GOOGLE_VERTEX_BASE_URL"] == expected
    assert env["CODE_ASSIST_ENDPOINT"] == expected
    assert lines == [
        f"GOOGLE_GEMINI_BASE_URL={expected}",
        f"GOOGLE_VERTEX_BASE_URL={expected}",
        f"CODE_ASSIST_ENDPOINT={expected}",
    ]
