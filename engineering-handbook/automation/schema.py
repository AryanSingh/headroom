"""Stable schema constants and result types for handbook automation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

SEVERITIES = {"error", "warning"}


@dataclass(frozen=True)
class Finding:
    code: str
    path: Path
    message: str
    severity: str = "error"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["path"] = self.path.as_posix()
        return payload


@dataclass(frozen=True)
class ExampleResult:
    example_id: str
    manifest: Path
    status: str
    message: str
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    timed_out: bool = False
    cleanup_exit_codes: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["manifest"] = self.manifest.as_posix()
        return payload


CHAPTER_METADATA_FIELDS = (
    "id",
    "kind",
    "title",
    "purpose",
    "audience",
    "scope",
    "applicability",
    "owners",
    "inputs",
    "outputs",
    "dependencies",
)

CHAPTER_SECTIONS = {
    "CHAPTER_OVERVIEW_MISSING": ("purpose, audience, scope, and applicability",),
    "CHAPTER_CONCEPTS_MISSING": ("concepts and engineering principles",),
    "CHAPTER_ROLES_MISSING": ("roles and accountability",),
    "CHAPTER_PREREQUISITES_MISSING": ("prerequisites and required inputs",),
    "CHAPTER_SOP_MISSING": ("standard operating procedure",),
    "CHAPTER_WORKED_EXAMPLE_MISSING": ("worked example",),
    "CHAPTER_AUTOMATION_MISSING": ("automation examples",),
    "CHAPTER_CHECKLIST_MISSING": ("workflow checklist", "checklist"),
    "CHAPTER_EVIDENCE_MISSING": ("evidence requirements and retention guidance",),
    "CHAPTER_FINDINGS_MISSING": ("example findings with severity and remediation",),
    "CHAPTER_KPI_MISSING": ("kpis and domain scorecard", "kpis", "scorecard"),
    "CHAPTER_FAILURE_PATTERNS_MISSING": (
        "common failure patterns and diagnostic guidance",
        "failure patterns",
    ),
    "CHAPTER_EXIT_CRITERIA_MISSING": ("exit criteria",),
    "CHAPTER_RELATED_ASSETS_MISSING": (
        "related runbooks, controls, examples, and templates",
        "related assets",
    ),
}

WORKED_EXAMPLE_FIELDS = (
    "preconditions",
    "placement",
    "dependencies",
    "invocation",
    "expected_output",
    "failure_output",
    "interpretation",
    "remediation",
    "cleanup",
)

PROMPT_FIELDS = (
    "id",
    "kind",
    "chapter",
    "model_family",
    "workload_type",
    "objective",
    "inputs",
    "boundaries",
    "evidence",
    "output_schema",
    "uncertainty",
    "stop_conditions",
    "escalation",
)

CONTROL_FIELDS = (
    "id",
    "requirement",
    "applicability",
    "procedure",
    "expected_result",
    "evidence",
    "automation",
    "owner",
    "frequency",
    "failure_action",
    "standards",
)

RUNBOOK_FIELDS = (
    "triggers",
    "severity",
    "roles",
    "prerequisites",
    "decisions",
    "communication",
    "containment_or_rollback",
    "evidence",
    "recovery",
    "exit_criteria",
    "follow_up",
)

KPI_FIELDS = (
    "id",
    "name",
    "decision",
    "calculation",
    "source",
    "frequency",
    "owner",
    "target",
    "warning",
    "distortions",
    "anti_gaming",
    "interpretation",
)

TEMPLATE_FIELDS = ("field_instructions", "completed_example")

STANDARD_FIELDS = (
    "id",
    "publisher",
    "title",
    "version",
    "publication_date",
    "official_url",
    "retrieved",
    "scope",
    "status",
    "control_families",
    "copyright_note",
    "refresh_policy",
)

EXAMPLE_MANIFEST_FIELDS = (
    "schema_version",
    "id",
    "title",
    "command",
    "timeout_seconds",
    "cleanup",
    "dependencies",
    "fixtures",
    "expected_output",
    "offline",
    "mutable_network",
    "environment",
)
