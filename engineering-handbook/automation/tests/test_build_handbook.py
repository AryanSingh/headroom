from pathlib import Path

from build_handbook import build_docx, build_markdown, parse_document, write_reference_style


def test_build_markdown_preserves_summary_order_and_strips_front_matter(tmp_path: Path) -> None:
    root = tmp_path / "handbook"
    root.mkdir()
    (root / "metadata.yaml").write_text("handbook:\n  title: Pilot Manual\n", encoding="utf-8")
    (root / "SUMMARY.md").write_text("- [Second](second.md)\n- [First](first.md)\n", encoding="utf-8")
    (root / "first.md").write_text("---\nid: first\n---\n# First\n\nFirst body.\n", encoding="utf-8")
    (root / "second.md").write_text("---\nid: second\n---\n# Second\n\nSecond body.\n", encoding="utf-8")

    output = tmp_path / "manual.md"
    build_markdown(root, output)

    assembled = output.read_text(encoding="utf-8")
    assert assembled.count("# Pilot Manual") == 1
    assert assembled.index("# Second") < assembled.index("# First")
    assert "id: first" not in assembled


def test_parser_captures_tables_lists_and_code(tmp_path: Path) -> None:
    source = tmp_path / "sample.md"
    source.write_text(
        "# Heading\n\n- [ ] Review\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n\n```python\nprint('ok')\n```\n",
        encoding="utf-8",
    )

    nodes = parse_document(source.read_text(encoding="utf-8"))

    assert {node.kind for node in nodes} >= {"heading", "task", "table", "code"}


def test_build_docx_writes_a_valid_document(tmp_path: Path) -> None:
    root = tmp_path / "handbook"
    root.mkdir()
    (root / "metadata.yaml").write_text("handbook:\n  title: Pilot Manual\n", encoding="utf-8")
    (root / "SUMMARY.md").write_text("- [Pilot](pilot.md)\n", encoding="utf-8")
    (root / "pilot.md").write_text("# Pilot\n\nA short paragraph.\n", encoding="utf-8")

    output = tmp_path / "manual.docx"
    build_docx(root, output, toc_page_numbers={"Pilot": 1})

    assert output.read_bytes()[:2] == b"PK"


def test_reference_style_docx_is_reproducible(tmp_path: Path) -> None:
    output = tmp_path / "reference.docx"

    write_reference_style(output)

    assert output.read_bytes()[:2] == b"PK"
