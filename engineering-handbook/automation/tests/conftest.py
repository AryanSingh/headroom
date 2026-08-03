from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

AUTOMATION_DIR = Path(__file__).resolve().parents[1]
if str(AUTOMATION_DIR) not in sys.path:
    sys.path.insert(0, str(AUTOMATION_DIR))


@pytest.fixture
def handbook(tmp_path: Path) -> Path:
    root = tmp_path / "engineering-handbook"
    root.mkdir()
    (root / "metadata.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "handbook": {
                    "id": "enterprise-engineering-manual",
                    "title": "Enterprise Engineering Manual",
                    "edition": "2026.1",
                    "status": "draft",
                    "owners": ["Engineering Enablement"],
                },
                "canonical_roots": [
                    "chapters",
                    "runbooks",
                    "checklists",
                    "prompts",
                    "templates",
                    "standards",
                ],
                "suppressions": [],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (root / "standards").mkdir()
    (root / "standards" / "registry.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "sources": [
                    {
                        "id": "NIST-SSDF-1.1",
                        "publisher": "NIST",
                        "title": "Secure Software Development Framework",
                        "version": "SP 800-218, Version 1.1",
                        "publication_date": "2022-02-03",
                        "official_url": "https://csrc.nist.gov/pubs/sp/800/218/final",
                        "immutable_url": "https://doi.org/10.6028/NIST.SP.800-218",
                        "retrieved": "2026-08-03",
                        "scope": "Secure software development practices",
                        "status": "normative",
                        "control_families": ["governance"],
                        "copyright_note": "Paraphrase and cite; do not reproduce wholesale.",
                        "refresh_policy": "Review annually and on publisher revision.",
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return root


def write_markdown(root: Path, relative: str, metadata: dict, body: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = yaml.safe_dump(metadata, sort_keys=False).strip()
    path.write_text(f"---\n{frontmatter}\n---\n\n{body.strip()}\n", encoding="utf-8")
    return path


@pytest.fixture
def write_md():
    return write_markdown
