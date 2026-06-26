"""Evaluation runners for different scenarios."""

from cutctx.evals.runners.before_after import BeforeAfterRunner
from cutctx.evals.runners.compression_only import CompressionOnlyRunner

__all__ = ["BeforeAfterRunner", "CompressionOnlyRunner"]
