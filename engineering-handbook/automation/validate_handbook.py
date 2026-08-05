"""Validate the canonical engineering handbook source tree."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen

import yaml
from markdown_it import MarkdownIt
from markdown_it.token import Token
from schema import (
    CHAPTER_METADATA_FIELDS,
    CHAPTER_SECTIONS,
    CONTROL_FIELDS,
    KPI_FIELDS,
    PROMPT_FIELDS,
    RUNBOOK_FIELDS,
    STANDARD_FIELDS,
    TEMPLATE_FIELDS,
    WORKED_EXAMPLE_FIELDS,
    Finding,
)

CONTROL_ID = re.compile(r"\b(?:SEC|GOV|REL|OPS|DATA|AI|RELSE|ACC)-[A-Z0-9]+-\d{3}\b")
KPI_ID = re.compile(r"\bKPI-[A-Z0-9]+-\d{3}\b")
PLACEHOLDER = re.compile(r"\b(?:TODO|TBD|FIXME|XXX)\b|\[INSERT[^\]]*\]|<placeholder>", re.I)
NORMATIVE = re.compile(r"\b(?:must|shall|required|prohibited|may not)\b", re.I)
EXTERNAL_SCHEMES = {"http", "https", "mailto", "tel", "data"}
PROMPT_FAMILIES = ("opus", "sonnet", "haiku")
REGISTRY_FIELDS = ("schema_version", "registry_version", "manual_edition", "owner", "last_verified")


def _markdown() -> MarkdownIt:
    return MarkdownIt("commonmark", {"html": True}).enable("table")


def _frontmatter(text: str) -> tuple[dict[str, Any], str, str | None]:
    if not text.startswith("---\n"):
        return {}, text, None
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text, "YAML front matter is not terminated."
    raw = text[4:end]
    try:
        loaded = yaml.safe_load(raw) or {}
    except yaml.YAMLError as exc:
        return {}, text[end + 5 :], f"Invalid YAML front matter: {exc}"
    if not isinstance(loaded, dict):
        return {}, text[end + 5 :], "YAML front matter must be a mapping."
    return loaded, text[end + 5 :], None


def _read_yaml(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"{path.name} must contain a YAML mapping")
    return loaded


def _walk_tokens(tokens: Iterable[Token]) -> Iterable[Token]:
    for token in tokens:
        yield token
        if token.children:
            yield from _walk_tokens(token.children)


def _slug(value: str) -> str:
    value = re.sub(r"\s*\{#[A-Za-z][\w:.-]*\}\s*$", "", value).strip().lower()
    value = re.sub(r"[^\w\s-]", "", value)
    return re.sub(r"[-\s]+", "-", value).strip("-")


def _headings(tokens: list[Token]) -> tuple[list[str], set[str]]:
    headings: list[str] = []
    anchors: set[str] = set()
    for index, token in enumerate(tokens[:-1]):
        if token.type != "heading_open":
            continue
        inline = tokens[index + 1]
        if inline.type != "inline":
            continue
        text = inline.content.strip()
        headings.append(_slug(text))
        explicit = re.search(r"\{#([A-Za-z][\w:.-]*)\}\s*$", text)
        anchors.add(explicit.group(1) if explicit else _slug(text))
    return headings, anchors


def _prose(tokens: list[Token]) -> str:
    chunks: list[str] = []
    for token in tokens:
        if token.type != "inline" or not token.children:
            continue
        for child in token.children:
            if child.type in {"text", "code_inline"} and child.type != "code_inline":
                chunks.append(child.content)
    return "\n".join(chunks)


def _links_and_images(tokens: list[Token]) -> tuple[list[str], list[str]]:
    links: list[str] = []
    images: list[str] = []
    for token in _walk_tokens(tokens):
        if token.type == "link_open":
            href = token.attrGet("href")
            if href:
                links.append(href)
        elif token.type == "image":
            src = token.attrGet("src")
            if src:
                images.append(src)
    return links, images


def _missing_fields(record: dict[str, Any], fields: Iterable[str]) -> list[str]:
    return [field for field in fields if field not in record or record[field] in (None, "", [], {})]


def load_manifest(root: Path) -> list[Path]:
    """Return ordered local Markdown paths from SUMMARY.md."""
    summary = root / "SUMMARY.md"
    tokens = _markdown().parse(summary.read_text(encoding="utf-8"))
    links, _ = _links_and_images(tokens)
    result: list[Path] = []
    for href in links:
        split = urlsplit(href)
        if split.scheme or not split.path or not split.path.lower().endswith(".md"):
            continue
        result.append(Path(unquote(split.path)))
    return result


def _load_documents(root: Path, manifest: list[Path]) -> dict[Path, dict[str, Any]]:
    documents: dict[Path, dict[str, Any]] = {}
    candidates = set(manifest)
    for path in root.rglob("*.md"):
        candidates.add(path.relative_to(root))
    for relative in sorted(candidates):
        path = root / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        metadata, body, error = _frontmatter(text)
        tokens = _markdown().parse(body)
        headings, anchors = _headings(tokens)
        links, images = _links_and_images(tokens)
        documents[relative] = {
            "metadata": metadata,
            "error": error,
            "tokens": tokens,
            "headings": headings,
            "anchors": anchors,
            "links": links,
            "images": images,
            "prose": _prose(tokens),
        }
    return documents


def _finding(code: str, path: Path, message: str, severity: str = "error") -> Finding:
    return Finding(code=code, path=path, message=message, severity=severity)


def _validate_registry(root: Path, findings: list[Finding]) -> set[str]:
    path = root / "standards" / "registry.yaml"
    if not path.is_file():
        findings.append(
            _finding(
                "STANDARDS_REGISTRY_MISSING",
                Path("standards/registry.yaml"),
                "Standards registry is missing.",
            )
        )
        return set()
    try:
        registry = _read_yaml(path)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        findings.append(
            _finding("STANDARDS_REGISTRY_INVALID", Path("standards/registry.yaml"), str(exc))
        )
        return set()
    missing_header = _missing_fields(registry, REGISTRY_FIELDS)
    if registry.get("schema_version") != 1 or missing_header:
        requirements = ", ".join(field for field in missing_header if field != "schema_version")
        findings.append(
            _finding(
                "STANDARDS_REGISTRY_INVALID",
                Path("standards/registry.yaml"),
                f"Registry requires schema_version 1 and non-empty fields: {requirements or 'schema_version'}.",
            )
        )
    sources = registry.get("sources")
    if not isinstance(sources, list):
        findings.append(
            _finding(
                "STANDARDS_REGISTRY_INVALID",
                Path("standards/registry.yaml"),
                "sources must be a list.",
            )
        )
        return set()
    ids: list[str] = []
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            findings.append(
                _finding(
                    "STANDARD_RECORD_INVALID",
                    Path("standards/registry.yaml"),
                    f"Source record {index + 1} must be a mapping.",
                )
            )
            continue
        missing = _missing_fields(source, STANDARD_FIELDS)
        if missing:
            findings.append(
                _finding(
                    "STANDARD_FIELD_MISSING",
                    Path("standards/registry.yaml"),
                    f"Standard {source.get('id', index + 1)} is missing: {', '.join(missing)}.",
                )
            )
        if source.get("immutable_url") is not None and not isinstance(
            source.get("immutable_url"), str
        ):
            findings.append(
                _finding(
                    "STANDARD_RECORD_INVALID",
                    Path("standards/registry.yaml"),
                    f"Standard {source.get('id', index + 1)} has an invalid immutable_url.",
                )
            )
        if source.get("id"):
            ids.append(str(source["id"]))
    for duplicate, count in Counter(ids).items():
        if count > 1:
            findings.append(
                _finding(
                    "DUPLICATE_STANDARD_ID",
                    Path("standards/registry.yaml"),
                    f"Standard ID {duplicate} appears {count} times.",
                )
            )
    return set(ids)


def _url_reachable(url: str, timeout: float) -> bool:
    request = Request(url, method="HEAD", headers={"User-Agent": "handbook-validator/1"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return 200 <= response.status < 400
    except OSError:
        return False


def check_standard_links(root: Path, timeout: float = 10) -> list[Finding]:
    """Check standards registry URLs using the network-aware validation path."""
    registry_path = root.resolve() / "standards" / "registry.yaml"
    registry = _read_yaml(registry_path)
    findings: list[Finding] = []
    for source in registry.get("sources", []):
        if not isinstance(source, dict):
            continue
        for field in ("official_url", "immutable_url"):
            url = source.get(field)
            if isinstance(url, str) and url and not _url_reachable(url, timeout):
                findings.append(
                    _finding(
                        "STANDARD_URL_UNREACHABLE",
                        Path("standards/registry.yaml"),
                        f"{source.get('id', 'unknown')} {field} is unreachable: {url}.",
                    )
                )
    return findings


def _resolve_link(source: Path, href: str) -> tuple[Path | None, str]:
    split = urlsplit(href)
    if split.scheme in EXTERNAL_SCHEMES or href.startswith("//"):
        return None, ""
    raw_path = unquote(split.path)
    target = (source.parent / raw_path) if raw_path else source
    normalized = Path(os.path.normpath(target.as_posix()))
    return normalized, unquote(split.fragment)


def _linked_documents(
    relative: Path, documents: dict[Path, dict[str, Any]]
) -> list[tuple[Path, dict[str, Any]]]:
    linked: list[tuple[Path, dict[str, Any]]] = []
    for href in documents[relative]["links"]:
        target, _ = _resolve_link(relative, href)
        if target in documents:
            linked.append((target, documents[target]))
    return linked


def _validate_chapter(
    relative: Path,
    document: dict[str, Any],
    documents: dict[Path, dict[str, Any]],
    findings: list[Finding],
) -> None:
    metadata = document["metadata"]
    missing_metadata = _missing_fields(metadata, CHAPTER_METADATA_FIELDS)
    if missing_metadata:
        findings.append(
            _finding(
                "CHAPTER_METADATA_MISSING",
                relative,
                f"Chapter metadata is missing: {', '.join(missing_metadata)}.",
            )
        )
    chapter_id = metadata.get("id")
    linked = _linked_documents(relative, documents)
    linked_assets = [
        item
        for _, item in linked
        if item["metadata"].get("chapter") == chapter_id
        and item["metadata"].get("kind")
        in {
            "chapter-asset",
            "worked-example",
            "prompt",
            "checklist",
            "runbook",
            "kpi-catalog",
            "template",
        }
    ]
    headings = set(document["headings"])
    for item in linked_assets:
        if item["metadata"].get("kind") == "chapter-asset":
            headings.update(item["headings"])
    for code, aliases in CHAPTER_SECTIONS.items():
        if not any(_slug(alias) in headings for alias in aliases):
            findings.append(
                _finding(code, relative, f"Chapter contract section is missing: {aliases[0]}.")
            )
    for family in PROMPT_FAMILIES:
        if _slug(f"{family} prompt") not in headings and not any(
            item["metadata"].get("kind") == "prompt"
            and item["metadata"].get("model_family") == family
            for item in linked_assets
        ):
            findings.append(
                _finding(
                    f"CHAPTER_{family.upper()}_PROMPT_MISSING",
                    relative,
                    f"Chapter is missing a distinct {family.title()} prompt.",
                )
            )
    example_records = [
        item["metadata"]
        for item in linked_assets
        if item["metadata"].get("kind") == "worked-example"
    ]
    inline_fields = {
        field for field in WORKED_EXAMPLE_FIELDS if _slug(field.replace("_", " ")) in headings
    }
    if "worked example" in headings and not example_records:
        missing = [field for field in WORKED_EXAMPLE_FIELDS if field not in inline_fields]
        if missing:
            findings.append(
                _finding(
                    "WORKED_EXAMPLE_FIELD_MISSING",
                    relative,
                    f"Worked example is missing: {', '.join(missing)}.",
                )
            )
    for record in example_records:
        missing = _missing_fields(record, WORKED_EXAMPLE_FIELDS)
        if missing:
            findings.append(
                _finding(
                    "WORKED_EXAMPLE_FIELD_MISSING",
                    relative,
                    f"Linked worked example is missing: {', '.join(missing)}.",
                )
            )


def _validate_asset_contract(
    relative: Path, metadata: dict[str, Any], findings: list[Finding], standards: set[str]
) -> None:
    kind = metadata.get("kind")
    if kind == "prompt":
        missing = _missing_fields(metadata, PROMPT_FIELDS)
        if missing:
            findings.append(
                _finding(
                    "PROMPT_FIELD_MISSING",
                    relative,
                    f"Prompt metadata is missing: {', '.join(missing)}.",
                )
            )
        if metadata.get("model_family") not in PROMPT_FAMILIES:
            findings.append(
                _finding(
                    "PROMPT_MODEL_FAMILY_INVALID",
                    relative,
                    "model_family must be opus, sonnet, or haiku.",
                )
            )
    elif kind == "runbook":
        missing = _missing_fields(metadata, RUNBOOK_FIELDS)
        if missing:
            findings.append(
                _finding(
                    "RUNBOOK_FIELD_MISSING",
                    relative,
                    f"Runbook metadata is missing: {', '.join(missing)}.",
                )
            )
    elif kind == "checklist":
        controls = metadata.get("controls")
        if not isinstance(controls, list) or not controls:
            findings.append(
                _finding(
                    "CONTROL_FIELD_MISSING", relative, "Checklist must define at least one control."
                )
            )
        else:
            for control in controls:
                missing = _missing_fields(
                    control if isinstance(control, dict) else {}, CONTROL_FIELDS
                )
                if missing:
                    findings.append(
                        _finding(
                            "CONTROL_FIELD_MISSING",
                            relative,
                            f"Control is missing: {', '.join(missing)}.",
                        )
                    )
                references = control.get("standards") if isinstance(control, dict) else None
                if isinstance(references, list):
                    for reference in references:
                        if reference not in standards:
                            findings.append(
                                _finding(
                                    "STANDARD_REFERENCE_UNKNOWN",
                                    relative,
                                    f"Unknown standards registry ID: {reference}.",
                                )
                            )
    elif kind == "kpi-catalog":
        kpis = metadata.get("kpis")
        if not isinstance(kpis, list) or not kpis:
            findings.append(
                _finding("KPI_FIELD_MISSING", relative, "KPI catalog must define at least one KPI.")
            )
        else:
            for kpi in kpis:
                missing = _missing_fields(kpi if isinstance(kpi, dict) else {}, KPI_FIELDS)
                if missing:
                    findings.append(
                        _finding(
                            "KPI_FIELD_MISSING", relative, f"KPI is missing: {', '.join(missing)}."
                        )
                    )
    elif kind == "template":
        missing = _missing_fields(metadata, TEMPLATE_FIELDS)
        if missing:
            findings.append(
                _finding(
                    "TEMPLATE_FIELD_MISSING",
                    relative,
                    f"Template metadata is missing: {', '.join(missing)}.",
                )
            )


def _validate_prompts(documents: dict[Path, dict[str, Any]], findings: list[Finding]) -> None:
    grouped: dict[str, dict[str, tuple[str, str, Path]]] = defaultdict(dict)
    for relative, document in documents.items():
        metadata = document["metadata"]
        if metadata.get("kind") != "prompt" or metadata.get("model_family") not in PROMPT_FAMILIES:
            continue
        grouped[str(metadata.get("chapter", ""))][str(metadata["model_family"])] = (
            str(metadata.get("workload_type", "")),
            json.dumps(metadata.get("output_schema", ""), sort_keys=True),
            relative,
        )
    for chapter, families in grouped.items():
        if all(family in families for family in PROMPT_FAMILIES):
            workloads = [families[family][0] for family in PROMPT_FAMILIES]
            outputs = [families[family][1] for family in PROMPT_FAMILIES]
            if len(set(workloads)) != len(workloads) or len(set(outputs)) != len(outputs):
                findings.append(
                    _finding(
                        "PROMPT_FAMILIES_NOT_DISTINCT",
                        families["opus"][2],
                        f"Prompt workload/output declarations for {chapter} are not distinct across model families.",
                    )
                )


def _validate_mermaid(relative: Path, document: dict[str, Any], findings: list[Finding]) -> None:
    blocks = [
        token.content
        for token in document["tokens"]
        if token.type == "fence" and token.info.strip().split()[0:1] == ["mermaid"]
    ]
    if not blocks:
        return
    command = os.environ.get("HANDBOOK_MERMAID_COMMAND") or (
        f"{shlex.quote(sys.executable)} {shlex.quote(str(Path(__file__).with_name('mermaid_check.py')))} "
        "{input} {output}"
    )
    for block in blocks:
        with tempfile.TemporaryDirectory(prefix="handbook-mermaid-") as temp:
            source = Path(temp) / "diagram.mmd"
            output = Path(temp) / "diagram.svg"
            source.write_text(block, encoding="utf-8")
            args = [
                part.replace("{input}", str(source)).replace("{output}", str(output))
                for part in shlex.split(command)
            ]
            if "{input}" not in command:
                args.append(str(source))
            try:
                completed = subprocess.run(
                    args, capture_output=True, text=True, timeout=30, check=False
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                findings.append(
                    _finding(
                        "MERMAID_COMPILE_FAILED", relative, f"Mermaid compilation failed: {exc}."
                    )
                )
                continue
            if completed.returncode != 0 or not output.is_file():
                findings.append(
                    _finding(
                        "MERMAID_COMPILE_FAILED",
                        relative,
                        f"Mermaid compilation failed: {completed.stderr.strip() or completed.stdout.strip() or completed.returncode}.",
                    )
                )


def _validate_suppressions(
    metadata: dict[str, Any], findings: list[Finding]
) -> list[dict[str, Any]]:
    valid: list[dict[str, Any]] = []
    suppressions = metadata.get("suppressions", [])
    if not isinstance(suppressions, list):
        findings.append(
            _finding("SUPPRESSIONS_INVALID", Path("metadata.yaml"), "suppressions must be a list.")
        )
        return valid
    for item in suppressions:
        if not isinstance(item, dict):
            findings.append(
                _finding(
                    "SUPPRESSION_INVALID",
                    Path("metadata.yaml"),
                    "Each suppression must be a mapping.",
                )
            )
            continue
        missing = _missing_fields(item, ("id", "code", "path", "reason", "owner", "expires"))
        if missing:
            findings.append(
                _finding(
                    "SUPPRESSION_INVALID",
                    Path("metadata.yaml"),
                    f"Suppression is missing: {', '.join(missing)}.",
                )
            )
            continue
        try:
            expires = date.fromisoformat(str(item["expires"]))
        except ValueError:
            findings.append(
                _finding(
                    "SUPPRESSION_INVALID",
                    Path("metadata.yaml"),
                    f"Suppression {item['id']} has an invalid expiry date.",
                )
            )
            continue
        if expires < date.today():
            findings.append(
                _finding(
                    "SUPPRESSION_EXPIRED",
                    Path("metadata.yaml"),
                    f"Suppression {item['id']} expired on {expires.isoformat()}.",
                )
            )
            continue
        valid.append(item)
    return valid


def _apply_suppressions(
    findings: list[Finding], suppressions: list[dict[str, Any]]
) -> list[Finding]:
    result: list[Finding] = []
    for finding in findings:
        if any(
            item["code"] == finding.code and Path(str(item["path"])) == finding.path
            for item in suppressions
        ):
            continue
        result.append(finding)
    return result


def validate_handbook(root: Path) -> list[Finding]:
    """Return deterministic validation findings for a handbook root."""
    root = root.resolve()
    findings: list[Finding] = []
    if not root.is_dir():
        raise FileNotFoundError(f"Handbook root does not exist: {root}")
    metadata_path = root / "metadata.yaml"
    summary_path = root / "SUMMARY.md"
    if not metadata_path.is_file() or not summary_path.is_file():
        missing = [path.name for path in (metadata_path, summary_path) if not path.is_file()]
        raise FileNotFoundError(f"Required handbook configuration is missing: {', '.join(missing)}")
    metadata = _read_yaml(metadata_path)
    if metadata.get("schema_version") != 1 or not isinstance(metadata.get("handbook"), dict):
        findings.append(
            _finding(
                "HANDBOOK_METADATA_INVALID",
                Path("metadata.yaml"),
                "schema_version 1 and a handbook mapping are required.",
            )
        )
    suppressions = _validate_suppressions(metadata, findings)
    standards = _validate_registry(root, findings)
    manifest = load_manifest(root)
    documents = _load_documents(root, manifest)
    manifest_set = set(manifest)
    for relative in manifest:
        if not (root / relative).is_file():
            findings.append(
                _finding("MANIFEST_FILE_MISSING", relative, "Manifest entry does not exist.")
            )
    canonical_roots = metadata.get("canonical_roots", [])
    orphan_severity = (
        metadata.get("validation", {}).get("orphan_severity", "error")
        if isinstance(metadata.get("validation", {}), dict)
        else "error"
    )
    for root_name in canonical_roots if isinstance(canonical_roots, list) else []:
        canonical = root / str(root_name)
        if not canonical.is_dir():
            continue
        for path in canonical.rglob("*.md"):
            relative = path.relative_to(root)
            if path.name in {"README.md", "schema.md", "prompt-selection-guide.md"}:
                continue
            if relative not in manifest_set:
                findings.append(
                    _finding(
                        "ORPHAN_CANONICAL_FILE",
                        relative,
                        "Canonical Markdown file is not listed in SUMMARY.md.",
                        orphan_severity,
                    )
                )
    control_counts: Counter[str] = Counter()
    kpi_counts: Counter[str] = Counter()
    for relative, document in documents.items():
        if document["error"]:
            findings.append(_finding("MARKDOWN_METADATA_INVALID", relative, document["error"]))
        metadata_record = document["metadata"]
        _validate_asset_contract(relative, metadata_record, findings, standards)
        for control in metadata_record.get("controls", []):
            if isinstance(control, dict) and isinstance(control.get("id"), str):
                control_counts[control["id"]] += 1
        for kpi in metadata_record.get("kpis", []):
            if isinstance(kpi, dict) and isinstance(kpi.get("id"), str):
                kpi_counts[kpi["id"]] += 1
        if metadata_record.get("kind") == "chapter":
            _validate_chapter(relative, document, documents, findings)
        prose = document["prose"]
        control_counts.update(CONTROL_ID.findall(prose))
        kpi_counts.update(KPI_ID.findall(prose))
        if PLACEHOLDER.search(prose):
            findings.append(
                _finding(
                    "FORBIDDEN_PLACEHOLDER",
                    relative,
                    "Drafting marker or forbidden placeholder appears in prose.",
                )
            )
        if any(
            token.type in {"html_block", "html_inline"}
            for token in _walk_tokens(document["tokens"])
        ):
            findings.append(
                _finding(
                    "UNSUPPORTED_RAW_HTML",
                    relative,
                    "Raw HTML is not supported in canonical Markdown.",
                )
            )
        references = metadata_record.get("standards", [])
        if references and not isinstance(references, list):
            findings.append(
                _finding(
                    "STANDARDS_REFERENCE_INVALID", relative, "standards metadata must be a list."
                )
            )
            references = []
        valid_references = [reference for reference in references if reference in standards]
        for reference in references:
            if reference not in standards:
                findings.append(
                    _finding(
                        "STANDARD_REFERENCE_UNKNOWN",
                        relative,
                        f"Unknown standards registry ID: {reference}.",
                    )
                )
        if metadata_record and NORMATIVE.search(prose) and not valid_references:
            findings.append(
                _finding(
                    "NORMATIVE_CLAIM_UNCITED",
                    relative,
                    "Normative prose requires at least one valid standards registry reference.",
                )
            )
        for href in document["links"]:
            target, anchor = _resolve_link(relative, href)
            if target is None:
                continue
            target_path = root / target
            if not target_path.is_file():
                findings.append(
                    _finding(
                        "LOCAL_LINK_MISSING", relative, f"Local link target does not exist: {href}."
                    )
                )
            elif anchor and target.suffix.lower() == ".md":
                target_document = documents.get(target)
                if target_document is None or anchor not in target_document["anchors"]:
                    findings.append(
                        _finding("ANCHOR_MISSING", relative, f"Anchor does not exist: {href}.")
                    )
        for src in document["images"]:
            target, _ = _resolve_link(relative, src)
            if target is not None and not (root / target).is_file():
                findings.append(
                    _finding("IMAGE_MISSING", relative, f"Image does not exist: {src}.")
                )
        _validate_mermaid(relative, document, findings)
    for identifier, count in sorted(control_counts.items()):
        if count > 1:
            findings.append(
                _finding(
                    "DUPLICATE_CONTROL_ID",
                    Path("."),
                    f"Control ID {identifier} appears {count} times.",
                )
            )
    for identifier, count in sorted(kpi_counts.items()):
        if count > 1:
            findings.append(
                _finding(
                    "DUPLICATE_KPI_ID", Path("."), f"KPI ID {identifier} appears {count} times."
                )
            )
    _validate_prompts(documents, findings)
    return sorted(
        _apply_suppressions(findings, suppressions),
        key=lambda item: (item.path.as_posix(), item.code, item.message),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--format", choices=("human", "json"), default="human")
    parser.add_argument(
        "--check-standard-links",
        action="store_true",
        help="Also perform network checks for official and immutable standards URLs.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        findings = validate_handbook(Path(args.root))
        if args.check_standard_links:
            findings.extend(check_standard_links(Path(args.root)))
    except Exception as exc:
        if args.format == "json":
            print(json.dumps({"error": str(exc)}, indent=2))
        else:
            print(f"configuration failure: {exc}", file=sys.stderr)
        return 3
    if args.format == "json":
        print(json.dumps([finding.to_dict() for finding in findings], indent=2))
    elif findings:
        for finding in findings:
            print(f"{finding.severity.upper()} {finding.code} {finding.path}: {finding.message}")
    else:
        print("Handbook validation passed.")
    if any(finding.severity == "error" for finding in findings):
        return 1
    if findings:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
