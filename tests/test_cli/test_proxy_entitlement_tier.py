"""The proxy CLI must honor the documented entitlement-tier configuration.

`cutctx/proxy/models.py` documents `CUTCTX_ENTITLEMENT_TIER` (and a
`--entitlement-tier` flag) as the way to declare a plan tier; `docs/content/
docs/plans.mdx` and the docs env table advertise the env var as the dev/QA
path for exercising paid features. The CLI entrypoint (`cutctx proxy`) built
ProxyConfig without ever reading it, so the documented path was dead: a QA
engineer (or a customer on the honor-system open-core path) always ran as
builder tier regardless of the setting.
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from cutctx.cli.main import main
from cutctx.proxy.server import ProxyConfig


def _capture_config(env: dict[str, str], args: list[str] | None = None) -> ProxyConfig:
    captured: dict[str, ProxyConfig] = {}

    def mock_run_server(config: ProxyConfig, **_kwargs: object) -> None:
        captured["config"] = config

    runner = CliRunner()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("cutctx.proxy.server.run_server", mock_run_server)
        # Hermetic: the CLI merges a machine-local .env.local via
        # load_local_env(setdefault); neutralize it so the test reflects
        # only the env passed here, not the developer's dotfile.
        mp.setattr("cutctx.env.load_local_env", lambda *a, **k: ())
        full_env = {"CUTCTX_ENTITLEMENT_TIER": "", **env}
        result = runner.invoke(
            main,
            ["proxy", *(args or [])],
            env=full_env,
            catch_exceptions=False,
        )
    assert result.exit_code == 0, result.output
    return captured["config"]


def test_proxy_cli_reads_entitlement_tier_env() -> None:
    config = _capture_config({"CUTCTX_ENTITLEMENT_TIER": "enterprise"})
    assert config.entitlement_tier == "enterprise"


def test_proxy_cli_entitlement_tier_unset_is_falsy() -> None:
    # Unset (or empty) tier must not silently grant a paid plan.
    config = _capture_config({})
    assert not config.entitlement_tier
