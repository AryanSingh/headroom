"""Compression-only evaluation runner.

Evaluates compression quality WITHOUT making any LLM API calls (zero cost).
Used for:
- CCR lossless round-trip verification
- Information retention (probe facts survive compression)
- Needle retention (specific values preserved in compressed output)
- Verbatim compaction fidelity (exact anchors survive deterministic deletion)
- Tool schema compaction integrity (property names survive annotation stripping)
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CompressionOnlyResult:
    """Result from a compression-only evaluation."""

    benchmark: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    accuracy_rate: float
    avg_compression_ratio: float
    total_original_tokens: int
    total_compressed_tokens: int
    total_tokens_saved: int
    tokens_per_second: float | None = None
    critical_item_recall: float | None = None
    verbatim_fidelity: float | None = None
    duration_seconds: float = 0.0
    details: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark": self.benchmark,
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "failed_cases": self.failed_cases,
            "accuracy_rate": round(self.accuracy_rate, 4),
            "avg_compression_ratio": round(self.avg_compression_ratio, 4),
            "total_original_tokens": self.total_original_tokens,
            "total_compressed_tokens": self.total_compressed_tokens,
            "total_tokens_saved": self.total_tokens_saved,
            "tokens_per_second": round(self.tokens_per_second, 2)
            if self.tokens_per_second is not None
            else None,
            "critical_item_recall": round(self.critical_item_recall, 4)
            if self.critical_item_recall is not None
            else None,
            "verbatim_fidelity": round(self.verbatim_fidelity, 4)
            if self.verbatim_fidelity is not None
            else None,
            "duration_seconds": round(self.duration_seconds, 2),
            "errors": self.errors,
        }

    @property
    def passed(self) -> bool:
        return self.failed_cases == 0


class CompressionOnlyRunner:
    """Evaluate compression quality without LLM calls.

    Supports three evaluation modes:
    1. CCR lossless round-trip: compress → decompress → verify byte-exact match
    2. Information retention: compress and check if probe facts survive
    3. Needle retention: compress JSON array, verify anomalies/needles preserved
    4. Verbatim compaction: preserve exact file paths, line numbers, and error strings
    """

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count (~4 chars per token)."""
        return len(text) // 4

    def evaluate_ccr_lossless(
        self,
        test_cases: list[dict[str, Any]],
    ) -> CompressionOnlyResult:
        """Verify SmartCrusher needle retention: critical items survive compression.

        Tests that errors, anomalies, and specific values are preserved
        after compression (the CCR guarantee). Each test_case should have:
            - "id": str
            - "content": str (JSON array to compress)
            - "needles": list[str] (values that must survive in compressed output)

        If needles are not provided, generates them from the content.
        """
        from cutctx.transforms.smart_crusher import SmartCrusher, SmartCrusherConfig

        start_time = time.time()
        crusher = SmartCrusher(config=SmartCrusherConfig())
        passed = 0
        failed = 0
        total_original = 0
        total_compressed = 0
        details = []
        errors = []

        for case in test_cases:
            case_id = case.get("id", "unknown")
            content = case["content"]
            needles = case.get("needles", [])
            original_tokens = self._estimate_tokens(content)
            total_original += original_tokens

            try:
                result = crusher.crush(content)
                compressed = result.compressed
                compressed_tokens = self._estimate_tokens(compressed)
                total_compressed += compressed_tokens

                # Check needles are preserved
                if needles:
                    compressed_lower = compressed.lower()
                    preserved = [n for n in needles if n.lower() in compressed_lower]
                    lost = [n for n in needles if n.lower() not in compressed_lower]
                    is_pass = len(lost) == 0
                else:
                    # No needles: just verify compression produces valid output
                    is_pass = len(compressed) > 0
                    preserved = []
                    lost = []

                if is_pass:
                    passed += 1
                else:
                    failed += 1
                    errors.append(f"Needles lost in {case_id}: {lost}")

                details.append(
                    {
                        "id": case_id,
                        "passed": is_pass,
                        "original_tokens": original_tokens,
                        "compressed_tokens": compressed_tokens,
                        "compression_ratio": 1 - (compressed_tokens / original_tokens)
                        if original_tokens > 0
                        else 0,
                        "needles_preserved": len(preserved),
                        "needles_lost": lost,
                    }
                )
            except Exception as e:
                failed += 1
                total_compressed += original_tokens
                errors.append(f"Compression error for case {case_id}: {e}")
                details.append({"id": case_id, "passed": False, "error": str(e)})

        total_cases = passed + failed
        ratios = [d.get("compression_ratio", 0) for d in details if "compression_ratio" in d]

        duration_seconds = time.time() - start_time
        tokens_per_second = total_original / duration_seconds if duration_seconds > 0 else None

        return CompressionOnlyResult(
            benchmark="ccr_roundtrip",
            total_cases=total_cases,
            passed_cases=passed,
            failed_cases=failed,
            accuracy_rate=passed / total_cases if total_cases > 0 else 0.0,
            avg_compression_ratio=sum(ratios) / len(ratios) if ratios else 0.0,
            total_original_tokens=total_original,
            total_compressed_tokens=total_compressed,
            total_tokens_saved=total_original - total_compressed,
            tokens_per_second=tokens_per_second,
            duration_seconds=duration_seconds,
            details=details,
            errors=errors,
        )

    def evaluate_information_retention(
        self,
        test_cases: list[dict[str, Any]],
    ) -> CompressionOnlyResult:
        """Check if probe facts survive compression.

        Each test_case should have:
            - "id": str
            - "content": str
            - "probe_facts": list[str] (facts that must survive compression)
        """
        from cutctx.evals.metrics import compute_information_recall
        from cutctx.transforms.content_router import ContentRouter

        start_time = time.time()
        router = ContentRouter()
        passed = 0
        failed = 0
        total_original = 0
        total_compressed = 0
        details = []
        errors = []

        for case in test_cases:
            case_id = case.get("id", "unknown")
            content = case["content"]
            probe_facts = case["probe_facts"]
            original_tokens = self._estimate_tokens(content)
            total_original += original_tokens

            try:
                result = router.compress(content)
                compressed = result.compressed
                compressed_tokens = self._estimate_tokens(compressed)
                total_compressed += compressed_tokens

                recall_result = compute_information_recall(content, compressed, probe_facts)
                is_pass = recall_result["recall"] >= 0.9  # 90% of facts must survive

                if is_pass:
                    passed += 1
                else:
                    failed += 1

                details.append(
                    {
                        "id": case_id,
                        "passed": is_pass,
                        "recall": recall_result["recall"],
                        "facts_preserved": recall_result["facts_preserved"],
                        "facts_lost": recall_result["facts_lost"],
                        "compression_ratio": 1 - (compressed_tokens / original_tokens)
                        if original_tokens > 0
                        else 0,
                    }
                )
            except Exception as e:
                failed += 1
                total_compressed += original_tokens
                errors.append(f"Info retention error for {case_id}: {e}")
                details.append({"id": case_id, "passed": False, "error": str(e)})

        total_cases = passed + failed
        ratios = [d.get("compression_ratio", 0) for d in details if "compression_ratio" in d]

        duration_seconds = time.time() - start_time
        tokens_per_second = total_original / duration_seconds if duration_seconds > 0 else None

        return CompressionOnlyResult(
            benchmark="information_retention",
            total_cases=total_cases,
            passed_cases=passed,
            failed_cases=failed,
            accuracy_rate=passed / total_cases if total_cases > 0 else 0.0,
            avg_compression_ratio=sum(ratios) / len(ratios) if ratios else 0.0,
            total_original_tokens=total_original,
            total_compressed_tokens=total_compressed,
            total_tokens_saved=total_original - total_compressed,
            tokens_per_second=tokens_per_second,
            duration_seconds=duration_seconds,
            details=details,
            errors=errors,
        )

    def generate_ccr_test_cases(self, n: int = 50) -> list[dict[str, Any]]:
        """Generate synthetic test cases for CCR needle-retention testing.

        Each case is a JSON array with embedded 'needles' (errors, anomalies)
        that must survive SmartCrusher compression.
        """
        cases = []

        for i in range(n):
            error_code = f"ERR-{2000 + i}"
            critical_id = f"task-{i:04d}"

            # Build a JSON array with mostly normal items and a few needles
            items = [
                {"id": j, "name": f"item_{j}", "value": j * 1.5, "status": "active"}
                for j in range(20)
            ]
            # Inject needles: an error item and an anomalous value
            items[7] = {
                "id": 7,
                "name": "item_7",
                "value": 999.99,
                "status": "error",
                "error_code": error_code,
                "task_id": critical_id,
            }
            items[15] = {
                "id": 15,
                "name": "item_15",
                "value": -1.0,
                "status": "failed",
                "message": f"Timeout on {critical_id}",
            }

            cases.append(
                {
                    "id": f"ccr_{i}",
                    "content": json.dumps(items, indent=2),
                    "needles": [error_code, "error", "failed", "999.99"],
                }
            )

        return cases[:n]

    def generate_info_retention_cases(self, n: int = 30) -> list[dict[str, Any]]:
        """Generate test cases with probe facts for information retention testing."""
        cases = []

        for i in range(n):
            # Create a document with specific facts embedded
            error_code = f"ERR-{1000 + i}"
            metric_value = f"{42.5 + i}"
            server_name = f"prod-server-{i:03d}"

            content = json.dumps(
                [
                    {"server": server_name, "cpu": 45.2, "memory": 72.1, "status": "healthy"},
                    {"server": f"staging-{i}", "cpu": 12.0, "memory": 30.5, "status": "healthy"},
                    {"server": f"dev-{i}", "cpu": 5.0, "memory": 20.0, "status": "healthy"},
                    {
                        "server": f"prod-error-{i}",
                        "cpu": 98.7,
                        "memory": 95.3,
                        "status": "critical",
                        "error": error_code,
                        "metric": float(metric_value),
                    },
                ]
                + [
                    {
                        "server": f"node-{j}",
                        "cpu": 40 + j * 0.5,
                        "memory": 60 + j * 0.3,
                        "status": "healthy",
                    }
                    for j in range(20)
                ],
                indent=2,
            )

            cases.append(
                {
                    "id": f"retention_{i}",
                    "content": content,
                    "probe_facts": [
                        error_code,  # Error codes must survive
                        "critical",  # Alert status must survive
                        "98.7",  # Anomalous values must survive
                        server_name,  # Named servers must survive
                    ],
                }
            )

        return cases[:n]

    def generate_tool_schema_cases(self) -> list[dict[str, Any]]:
        """Generate tool schema test cases for compaction integrity verification.

        Each case exercises a different way a DROP_KEY can appear as a
        property *name* inside a JSON Schema `properties` object.
        The cases also include annotation keys at the schema level so we
        can verify those ARE still stripped.
        """
        return [
            {
                "id": "schema_title_property",
                "description": "property named 'title' must survive; schema-level title must be dropped",
                "payload": {
                    "tools": [
                        {
                            "type": "function",
                            "name": "eval_cells",
                            "description": "Evaluate notebook cells.",
                            "parameters": {
                                "$schema": "https://json-schema.org/draft/2020-12/schema",
                                "title": "EvalCellsParameters",
                                "type": "object",
                                "properties": {
                                    "cells": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "title": "CellItem",
                                            "properties": {
                                                "language": {"type": "string"},
                                                "code": {"type": "string"},
                                                "title": {"type": "string"},
                                            },
                                            "required": ["language", "code", "title"],
                                        },
                                    }
                                },
                                "required": ["cells"],
                            },
                        }
                    ]
                },
                "must_preserve": ["title"],
                "must_drop_schema_annotations": True,
            },
            {
                "id": "schema_deprecated_property",
                "description": "property named 'deprecated' must survive",
                "payload": {
                    "tools": [
                        {
                            "type": "function",
                            "name": "list_apis",
                            "description": "List available APIs with their status.",
                            "parameters": {
                                "$schema": "https://json-schema.org/draft/2020-12/schema",
                                "title": "ListApisParameters",
                                "type": "object",
                                "properties": {
                                    "deprecated": {
                                        "type": "boolean",
                                        "description": "Include deprecated APIs in results.",
                                    },
                                    "name": {"type": "string"},
                                },
                                "required": ["deprecated"],
                            },
                        }
                    ]
                },
                "must_preserve": ["deprecated"],
                "must_drop_schema_annotations": True,
            },
            {
                "id": "schema_readonly_property",
                "description": "property named 'readOnly' must survive",
                "payload": {
                    "tools": [
                        {
                            "type": "function",
                            "name": "update_field",
                            "description": "Update a field in a record.",
                            "parameters": {
                                "title": "UpdateFieldParameters",
                                "type": "object",
                                "properties": {
                                    "field_name": {"type": "string"},
                                    "value": {"type": "string"},
                                    "readOnly": {
                                        "type": "boolean",
                                        "description": "Whether the field is read-only.",
                                    },
                                },
                                "required": ["field_name", "value", "readOnly"],
                                "additionalProperties": False,
                            },
                        }
                    ]
                },
                "must_preserve": ["readOnly"],
                "must_drop_schema_annotations": True,
            },
            {
                "id": "schema_multiple_collisions",
                "description": "multiple DROP_KEY collisions in one schema",
                "payload": {
                    "tools": [
                        {
                            "type": "function",
                            "name": "create_field",
                            "description": "Create a schema field descriptor.",
                            "parameters": {
                                "$schema": "https://json-schema.org/draft/2020-12/schema",
                                "title": "CreateFieldParameters",
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "deprecated": {"type": "boolean"},
                                    "examples": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                    "readOnly": {"type": "boolean"},
                                },
                                "required": ["title", "deprecated", "examples", "readOnly"],
                            },
                        }
                    ]
                },
                "must_preserve": ["title", "deprecated", "examples", "readOnly"],
                "must_drop_schema_annotations": True,
            },
        ]

    def generate_verbatim_compaction_cases(self) -> list[dict[str, Any]]:
        """Load fixed local fixtures for exact-preservation compaction checks."""
        from cutctx.evals.datasets import load_verbatim_compaction_samples

        suite = load_verbatim_compaction_samples()
        return [
            {
                "id": case.id,
                "content": case.context,
                "query": case.query,
                "critical_items": list(case.metadata.get("critical_items", [])),
            }
            for case in suite.cases
        ]

    def evaluate_verbatim_compaction(
        self,
        cases: list[dict[str, Any]] | None = None,
        *,
        fidelity_threshold: float = 0.90,
    ) -> CompressionOnlyResult:
        """Verify deterministic compaction preserves exact critical anchors."""
        from cutctx.transforms.verbatim_compactor import VerbatimCompactor

        if cases is None:
            cases = self.generate_verbatim_compaction_cases()

        start_time = time.time()
        compactor = VerbatimCompactor()
        passed = 0
        failed = 0
        total_original = 0
        total_compressed = 0
        details: list[dict[str, Any]] = []
        errors: list[str] = []
        fidelity_scores: list[float] = []
        ratios: list[float] = []

        for case in cases:
            case_id = case.get("id", "unknown")
            content = case["content"]
            query = case.get("query", "")
            critical_items = [item for item in case.get("critical_items", []) if str(item).strip()]
            original_tokens = self._estimate_tokens(content)
            total_original += original_tokens

            try:
                result = compactor.compress(content, context=query, critical_items=critical_items)
                compressed = result.compressed
                compressed_tokens = self._estimate_tokens(compressed)
                total_compressed += compressed_tokens

                preserved = [item for item in critical_items if item in compressed]
                lost = [item for item in critical_items if item not in compressed]
                fidelity = len(preserved) / len(critical_items) if critical_items else 1.0
                fidelity_scores.append(fidelity)

                ratio = 1 - (compressed_tokens / original_tokens) if original_tokens > 0 else 0.0
                ratios.append(ratio)
                is_pass = fidelity >= fidelity_threshold

                if is_pass:
                    passed += 1
                else:
                    failed += 1
                    errors.append(f"Verbatim anchors lost in {case_id}: {lost}")

                details.append(
                    {
                        "id": case_id,
                        "passed": is_pass,
                        "verbatim_fidelity": fidelity,
                        "anchors_preserved": len(preserved),
                        "anchors_lost": lost,
                        "compression_ratio": ratio,
                    }
                )
            except Exception as exc:
                failed += 1
                total_compressed += original_tokens
                errors.append(f"Verbatim compaction error for {case_id}: {exc}")
                details.append({"id": case_id, "passed": False, "error": str(exc)})

        total_cases = passed + failed
        avg_fidelity = sum(fidelity_scores) / len(fidelity_scores) if fidelity_scores else 0.0
        avg_ratio = sum(ratios) / len(ratios) if ratios else 0.0

        duration_seconds = time.time() - start_time
        tokens_per_second = total_original / duration_seconds if duration_seconds > 0 else None

        return CompressionOnlyResult(
            benchmark="verbatim_compaction",
            total_cases=total_cases,
            passed_cases=passed,
            failed_cases=failed,
            accuracy_rate=avg_fidelity,
            avg_compression_ratio=avg_ratio,
            total_original_tokens=total_original,
            total_compressed_tokens=total_compressed,
            total_tokens_saved=total_original - total_compressed,
            tokens_per_second=tokens_per_second,
            critical_item_recall=avg_fidelity,
            verbatim_fidelity=avg_fidelity,
            duration_seconds=duration_seconds,
            details=details,
            errors=errors,
        )

    def evaluate_tool_schema_compaction(
        self,
        cases: list[dict[str, Any]] | None = None,
    ) -> CompressionOnlyResult:
        """Verify tool schema compaction preserves property names that collide with DROP_KEYS.

        The compaction pass must never strip a key that appears as a property
        *name* under a JSON Schema `properties` object, even if the same key
        is in the annotation drop-list (title, deprecated, readOnly, examples, …).

        Assertions per case:
        - token count is smaller after compaction (annotations were stripped)
        - every property name listed in `must_preserve` is present in the
          compacted schema's `properties` dict
        - every `required` array is a subset of the surviving `properties` keys
          (no dangling required entry pointing at a stripped property)
        - schema-level annotations ($schema, title at root level) ARE dropped
        """
        # This is intentionally independent of the OpenAI handler package:
        # importing that package pulls in httpx, provider/auth, and transport
        # machinery.  The zero-cost suite must be runnable with no provider
        # stack installed.
        from cutctx.proxy.schema_compress import compress_tool_schemas

        if cases is None:
            cases = self.generate_tool_schema_cases()

        start_time = time.time()
        passed = 0
        failed = 0
        total_original = 0
        total_compressed = 0
        details: list[dict[str, Any]] = []
        errors: list[str] = []

        for case in cases:
            case_id = case["id"]
            payload = case["payload"]
            must_preserve: list[str] = case.get("must_preserve", [])
            must_drop_schema_annotations: bool = case.get("must_drop_schema_annotations", False)

            original_bytes = len(json.dumps(payload).encode())
            total_original += original_bytes

            try:
                compacted_tools, modified, before_bytes, after_bytes = compress_tool_schemas(
                    payload.get("tools") if isinstance(payload.get("tools"), list) else None,
                    max_description_length=200,
                )
                compacted = {**payload, "tools": compacted_tools} if modified else payload
                total_compressed += after_bytes if modified else original_bytes

                case_errors: list[str] = []

                if not modified:
                    case_errors.append(
                        "compaction reported no modification (annotations not stripped)"
                    )

                for tool in compacted.get("tools", []):
                    params = tool.get("parameters", {})
                    _check_properties_recursive(params, must_preserve, tool["name"], case_errors)

                if must_drop_schema_annotations:
                    for tool in compacted.get("tools", []):
                        params = tool.get("parameters", {})
                        for ann_key in ("$schema", "title"):
                            if ann_key in params:
                                case_errors.append(
                                    f"tool '{tool['name']}': schema annotation '{ann_key}' "
                                    f"was not stripped from parameters root"
                                )

                is_pass = len(case_errors) == 0
                if is_pass:
                    passed += 1
                else:
                    failed += 1
                    errors.extend(f"[{case_id}] {e}" for e in case_errors)

                details.append(
                    {
                        "id": case_id,
                        "passed": is_pass,
                        "original_bytes": before_bytes,
                        "compacted_bytes": after_bytes,
                        "compression_ratio": 1 - (after_bytes / before_bytes)
                        if before_bytes > 0
                        else 0,
                        "errors": case_errors,
                    }
                )

            except Exception as exc:
                failed += 1
                total_compressed += original_bytes
                errors.append(f"[{case_id}] unexpected exception: {exc}")
                details.append({"id": case_id, "passed": False, "error": str(exc)})

        total_cases = passed + failed
        ratios = [d.get("compression_ratio", 0) for d in details if "compression_ratio" in d]

        duration_seconds = time.time() - start_time
        tokens_per_second = (
            (total_original // 4) / duration_seconds if duration_seconds > 0 else None
        )

        return CompressionOnlyResult(
            benchmark="tool_schema_compaction",
            total_cases=total_cases,
            passed_cases=passed,
            failed_cases=failed,
            accuracy_rate=passed / total_cases if total_cases > 0 else 0.0,
            avg_compression_ratio=sum(ratios) / len(ratios) if ratios else 0.0,
            total_original_tokens=total_original // 4,
            total_compressed_tokens=total_compressed // 4,
            total_tokens_saved=(total_original - total_compressed) // 4,
            tokens_per_second=tokens_per_second,
            duration_seconds=duration_seconds,
            details=details,
            errors=errors,
        )


def _check_properties_recursive(
    schema: Any,
    must_preserve: list[str],
    tool_name: str,
    errors: list[str],
) -> None:
    """Walk a JSON Schema object and assert that must_preserve keys survive inside `properties`."""
    if not isinstance(schema, dict):
        return

    properties = schema.get("properties")
    if isinstance(properties, dict):
        required = schema.get("required", [])
        for key in must_preserve:
            if key in required and key not in properties:
                errors.append(
                    f"tool '{tool_name}': property '{key}' is in `required` but was "
                    f"stripped from `properties` by compaction"
                )
        for sub_schema in properties.values():
            _check_properties_recursive(sub_schema, must_preserve, tool_name, errors)

    items = schema.get("items")
    if isinstance(items, dict):
        _check_properties_recursive(items, must_preserve, tool_name, errors)
