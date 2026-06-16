"""ONNX-based injection classifier for the LLM Firewall.

Runs on CPU in <20ms. Falls back to heuristic scanner if model not available.

Usage:
    # Export model (one-time):
    python scripts/export_firewall_model.py

    # Use in code:
    from headroom.security.firewall_ml import MLInjectionClassifier
    clf = MLInjectionClassifier()
    if clf.is_injection("ignore previous instructions"):
        ...
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_MODEL_DIR = Path(__file__).parent / "models"


class MLInjectionClassifier:
    """ONNX-based injection classifier. Runs on CPU in <20ms.

    Falls back gracefully if model files or onnxruntime are not available.
    """

    _instance: MLInjectionClassifier | None = None

    def __init__(self, model_dir: Path | None = None) -> None:
        self._available = False
        self._session = None
        self._tokenizer = None

        model_dir = model_dir or _DEFAULT_MODEL_DIR
        onnx_path = model_dir / "injection_classifier.onnx"
        tokenizer_path = model_dir / "tokenizer"

        if not onnx_path.exists():
            logger.debug(
                "Firewall ML model not found at %s. "
                "Run: python scripts/export_firewall_model.py to enable.",
                onnx_path,
            )
            return

        try:
            import onnxruntime as ort  # noqa: F811
            from transformers import AutoTokenizer  # noqa: F811

            self._session = ort.InferenceSession(
                str(onnx_path),
                providers=["CPUExecutionProvider"],
            )
            self._tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_path))
            self._available = True
            logger.info("Firewall ML classifier loaded from %s", model_dir)
        except ImportError:
            logger.warning(
                "onnxruntime not installed -- ML firewall disabled. "
                "Install: pip install onnxruntime"
            )
        except Exception as exc:
            logger.warning("Failed to load ML firewall model: %s", exc)

    @classmethod
    def get_instance(cls) -> MLInjectionClassifier:
        """Get or create singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (for testing)."""
        cls._instance = None

    @property
    def available(self) -> bool:
        return self._available

    def score(self, text: str) -> float:
        """Returns injection probability 0.0-1.0. Fast: ~15ms on CPU."""
        if not self._available or self._session is None or self._tokenizer is None:
            return 0.0

        import numpy as np

        tokens = self._tokenizer(
            text,
            return_tensors="np",
            padding=True,
            truncation=True,
            max_length=512,
        )
        logits = self._session.run(
            ["logits"],
            {
                "input_ids": tokens["input_ids"],
                "attention_mask": tokens["attention_mask"],
            },
        )[0]
        # Class 1 = injection
        exp_logits = np.exp(logits - logits.max(axis=-1, keepdims=True))
        probs = exp_logits / exp_logits.sum(axis=-1, keepdims=True)
        return float(probs[0][1])

    def is_injection(self, text: str, threshold: float = 0.85) -> bool:
        """Check if text is an injection attempt."""
        return self.score(text) >= threshold

    def score_batch(self, texts: list[str]) -> list[float]:
        """Score multiple texts at once."""
        return [self.score(t) for t in texts]
