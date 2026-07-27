"""Kompress must be reachable from the proxy.

Kompress is the highest-fidelity compressor in the product: benchmarked at
matched compression ratio it reaches 0.962 information recall on LongBench
against LLMLingua-2's 0.960 (docs/benchmarks-vs-llmlingua.md).

It could not be turned on. The proxy builds its own ContentRouter, so the
CUTCTX_ENABLE_KOMPRESS env var read in transforms/pipeline.py never reached
it, and the only assignment to router_config.enable_kompress set it to False.
The shipped `--disable-kompress` flag therefore disabled something already
off, and the quality tier was unreachable in the product's main surface.
"""

from __future__ import annotations

import os

import pytest

from cutctx.cli.proxy import proxy as proxy_command
from cutctx.proxy.models import ProxyConfig
from cutctx.transforms.content_router import CompressionStrategy, ContentRouterConfig


def _resolve(config: ProxyConfig) -> ContentRouterConfig:
    """Mirror the enable/disable resolution in proxy/server.py."""
    router_config = ContentRouterConfig()
    if getattr(config, "enable_kompress", False):
        router_config.enable_kompress = True
        router_config.fallback_strategy = CompressionStrategy.KOMPRESS
    if config.disable_kompress:
        router_config.enable_kompress = False
        router_config.fallback_strategy = CompressionStrategy.PASSTHROUGH
    return router_config


def test_kompress_is_off_by_default() -> None:
    """1.5-5.6s per payload is not viable for every request."""
    assert ProxyConfig().enable_kompress is False
    assert _resolve(ProxyConfig()).enable_kompress is False


def test_kompress_can_actually_be_enabled() -> None:
    """The regression: there was no way to reach it at all."""
    router_config = _resolve(ProxyConfig(enable_kompress=True))

    assert router_config.enable_kompress is True
    assert router_config.fallback_strategy is CompressionStrategy.KOMPRESS


def test_disable_wins_over_enable() -> None:
    """--disable-kompress is the explicit rule-based-only switch."""
    router_config = _resolve(ProxyConfig(enable_kompress=True, disable_kompress=True))

    assert router_config.enable_kompress is False
    assert router_config.fallback_strategy is CompressionStrategy.PASSTHROUGH


@pytest.mark.parametrize(
    ("argv", "env", "expected"),
    [
        ([], {}, False),
        (["--enable-kompress"], {}, True),
        ([], {"CUTCTX_ENABLE_KOMPRESS": "1"}, True),
    ],
)
def test_cli_exposes_the_switch(
    monkeypatch: pytest.MonkeyPatch, argv: list[str], env: dict[str, str], expected: bool
) -> None:
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("CUTCTX_DISABLE_KOMPRESS", raising=False)
    if not env:
        monkeypatch.delenv("CUTCTX_ENABLE_KOMPRESS", raising=False)

    ctx = proxy_command.make_context("proxy", list(argv), resilient_parsing=True)

    assert ctx.params.get("enable_kompress") is expected
    assert os.environ.get("CUTCTX_DISABLE_KOMPRESS") is None
