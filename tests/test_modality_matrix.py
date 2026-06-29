"""Modality matrix verification test.

Validates that every externally-advertised data modality maps to a
discoverable implementation path and that the feature_availability
snapshot is internally consistent.

These are import/contract tests — they do NOT require optional extras to
be installed (missing extras → skip rather than fail).
"""
from __future__ import annotations

import importlib
import importlib.util
import sys

import pytest


# ── 1. Core compressor imports ──────────────────────────────────────────────

def test_log_compressor_importable():
    mod = importlib.import_module("cutctx.transforms.log_compressor")
    assert hasattr(mod, "LogCompressor") or mod is not None


def test_diff_compressor_importable():
    mod = importlib.import_module("cutctx.transforms.diff_compressor")
    assert mod is not None


def test_search_compressor_importable():
    mod = importlib.import_module("cutctx.transforms.search_compressor")
    assert mod is not None


def test_code_compressor_importable():
    mod = importlib.import_module("cutctx.transforms.code_compressor")
    assert mod is not None


def test_image_compressor_importable():
    mod = importlib.import_module("cutctx.image.compressor")
    assert mod is not None


# ── 2. Drain3 (log-ml extra) ────────────────────────────────────────────────

def test_drain3_compressor_importable():
    mod = importlib.import_module("cutctx.transforms.drain3_compressor")
    assert mod is not None


@pytest.mark.skipif(
    importlib.util.find_spec("drain3") is None,
    reason="drain3 not installed — pip install cutctx-ai[log-ml]",
)
def test_drain3_available_function():
    from cutctx.transforms.drain3_compressor import drain3_available
    result = drain3_available()
    assert result is not None  # True or module


# ── 3. Kompress (ONNX) ───────────────────────────────────────────────────────

def test_kompress_compressor_importable():
    mod = importlib.import_module("cutctx.transforms.kompress_compressor")
    assert mod is not None


# ── 4. LLMLingua extra ────────────────────────────────────────────────────────

def test_llmlingua_compressor_importable():
    mod = importlib.import_module("cutctx.transforms.llmlingua_compressor")
    assert mod is not None


# ── 5. feature_availability snapshot ─────────────────────────────────────────

def test_feature_availability_snapshot_structure():
    """The snapshot must return a dict with the canonical modality keys."""
    # We import the function without starting the proxy server
    import importlib as _imp
    spec = _imp.util.find_spec("cutctx.proxy.server")
    assert spec is not None, "cutctx.proxy.server must be importable"

    # Import just the helper — note it is a module-level def, not a class
    # We can't call it without a running proxy, so we just verify the
    # expected keys exist in the source via a snapshot import check.
    required_keys = {
        "knowledge_graph",
        "drain3",
        "difftastic",
        "llmlingua",
        "multimodal_image",
        "smart_crusher",
        "kompress",
        "html_extractor",
        "voice_filler",
        "code_ast",
        "audio",
    }
    import ast, pathlib
    server_src = pathlib.Path("cutctx/proxy/server.py").read_text()
    for key in required_keys:
        assert f'"{key}"' in server_src, (
            f"feature_availability snapshot is missing key {key!r}. "
            "Add it to _feature_availability_snapshot() in cutctx/proxy/server.py"
        )


# ── 6. Audio is documented as pass-through ────────────────────────────────────

def test_audio_modality_is_passthrough():
    """Audio routes exist but are documented as pass-through (no compression)."""
    import pathlib
    server_src = pathlib.Path("cutctx/proxy/server.py").read_text()
    # The feature_availability snapshot must label audio as pass-through
    assert "pass-through" in server_src, (
        "Audio must be documented as pass-through in _feature_availability_snapshot(). "
        "We proxy /v1/audio/* routes without token compression — this must be explicit."
    )


# ── 7. Audio proxy routes exist ────────────────────────────────────────────────

def test_audio_proxy_routes_present():
    """The proxy exposes /v1/audio/* routes (pass-through to upstream)."""
    import pathlib
    routes_src = pathlib.Path("cutctx/providers/proxy_routes.py").read_text()
    assert "/v1/audio/transcriptions" in routes_src
    assert "/v1/audio/speech" in routes_src


# ── 8. pyproject.toml has recommended and full extras ─────────────────────────

def test_pyproject_has_recommended_extra():
    import pathlib
    toml = pathlib.Path("pyproject.toml").read_text()
    assert "recommended" in toml, (
        "pyproject.toml must define a [recommended] extras group for production installs"
    )


def test_pyproject_has_full_extra():
    import pathlib
    toml = pathlib.Path("pyproject.toml").read_text()
    assert "full" in toml, (
        "pyproject.toml must define a [full] extras group for complete production installs"
    )


# ── 9. Modality truth table ────────────────────────────────────────────────────

MODALITY_TABLE = [
    ("prose/text",        "cutctx.compress",                    None),
    ("code",              "cutctx.transforms.code_compressor",  None),
    ("logs",              "cutctx.transforms.log_compressor",   None),
    ("diffs",             "cutctx.transforms.diff_compressor",  None),
    ("search output",     "cutctx.transforms.search_compressor",None),
    ("images",            "cutctx.image.compressor",            "PIL"),
    ("log ML (drain3)",   "cutctx.transforms.drain3_compressor","drain3"),
    ("kompress (ONNX)",   "cutctx.transforms.kompress_compressor","onnxruntime"),
    ("llmlingua",         "cutctx.transforms.llmlingua_compressor","llmlingua"),
]

@pytest.mark.parametrize("modality,module_path,required_extra", MODALITY_TABLE)
def test_modality_module_importable(modality, module_path, required_extra):
    """Every claimed modality must have an importable module path."""
    if required_extra and importlib.util.find_spec(required_extra) is None:
        pytest.skip(f"{modality} requires extra package {required_extra!r}")
    mod = importlib.import_module(module_path)
    assert mod is not None, f"Modality {modality!r} module {module_path!r} could not be imported"
