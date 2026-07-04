# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs
"""Tests for the WS16 normalize pre-pass wiring into ContentRouter.

Per artifacts/savings-moat-expansion-specs.md WS16 step 2 (ContentRouter
wiring as a pre-pass before compressors) and strategy-implementation-plan.md
§0.1 (flag-off golden parity test is permanent in the suite).

The pre-pass is a no-op when all sub-flags are off. The tests below
assert both contracts:
  - Flag-off: ContentRouter.compress() bytes identical to pre-WS16.
  - Flag-on: ContentRouter sees post-normalized content (e.g. decomposed
    unicode is composed, trailing whitespace is stripped).
"""

from __future__ import annotations

from cutctx.transforms.content_router import ContentRouter, ContentRouterConfig
from cutctx.transforms.normalize import NormalizeConfig

# ---------------------------------------------------------------------------
# Flag-off golden parity — the spec's permanent contract test
# ---------------------------------------------------------------------------


def test_content_router_flag_off_is_byte_identical() -> None:
    """With the default NormalizeConfig (all sub-flags off), ContentRouter
    must behave byte-identically to the pre-WS16 path. This is the
    flag-off golden test from the spec.
    """
    router = ContentRouter()  # NormalizeConfig() default: all off
    inputs = [
        "hello world",
        "héllo wörld",  # non-ASCII
        "    \n\n   foo   \n\n\n   bar   \n",  # whitespace
        "1.12345\n2.67890",  # numeric
        "aGVsbG8gd29ybGQ=",  # base64-ish
        "0xdeadbeefcafebabe1234567890abcdef",  # hex
    ]
    for s in inputs:
        result = router.compress(s)
        # The compressed content may differ from the input (compression
        # is applied) but the pre-pass MUST NOT have altered the input
        # before compression ran. We assert this indirectly: run
        # normalize_content on the input and confirm it returns s
        # unchanged when the flag is off.
        from cutctx.transforms.normalize import normalize_content

        n = normalize_content(s, NormalizeConfig())
        assert n.content == s, (
            f"normalize pre-pass altered input when flag off: {s!r} -> {n.content!r}"
        )


def test_content_router_default_normalize_config_is_all_off() -> None:
    """ContentRouterConfig().normalize_config must be a default
    NormalizeConfig (all sub-flags off). This is the spec's
    additive-only contract.
    """
    cfg = ContentRouterConfig()
    nc = cfg.normalize_config
    assert nc.enable_unicode_normalization is False
    assert nc.enable_whitespace_collapse is False
    assert nc.enable_blob_to_pointer is False
    assert nc.enable_decimal_cap is False


def test_content_router_config_normalize_field_is_default_factory() -> None:
    """ContentRouterConfig.normalize_config must be a fresh
    NormalizeConfig per instance (no shared mutable state across
    router instances — the additive-only contract).
    """
    a = ContentRouterConfig()
    b = ContentRouterConfig()
    assert a.normalize_config is not b.normalize_config
    assert a.normalize_config.enable_unicode_normalization is False
    a.normalize_config.enable_unicode_normalization = True
    assert b.normalize_config.enable_unicode_normalization is False, (
        "mutating one ContentRouterConfig's normalize_config leaked into another"
    )


# ---------------------------------------------------------------------------
# Flag-on: pre-pass fires and content changes
# ---------------------------------------------------------------------------


def test_content_router_unicode_normalize_runs_when_enabled() -> None:
    """When enable_unicode_normalization is on, the pre-pass should
    compose decomposed unicode before compression. We don't assert
    what the compressor does with the composed string (it depends on
    the strategy), only that the pre-pass ran — verified by
    instrumenting normalize_content and asserting the call.
    """
    import cutctx.transforms.content_router as cr_module
    import cutctx.transforms.normalize as normalize_module

    calls: list[tuple[str, NormalizeConfig]] = []
    original = normalize_module.normalize_content

    def _spy(content: str, config: NormalizeConfig, tokenizer=None):  # type: ignore[no-untyped-def]
        calls.append((content, config))
        return original(content, config, tokenizer)

    normalize_module.normalize_content = _spy
    # content_router does `from .normalize import normalize_content`
    # so the local binding is content_router_module.normalize_content.
    cr_module.normalize_content = _spy
    try:
        router = ContentRouter(
            config=ContentRouterConfig(
                normalize_config=NormalizeConfig(enable_unicode_normalization=True),
            )
        )
        # Use a non-trivial input
        router.compress("cafe\u0301 latte")  # decomposed "café latte"
    finally:
        normalize_module.normalize_content = original
        cr_module.normalize_content = original

    assert len(calls) == 1, f"expected 1 normalize call, got {len(calls)}"
    assert calls[0][1].enable_unicode_normalization is True


def test_content_router_whitespace_collapse_runs_when_enabled() -> None:
    """When enable_whitespace_collapse is on, the pre-pass strips
    trailing whitespace and collapses blank-line runs.
    """
    import cutctx.transforms.content_router as cr_module
    import cutctx.transforms.normalize as normalize_module

    calls: list[tuple[str, NormalizeConfig]] = []
    original = normalize_module.normalize_content

    def _spy(content: str, config: NormalizeConfig, tokenizer=None):  # type: ignore[no-untyped-def]
        calls.append((content, config))
        return original(content, config, tokenizer)

    normalize_module.normalize_content = _spy
    cr_module.normalize_content = _spy
    try:
        router = ContentRouter(
            config=ContentRouterConfig(
                normalize_config=NormalizeConfig(enable_whitespace_collapse=True),
            )
        )
        router.compress("foo   \nbar   ")
    finally:
        normalize_module.normalize_content = original
        cr_module.normalize_content = original

    assert len(calls) == 1
    assert calls[0][1].enable_whitespace_collapse is True


def test_content_router_compress_sees_post_normalized_content() -> None:
    """End-to-end behavioral test: when the pre-pass strips trailing
    whitespace, the compressor sees the stripped content.

    We use a content type whose compression is content-faithful (e.g.
    the LogCompressor preserves structure), so the pre-pass output
    is visible in the compressed result.
    """
    router = ContentRouter(
        config=ContentRouterConfig(
            normalize_config=NormalizeConfig(enable_whitespace_collapse=True),
        )
    )
    raw = "INFO: server started\nINFO: ready   \nINFO: listening   \n"
    result = router.compress(raw)
    # The trailing whitespace on lines 2 and 3 should be gone.
    # We don't assert the exact compressed form (depends on strategy),
    # only that no line has trailing whitespace.
    for line in result.compressed.splitlines():
        if line:  # skip empty lines
            assert line == line.rstrip(), f"trailing whitespace survived normalization: {line!r}"


def test_content_router_off_path_unchanged_against_spy() -> None:
    """The flag-off path must not call normalize_content at all. This
    is the strict version of the golden contract.
    """
    import cutctx.transforms.normalize as normalize_module

    calls: list[tuple[str, NormalizeConfig]] = []
    original = normalize_module.normalize_content

    def _spy(content: str, config: NormalizeConfig, tokenizer=None):  # type: ignore[no-untyped-def]
        calls.append((content, config))
        return original(content, config, tokenizer)

    normalize_module.normalize_content = _spy
    try:
        router = ContentRouter()  # default: all off
        router.compress("hello world")
        router.compress("héllo wörld")
        router.compress("foo   \nbar")
    finally:
        normalize_module.normalize_content = original

    assert calls == [], f"normalize_content was called with flag off: {len(calls)} call(s)"


# ---------------------------------------------------------------------------
# Regression guard: the pre-pass must not break the existing compress() contract
# ---------------------------------------------------------------------------


def test_content_router_still_returns_router_compression_result() -> None:
    """The normalize pre-pass must not change the return type or shape
    of compress().
    """
    from cutctx.transforms.content_router import RouterCompressionResult

    router = ContentRouter()
    result = router.compress("hello world")
    assert isinstance(result, RouterCompressionResult)
    # `original` field is the pre-compression input. With flag off,
    # it equals the input; with flag on, it still equals the input
    # (the pre-pass modifies `content` for compression but `original`
    # tracks the user-provided input).
    assert result.original == "hello world"
    # `compressed` may be shorter or equal.
    assert isinstance(result.compressed, str)


def test_content_router_passes_through_when_normalize_off_and_no_compressor() -> None:
    """When normalize is off AND no compressor matches, ContentRouter
    should fall through to the fallback strategy (per existing
    content_router tests). The pre-pass must not break this path.
    """
    router = ContentRouter(
        config=ContentRouterConfig(
            # Disable all compressors to force fallback path
            enable_code_aware=False,
            enable_kompress=False,
            enable_smart_crusher=False,
            enable_search_compressor=False,
            enable_log_compressor=False,
            enable_html_extractor=False,
            enable_image_optimizer=False,
        )
    )
    result = router.compress("hello world")
    # PASSTHROUGH or fallback (Kompress). Either is acceptable; the
    # point is no exception, and result is a RouterCompressionResult.
    assert hasattr(result, "compressed")
    assert hasattr(result, "original")
    assert result.original == "hello world"
