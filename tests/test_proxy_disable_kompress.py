"""Proxy configuration for disabling Kompress while keeping optimization on."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from cutctx.proxy.server import ProxyConfig, create_app
from cutctx.transforms import CompressionStrategy, ContentRouter


def _proxy_router(config: ProxyConfig):
    app = create_app(config)
    proxy = app.state.proxy
    return next(
        transform
        for transform in proxy.anthropic_pipeline.transforms
        if isinstance(transform, ContentRouter)
    )


def test_disable_kompress_config_keeps_optimization_but_disables_ml_fallback() -> None:
    router = _proxy_router(
        ProxyConfig(
            optimize=True,
            disable_kompress=True,
            cache_enabled=False,
            rate_limit_enabled=False,
            cost_tracking_enabled=False,
            log_requests=False,
        )
    )

    assert router.config.enable_kompress is False
    assert router.config.fallback_strategy == CompressionStrategy.PASSTHROUGH


def test_default_proxy_uses_fast_non_kompress_fallback() -> None:
    router = _proxy_router(
        ProxyConfig(
            optimize=True,
            cache_enabled=False,
            rate_limit_enabled=False,
            cost_tracking_enabled=False,
            log_requests=False,
        )
    )

    assert router.config.enable_kompress is False
    assert router.config.fallback_strategy == CompressionStrategy.PASSTHROUGH


def test_proxy_threads_selected_compression_policy_to_content_router() -> None:
    router = _proxy_router(
        ProxyConfig(
            optimize=True,
            compression_mode="aggressive",
            cache_enabled=False,
            rate_limit_enabled=False,
            cost_tracking_enabled=False,
            log_requests=False,
        )
    )

    assert router.config.compression_mode == "aggressive"


def test_default_proxy_enables_safe_terse_output_steering() -> None:
    app = create_app(
        ProxyConfig(
            optimize=True,
            cache_enabled=False,
            rate_limit_enabled=False,
            cost_tracking_enabled=False,
            log_requests=False,
        )
    )

    output_config = app.state.proxy.output_optimizer.config
    assert output_config.enabled is True
    assert output_config.enable_style is True
    assert output_config.enable_diff_edit is False
    assert output_config.enable_maxtok_auto is False
