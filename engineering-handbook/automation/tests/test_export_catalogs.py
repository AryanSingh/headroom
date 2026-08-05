from pathlib import Path

from export_catalogs import CONTROL_COLUMNS, KPI_COLUMNS, export_catalogs


def test_export_catalogs_uses_stable_columns_and_rows(tmp_path: Path) -> None:
    root = tmp_path / "handbook"
    root.mkdir()
    (root / "SUMMARY.md").write_text("- [Catalog](catalog.md)\n", encoding="utf-8")
    (root / "catalog.md").write_text(
        "---\nkind: checklist\ncontrols:\n  - id: SEC-AUTH-001\n    title: MFA\n    requirement: Require MFA\n    applicability: production\n    owner: Security\n    frequency: quarterly\n    standards: [OWASP-ASVS]\n---\n# Catalog\n",
        encoding="utf-8",
    )
    (root / "kpis.md").write_text(
        "---\nkind: kpi-catalog\nkpis:\n  - id: KPI-REL-001\n    name: Change failure rate\n    decision: Release gate\n    calculation: failed / total\n    source: deploys\n    frequency: weekly\n    owner: SRE\n    target: '< 5%'\n    warning: '>= 5%'\n---\n# KPIs\n",
        encoding="utf-8",
    )
    (root / "SUMMARY.md").write_text(
        "- [Catalog](catalog.md)\n- [KPIs](kpis.md)\n", encoding="utf-8"
    )

    destination = tmp_path / "out"
    result = export_catalogs(root, destination)

    assert result["controls"].read_text(encoding="utf-8").splitlines()[0] == ",".join(
        CONTROL_COLUMNS
    )
    assert result["kpis"].read_text(encoding="utf-8").splitlines()[0] == ",".join(KPI_COLUMNS)
    assert "SEC-AUTH-001" in result["controls"].read_text(encoding="utf-8")
    assert "KPI-REL-001" in result["kpis"].read_text(encoding="utf-8")
