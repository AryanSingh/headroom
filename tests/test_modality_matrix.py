"""Modality matrix verification.

These tests keep externally claimed data modalities aligned with an
importable implementation path or an explicit pass-through policy.
"""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

import pytest


def test_log_compressor_importable() -> None:
    mod = importlib.import_module("cutctx.transforms.log_compressor")
    assert hasattr(mod, "LogCompressor")


def test_diff_compressor_importable() -> None:
    mod = importlib.import_module("cutctx.transforms.diff_compressor")
    assert mod is not None


def test_search_compressor_importable() -> None:
    mod = importlib.import_module("cutctx.transforms.search_compressor")
    assert mod is not None


def test_code_compressor_importable() -> None:
    mod = importlib.import_module("cutctx.transforms.code_compressor")
    assert mod is not None


def test_image_compressor_importable() -> None:
    mod = importlib.import_module("cutctx.image.compressor")
    assert mod is not None


def test_drain3_compressor_importable() -> None:
    mod = importlib.import_module("cutctx.transforms.drain3_compressor")
    assert mod is not None


@pytest.mark.skipif(
    importlib.util.find_spec("drain3") is None,
    reason="drain3 not installed — pip install cutctx-ai[log-ml]",
)
def test_drain3_available_function() -> None:
    from cutctx.transforms.drain3_compressor import drain3_available

    assert drain3_available() is not None


def test_kompress_compressor_importable() -> None:
    mod = importlib.import_module("cutctx.transforms.kompress_compressor")
    assert mod is not None


def test_llmlingua_compressor_importable() -> None:
    mod = importlib.import_module("cutctx.transforms.llmlingua_compressor")
    assert mod is not None


def test_feature_availability_snapshot_structure() -> None:
    """The runtime capability snapshot should expose canonical feature keys."""
    spec = importlib.util.find_spec("cutctx.proxy.server")
    assert spec is not None, "cutctx.proxy.server must be importable"

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
    server_src = Path("cutctx/proxy/server.py").read_text()
    for key in required_keys:
        assert (
            f'"{key}"' in server_src
        ), f"feature_availability snapshot missing key {key!r} in cutctx/proxy/server.py"


def test_audio_modality_is_passthrough() -> None:
    """Audio routes exist but are explicitly documented as pass-through."""
    server_src = Path("cutctx/proxy/server.py").read_text()
    assert "pass-through" in server_src, (
        "Audio must be documented as pass-through in _feature_availability_snapshot(). "
        "We proxy /v1/audio/* routes without token compression."
    )


def test_audio_proxy_routes_present() -> None:
    """The proxy exposes /v1/audio/* pass-through routes."""
    routes_src = Path("cutctx/providers/proxy_routes.py").read_text()
    assert "/v1/audio/transcriptions" in routes_src
    assert "/v1/audio/speech" in routes_src


def test_enterprise_doc_matches_audio_passthrough_claim() -> None:
    """Public enterprise docs should not advertise audio compression."""
    enterprise_doc = Path("docs/enterprise.html").read_text()
    assert "audio pass-through" in enterprise_doc
    assert "images, audio</td>" not in enterprise_doc


def test_pyproject_has_recommended_extra() -> None:
    toml = Path("pyproject.toml").read_text()
    assert "recommended" in toml, (
        "pyproject.toml must define a [recommended] extras group for production installs"
    )


def test_pyproject_has_full_extra() -> None:
    toml = Path("pyproject.toml").read_text()
    assert "full" in toml, (
        "pyproject.toml must define a [full] extras group for complete production installs"
    )


MODALITY_TABLE = [
    ("prose/text", "cutctx.compress", None),
    ("code", "cutctx.transforms.code_compressor", None),
    ("logs", "cutctx.transforms.log_compressor", None),
    ("diffs", "cutctx.transforms.diff_compressor", None),
    ("search output", "cutctx.transforms.search_compressor", None),
    ("images", "cutctx.image.compressor", "PIL"),
    ("log ML (drain3)", "cutctx.transforms.drain3_compressor", "drain3"),
    ("kompress (ONNX)", "cutctx.transforms.kompress_compressor", "onnxruntime"),
    ("llmlingua", "cutctx.transforms.llmlingua_compressor", "llmlingua"),
]


@pytest.mark.parametrize("modality,module_path,required_extra", MODALITY_TABLE)
def test_modality_module_importable(
    modality: str, module_path: str, required_extra: str | None
) -> None:
    """Every claimed modality should have an importable module path."""
    if required_extra and importlib.util.find_spec(required_extra) is None:
        pytest.skip(f"{modality} requires extra package {required_extra!r}")

    mod = importlib.import_module(module_path)
    assert mod is not None, (
        f"Modality {modality!r} module path {module_path!r} could not be imported"
    )
