from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest
import validate_handbook as validator
import yaml
from validate_handbook import Finding, load_manifest, main, validate_handbook

CHAPTER_META = {
    "id": "CH-01",
    "kind": "chapter",
    "title": "Operating manual",
    "purpose": "Define the operating model.",
    "audience": ["staff engineers"],
    "scope": "Engineering review work.",
    "applicability": "All handbook users.",
    "owners": ["Engineering Enablement"],
    "inputs": ["approved audit brief"],
    "outputs": ["review evidence"],
    "dependencies": ["NIST-SSDF-1.1"],
    "standards": ["NIST-SSDF-1.1"],
}


COMPLETE_CHAPTER = """
# Operating manual {#operating-manual}

## Purpose, audience, scope, and applicability
This chapter is required for teams applying [NIST SSDF](../standards/README.md#nist-ssdf).

## Concepts and engineering principles
Use reproducible evidence.

## Roles and accountability
The owner approves the result.

## Prerequisites and required inputs
Start from an approved brief.

## Standard operating procedure
1. Collect evidence.
2. Record decisions.

## Worked example
### Preconditions
Use the fixture repository.
### Placement
Place files in a temporary checkout.
### Dependencies
Python 3.12.
### Invocation
`python example.py`
### Expected output
The command prints `pass`.
### Failure output
The command prints `fail`.
### Interpretation
`pass` means the evidence is complete.
### Remediation
Add the missing evidence.
### Cleanup
Remove the temporary checkout.

## Automation examples
Dependencies, placement, invocation, expected output, limits, and cleanup are stated above.

## Audit prompts
### Opus prompt
Workload: cross-system architecture synthesis. Output: risk-ranked decision record.
### Sonnet prompt
Workload: focused evidence review. Output: reproducible finding list.
### Haiku prompt
Workload: mechanical evidence inventory. Output: normalized checklist rows.

## Workflow checklist
Evidence, frequency, owner, and failure action are defined in the linked control.

## Evidence requirements and retention guidance
Retain command output for one release cycle.

## Example findings with severity and remediation
Important: missing evidence. Remediation: rerun the procedure.

## KPIs and domain scorecard
Track review completion.

## Common failure patterns and diagnostic guidance
Missing inputs cause incomplete reviews.

## Exit criteria
All blocking findings are closed.

## Related runbooks, controls, examples, and templates
See the linked assets in the manifest.
"""


def add_manifest(root: Path, entries: list[str]) -> None:
    lines = ["# Summary", ""] + [f"- [Item]({entry})" for entry in entries]
    (root / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def codes(findings: list[Finding]) -> list[str]:
    return [finding.code for finding in findings]


def test_load_manifest_uses_markdown_links_and_ignores_code(handbook: Path) -> None:
    (handbook / "chapters").mkdir()
    (handbook / "chapters" / "one.md").write_text("# One\n", encoding="utf-8")
    (handbook / "SUMMARY.md").write_text(
        "# Summary\n\n- [One](chapters/one.md)\n\n```md\n[Fake](missing.md)\n```\n",
        encoding="utf-8",
    )

    assert load_manifest(handbook) == [Path("chapters/one.md")]


def test_complete_chapter_has_no_chapter_contract_findings(handbook: Path, write_md) -> None:
    write_md(handbook, "chapters/01.md", CHAPTER_META, COMPLETE_CHAPTER)
    (handbook / "standards" / "README.md").write_text(
        "# Standards\n\n## NIST SSDF {#nist-ssdf}\n", encoding="utf-8"
    )
    add_manifest(handbook, ["chapters/01.md", "standards/README.md"])

    findings = validate_handbook(handbook)

    assert not [finding for finding in findings if finding.code.startswith("CHAPTER_")]


@pytest.mark.parametrize(
    ("heading", "code"),
    [
        ("Worked example", "CHAPTER_WORKED_EXAMPLE_MISSING"),
        ("Opus prompt", "CHAPTER_OPUS_PROMPT_MISSING"),
        ("Sonnet prompt", "CHAPTER_SONNET_PROMPT_MISSING"),
        ("Haiku prompt", "CHAPTER_HAIKU_PROMPT_MISSING"),
        ("Workflow checklist", "CHAPTER_CHECKLIST_MISSING"),
        ("KPIs and domain scorecard", "CHAPTER_KPI_MISSING"),
        ("Exit criteria", "CHAPTER_EXIT_CRITERIA_MISSING"),
    ],
)
def test_incomplete_chapter_reports_each_missing_contract_element(
    handbook: Path, write_md, heading: str, code: str
) -> None:
    body = COMPLETE_CHAPTER.replace(f"## {heading}\n", "## Removed section\n", 1)
    if "prompt" in heading.lower():
        body = COMPLETE_CHAPTER.replace(f"### {heading}\n", "### Removed prompt\n", 1)
    write_md(handbook, "chapters/01.md", CHAPTER_META, body)
    add_manifest(handbook, ["chapters/01.md"])

    assert code in codes(validate_handbook(handbook))


def test_linked_split_assets_satisfy_chapter_contract(handbook: Path, write_md) -> None:
    chapter = COMPLETE_CHAPTER.replace(
        "## Worked example\n",
        "## Worked example\nSee [complete example](../examples/complete.md).\n\n",
    )
    chapter = chapter.replace("### Preconditions", "### Summary")
    write_md(handbook, "chapters/01.md", CHAPTER_META, chapter)
    write_md(
        handbook,
        "examples/complete.md",
        {
            "id": "EX-01",
            "kind": "worked-example",
            "chapter": "CH-01",
            "preconditions": ["fixture repository"],
            "placement": "temporary checkout",
            "dependencies": ["Python 3.12"],
            "invocation": "python example.py",
            "expected_output": "pass",
            "failure_output": "fail",
            "interpretation": "pass is complete",
            "remediation": "add evidence",
            "cleanup": "remove checkout",
        },
        "# Complete example\n",
    )
    add_manifest(handbook, ["chapters/01.md", "examples/complete.md"])

    assert "WORKED_EXAMPLE_FIELD_MISSING" not in codes(validate_handbook(handbook))


def test_unrelated_linked_chapter_cannot_satisfy_contract(handbook: Path, write_md) -> None:
    write_md(handbook, "chapters/01.md", CHAPTER_META, "# Thin chapter\n\nSee [other](02.md).")
    other_meta = dict(CHAPTER_META, id="CH-02", title="Other chapter")
    write_md(handbook, "chapters/02.md", other_meta, COMPLETE_CHAPTER)
    (handbook / "standards" / "README.md").write_text("# Standards\n\n## NIST SSDF {#nist-ssdf}\n")
    add_manifest(handbook, ["chapters/01.md", "chapters/02.md"])

    found = codes(validate_handbook(handbook))

    assert "CHAPTER_SOP_MISSING" in found
    assert "CHAPTER_OPUS_PROMPT_MISSING" in found


def test_linked_prompt_must_belong_to_the_chapter(handbook: Path, write_md) -> None:
    chapter = COMPLETE_CHAPTER.replace("### Opus prompt", "### Removed prompt", 1)
    chapter = chapter.replace("## Audit prompts", "## Audit prompts\n[Opus](../prompts/opus.md)")
    write_md(handbook, "chapters/01.md", CHAPTER_META, chapter)
    prompt = {
        "id": "PROMPT-OTHER-OPUS-01", "kind": "prompt", "chapter": "CH-02",
        "model_family": "opus", "workload_type": "architecture review",
        "objective": "Review architecture", "inputs": ["evidence"],
        "boundaries": ["local files"], "evidence": ["paths"],
        "output_schema": {"type": "report"}, "uncertainty": "Mark unknowns.",
        "stop_conditions": ["missing evidence"], "escalation": "Ask the owner.",
    }
    write_md(handbook, "prompts/opus.md", prompt, "# Opus")
    (handbook / "standards" / "README.md").write_text("# Standards\n\n## NIST SSDF {#nist-ssdf}\n")
    add_manifest(handbook, ["chapters/01.md", "prompts/opus.md"])

    assert "CHAPTER_OPUS_PROMPT_MISSING" in codes(validate_handbook(handbook))


def test_duplicate_control_and_kpi_ids_are_reported_once_each(handbook: Path, write_md) -> None:
    body = "# Catalog\n\nSEC-AUTH-001 appears here.\n\nSEC-AUTH-001 appears again.\n\nKPI-REL-001 and KPI-REL-001."
    write_md(handbook, "checklists/catalog.md", {"id": "CAT-01", "kind": "catalog"}, body)
    add_manifest(handbook, ["checklists/catalog.md"])

    findings = validate_handbook(handbook)

    assert [finding.message for finding in findings if finding.code == "DUPLICATE_CONTROL_ID"] == [
        "Control ID SEC-AUTH-001 appears 2 times."
    ]
    assert [finding.message for finding in findings if finding.code == "DUPLICATE_KPI_ID"] == [
        "KPI ID KPI-REL-001 appears 2 times."
    ]


def test_duplicate_ids_in_structured_catalogs_are_reported(handbook: Path, write_md) -> None:
    control = {field: "value" for field in validator.CONTROL_FIELDS}
    control["id"] = "SEC-DATA-001"
    kpi = {field: "value" for field in validator.KPI_FIELDS}
    kpi["id"] = "KPI-DATA-001"
    write_md(
        handbook,
        "checklists/structured.md",
        {"id": "CL-01", "kind": "checklist", "controls": [control, dict(control)]},
        "# Structured controls",
    )
    write_md(
        handbook,
        "chapters/structured-kpis.md",
        {"id": "KCAT-01", "kind": "kpi-catalog", "kpis": [kpi, dict(kpi)]},
        "# Structured KPIs",
    )
    add_manifest(handbook, ["checklists/structured.md", "chapters/structured-kpis.md"])

    found = codes(validate_handbook(handbook))

    assert "DUPLICATE_CONTROL_ID" in found
    assert "DUPLICATE_KPI_ID" in found


def test_network_standard_link_check_reports_unreachable_urls(handbook: Path, monkeypatch) -> None:
    monkeypatch.setattr(validator, "_url_reachable", lambda url, timeout: False)

    findings = validator.check_standard_links(handbook)

    assert {finding.code for finding in findings} == {"STANDARD_URL_UNREACHABLE"}


def test_control_standard_references_must_exist_in_registry(handbook: Path, write_md) -> None:
    control = {field: "value" for field in validator.CONTROL_FIELDS}
    control["id"] = "SEC-AUTH-001"
    control["standards"] = ["UNKNOWN-STD"]
    write_md(
        handbook,
        "checklists/controls.md",
        {"id": "CL-01", "kind": "checklist", "controls": [control]},
        "# Controls",
    )
    add_manifest(handbook, ["checklists/controls.md"])

    assert "STANDARD_REFERENCE_UNKNOWN" in codes(validate_handbook(handbook))


def test_code_fences_do_not_create_duplicate_ids_or_placeholders(handbook: Path, write_md) -> None:
    write_md(
        handbook,
        "checklists/catalog.md",
        {"id": "CAT-01", "kind": "catalog"},
        "# Catalog\n\nSEC-AUTH-001\n\n```text\nSEC-AUTH-001 TODO TBD\n```",
    )
    add_manifest(handbook, ["checklists/catalog.md"])

    findings = validate_handbook(handbook)

    assert "DUPLICATE_CONTROL_ID" not in codes(findings)
    assert "FORBIDDEN_PLACEHOLDER" not in codes(findings)


def test_links_anchors_images_manifest_and_orphans_are_validated(handbook: Path, write_md) -> None:
    write_md(
        handbook,
        "chapters/links.md",
        {"id": "REF-01", "kind": "reference"},
        "# Links\n\n[missing](missing.md) [anchor](target.md#missing) ![diagram](missing.png)",
    )
    write_md(handbook, "chapters/target.md", {"id": "REF-02", "kind": "reference"}, "# Target")
    write_md(handbook, "chapters/orphan.md", {"id": "REF-03", "kind": "reference"}, "# Orphan")
    add_manifest(handbook, ["chapters/links.md", "chapters/target.md", "chapters/not-there.md"])

    found = codes(validate_handbook(handbook))

    assert "MANIFEST_FILE_MISSING" in found
    assert "ORPHAN_CANONICAL_FILE" in found
    assert "LOCAL_LINK_MISSING" in found
    assert "ANCHOR_MISSING" in found
    assert "IMAGE_MISSING" in found


def test_malformed_metadata_and_required_asset_contracts(handbook: Path, write_md) -> None:
    write_md(
        handbook, "runbooks/bad.md", {"id": "RB-01", "kind": "runbook", "triggers": []}, "# Runbook"
    )
    write_md(
        handbook,
        "checklists/bad.md",
        {
            "id": "CL-01",
            "kind": "checklist",
            "controls": [{"id": "SEC-AUTH-001", "requirement": "Authenticate users"}],
        },
        "# Checklist",
    )
    write_md(
        handbook,
        "templates/bad.md",
        {"id": "TPL-01", "kind": "template", "field_instructions": []},
        "# Template",
    )
    write_md(
        handbook,
        "chapters/kpi.md",
        {"id": "KPI-CAT", "kind": "kpi-catalog", "kpis": [{"id": "KPI-REL-001", "name": "SLO"}]},
        "# KPI",
    )
    entries = ["runbooks/bad.md", "checklists/bad.md", "templates/bad.md", "chapters/kpi.md"]
    add_manifest(handbook, entries)

    found = codes(validate_handbook(handbook))

    assert "RUNBOOK_FIELD_MISSING" in found
    assert "CONTROL_FIELD_MISSING" in found
    assert "TEMPLATE_FIELD_MISSING" in found
    assert "KPI_FIELD_MISSING" in found


def test_prompt_metadata_and_family_distinctness(handbook: Path, write_md) -> None:
    base = {
        "kind": "prompt",
        "chapter": "CH-01",
        "objective": "Review evidence",
        "inputs": ["evidence"],
        "boundaries": ["local files only"],
        "evidence": ["file paths"],
        "output_schema": "finding list",
        "uncertainty": "mark unknowns",
        "stop_conditions": ["missing inputs"],
        "escalation": "ask the owner",
        "workload_type": "same workload",
    }
    entries = []
    for family in ("opus", "sonnet", "haiku"):
        meta = dict(base, id=f"PROMPT-{family.upper()}-01", model_family=family)
        relative = f"prompts/{family}/01.md"
        write_md(handbook, relative, meta, f"# {family.title()} prompt")
        entries.append(relative)
    add_manifest(handbook, entries)

    found = codes(validate_handbook(handbook))

    assert "PROMPT_FAMILIES_NOT_DISTINCT" in found
    assert "PROMPT_FIELD_MISSING" not in found


@pytest.mark.parametrize("field", ["workload_type", "output_schema"])
def test_prompt_family_rejects_duplicate_workload_or_output_declaration(
    handbook: Path, write_md, field: str
) -> None:
    base = {
        "kind": "prompt", "chapter": "CH-01", "objective": "Review evidence",
        "inputs": ["evidence"], "boundaries": ["local files only"],
        "evidence": ["file paths"], "output_schema": {"type": "finding-list"},
        "uncertainty": "mark unknowns", "stop_conditions": ["missing inputs"],
        "escalation": "ask the owner",
    }
    entries = []
    for index, family in enumerate(("opus", "sonnet", "haiku")):
        meta = dict(base, id=f"PROMPT-{family.upper()}-01", model_family=family)
        meta["workload_type"] = "same workload" if field == "workload_type" else f"workload-{index}"
        meta["output_schema"] = {"type": "same"} if field == "output_schema" else {"type": f"output-{index}"}
        relative = f"prompts/{family}/01.md"
        write_md(handbook, relative, meta, f"# {family.title()} prompt")
        entries.append(relative)
    add_manifest(handbook, entries)

    assert "PROMPT_FAMILIES_NOT_DISTINCT" in codes(validate_handbook(handbook))


def test_registry_requires_versioned_header(handbook: Path) -> None:
    registry_path = handbook / "standards" / "registry.yaml"
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    registry.pop("schema_version")
    registry_path.write_text(yaml.safe_dump(registry), encoding="utf-8")
    add_manifest(handbook, [])

    assert "STANDARDS_REGISTRY_INVALID" in codes(validate_handbook(handbook))


def test_standards_references_and_uncited_normative_claims(handbook: Path, write_md) -> None:
    write_md(
        handbook,
        "chapters/normative.md",
        {"id": "REF-01", "kind": "reference", "standards": ["UNKNOWN-STD"]},
        "# Normative\n\nTeams must retain evidence.",
    )
    add_manifest(handbook, ["chapters/normative.md"])

    found = codes(validate_handbook(handbook))

    assert "STANDARD_REFERENCE_UNKNOWN" in found
    assert "NORMATIVE_CLAIM_UNCITED" in found


def test_valid_suppression_hides_finding_and_expired_suppression_fails(
    handbook: Path, write_md
) -> None:
    write_md(
        handbook, "chapters/draft.md", {"id": "REF-01", "kind": "reference"}, "# Draft\n\nTODO"
    )
    add_manifest(handbook, ["chapters/draft.md"])
    metadata = yaml.safe_load((handbook / "metadata.yaml").read_text(encoding="utf-8"))
    metadata["suppressions"] = [
        {
            "id": "SUP-001",
            "code": "FORBIDDEN_PLACEHOLDER",
            "path": "chapters/draft.md",
            "reason": "Drafting exception",
            "owner": "Docs lead",
            "expires": (date.today() + timedelta(days=1)).isoformat(),
        }
    ]
    (handbook / "metadata.yaml").write_text(yaml.safe_dump(metadata), encoding="utf-8")
    assert "FORBIDDEN_PLACEHOLDER" not in codes(validate_handbook(handbook))

    metadata["suppressions"][0]["expires"] = (date.today() - timedelta(days=1)).isoformat()
    (handbook / "metadata.yaml").write_text(yaml.safe_dump(metadata), encoding="utf-8")
    assert "SUPPRESSION_EXPIRED" in codes(validate_handbook(handbook))


def test_cli_exit_codes_and_json_output(handbook: Path, write_md, capsys) -> None:
    add_manifest(handbook, [])
    assert main([str(handbook), "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out) == []

    write_md(
        handbook, "chapters/draft.md", {"id": "REF-01", "kind": "reference"}, "# Draft\n\nTODO"
    )
    add_manifest(handbook, ["chapters/draft.md"])
    assert main([str(handbook), "--format", "json"]) == 1

    metadata = yaml.safe_load((handbook / "metadata.yaml").read_text(encoding="utf-8"))
    metadata["validation"] = {"orphan_severity": "warning"}
    (handbook / "metadata.yaml").write_text(yaml.safe_dump(metadata), encoding="utf-8")
    (handbook / "chapters" / "draft.md").unlink()
    write_md(handbook, "chapters/orphan.md", {"id": "REF-02", "kind": "reference"}, "# Orphan")
    add_manifest(handbook, [])
    assert main([str(handbook), "--format", "json"]) == 2

    assert main([str(handbook / "missing"), "--format", "json"]) == 3


def test_mermaid_compilation_failure_is_reported(handbook: Path, write_md, monkeypatch) -> None:
    write_md(
        handbook,
        "chapters/diagram.md",
        {"id": "REF-01", "kind": "reference"},
        "# Diagram\n\n```mermaid\ngraph TD\nA -->\n```",
    )
    add_manifest(handbook, ["chapters/diagram.md"])
    monkeypatch.setenv("HANDBOOK_MERMAID_COMMAND", "false")

    assert "MERMAID_COMPILE_FAILED" in codes(validate_handbook(handbook))


def test_mermaid_default_compiler_validates_a_valid_diagram(handbook: Path, write_md) -> None:
    write_md(
        handbook,
        "chapters/diagram.md",
        {"id": "REF-01", "kind": "reference"},
        "# Diagram\n\n```mermaid\ngraph TD\nA --> B\n```",
    )
    add_manifest(handbook, ["chapters/diagram.md"])

    found = codes(validate_handbook(handbook))

    assert "MERMAID_COMPILER_UNAVAILABLE" not in found
    assert "MERMAID_COMPILE_FAILED" not in found
