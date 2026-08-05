from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
GOVERNANCE = (
    "handbook-charter.md",
    "roles-and-accountability.md",
    "evidence-standard.md",
    "risk-severity-model.md",
    "exception-management.md",
)
TEMPLATES = (
    "audit-report.md",
    "evidence-register.md",
    "finding.md",
    "release-decision.md",
    "incident-review.md",
    "threat-model.md",
    "migration-plan.md",
    "benchmark-report.md",
    "ai-evaluation-report.md",
    "verification-plan.md",
    "executive-summary.md",
)


def _metadata(path: Path) -> dict:
    _, front_matter, _ = path.read_text(encoding="utf-8").split("---\n", 2)
    return yaml.safe_load(front_matter)


def test_governance_documents_and_complete_template_examples_exist() -> None:
    for name in GOVERNANCE:
        content = (ROOT / "governance" / name).read_text(encoding="utf-8")
        assert content.startswith("# ")
        assert "Product Atlas" in content
    for name in TEMPLATES:
        path = ROOT / "templates" / name
        metadata = _metadata(path)
        content = path.read_text(encoding="utf-8")
        assert metadata["kind"] == "template"
        assert metadata["field_instructions"]
        assert metadata["completed_example"]
        assert "## Completed example" in content
        assert "Product Atlas" in content
