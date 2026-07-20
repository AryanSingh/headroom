"""Versioned scenario fixtures for Codex and Claude protocol replay."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from cutctx.capture.fixture_safety import assert_fixture_safe, sanitize_capture_record

SUPPORTED_ACTIONS = {
    "request",
    "restart_proxy",
    "disconnect",
    "reconnect",
    "cancel",
}
SUPPORTED_TRANSPORTS = {"http-json", "http-sse", "websocket"}
SUPPORTED_RUNTIMES = {"python", "native"}
SCENARIO_FIELDS = {
    "schema_version",
    "id",
    "client",
    "client_version",
    "tags",
    "runtimes",
    "unsupported_runtimes",
    "steps",
    "assertions",
}
UPSTREAM_EVENT_TYPES = {
    "codex": {
        "error",
        "response.completed",
        "response.content_part.added",
        "response.content_part.done",
        "response.created",
        "response.failed",
        "response.function_call_arguments.delta",
        "response.function_call_arguments.done",
        "response.in_progress",
        "response.incomplete",
        "response.output_item.added",
        "response.output_item.done",
        "response.output_text.delta",
        "response.output_text.done",
        "response.reasoning_summary_part.added",
        "response.reasoning_summary_part.done",
        "response.reasoning_summary_text.delta",
        "response.reasoning_summary_text.done",
    },
    "claude": {
        "content_block_delta",
        "content_block_start",
        "content_block_stop",
        "error",
        "message_delta",
        "message_start",
        "message_stop",
        "ping",
    },
}


class FixtureValidationError(ValueError):
    """Raised for malformed or incomplete agent replay fixtures."""


def _required(mapping: dict[str, Any], key: str, expected: type) -> Any:
    value = mapping.get(key)
    if not isinstance(value, expected) or (expected in {str, list} and not value):
        raise FixtureValidationError(f"{key} must be a non-empty {expected.__name__}")
    return value


def validate_scenario(scenario: dict[str, Any]) -> None:
    unknown_fields = sorted(set(scenario) - SCENARIO_FIELDS)
    if unknown_fields:
        raise FixtureValidationError(
            "unknown scenario fields (protocol drift): " + ", ".join(unknown_fields)
        )
    if scenario.get("schema_version") != 1:
        raise FixtureValidationError("schema_version must be 1")
    _required(scenario, "id", str)
    if scenario.get("client") not in {"codex", "claude"}:
        raise FixtureValidationError("client must be codex or claude")
    _required(scenario, "client_version", str)
    tags = _required(scenario, "tags", list)
    if not all(isinstance(tag, str) and tag for tag in tags):
        raise FixtureValidationError("tags must contain non-empty strings")
    runtimes = scenario.get("runtimes", [])
    unsupported = scenario.get("unsupported_runtimes", [])
    if not isinstance(runtimes, list) or not set(runtimes).issubset(SUPPORTED_RUNTIMES):
        raise FixtureValidationError("runtimes contains an unsupported runtime")
    if not isinstance(unsupported, list):
        raise FixtureValidationError("unsupported_runtimes must be a list")
    for declaration in unsupported:
        if not isinstance(declaration, dict):
            raise FixtureValidationError("unsupported runtime declarations must be objects")
        if declaration.get("runtime") not in SUPPORTED_RUNTIMES:
            raise FixtureValidationError("unsupported runtime declaration has unknown runtime")
        for required in ("reason", "tracking_issue"):
            if not isinstance(declaration.get(required), str) or not declaration[required]:
                raise FixtureValidationError(f"unsupported runtime declaration requires {required}")
    declared = set(runtimes) | {
        declaration["runtime"] for declaration in unsupported if isinstance(declaration, dict)
    }
    if declared != SUPPORTED_RUNTIMES:
        raise FixtureValidationError("every runtime must be supported or explicitly unsupported")
    steps = _required(scenario, "steps", list)
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            raise FixtureValidationError(f"steps[{index}] must be an object")
        action = step.get("action")
        if action not in SUPPORTED_ACTIONS:
            raise FixtureValidationError(f"steps[{index}] has unsupported action {action!r}")
        if action == "request":
            if step.get("transport") not in SUPPORTED_TRANSPORTS:
                raise FixtureValidationError(f"steps[{index}] has unsupported transport")
            path = step.get("path")
            if not isinstance(path, str) or not path.startswith("/"):
                raise FixtureValidationError(f"steps[{index}] requires an absolute path")
            body_files = step.get("body_fixtures")
            if body_files is not None and (
                not isinstance(body_files, list)
                or not body_files
                or not all(isinstance(item, str) and item for item in body_files)
            ):
                raise FixtureValidationError(f"steps[{index}].body_fixtures must be non-empty")
    if not isinstance(scenario.get("assertions"), dict):
        raise FixtureValidationError("assertions must be an object")
    assert_fixture_safe(scenario)


def validate_upstream_script(script: dict[str, Any], *, client: str) -> None:
    if client not in UPSTREAM_EVENT_TYPES:
        raise FixtureValidationError(f"unknown fixture client {client!r}")
    if not isinstance(script.get("status", 200), int):
        raise FixtureValidationError("upstream script status must be an integer")
    events = script.get("events")
    if events is None:
        if not isinstance(script.get("json"), dict):
            raise FixtureValidationError("upstream script requires events or json")
        return
    if not isinstance(events, list):
        raise FixtureValidationError("upstream script events must be a list")
    for event in events:
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            raise FixtureValidationError("upstream script events require a type")
        if event["type"] not in UPSTREAM_EVENT_TYPES[client]:
            raise FixtureValidationError(
                f"unknown upstream event (protocol drift): {event['type']}"
            )


def load_scenario_corpus(root: str | Path) -> list[dict[str, Any]]:
    fixture_root = Path(root)
    scenarios: list[dict[str, Any]] = []
    for manifest in sorted(fixture_root.glob("*/scenario.json")):
        scenario = json.loads(manifest.read_text(encoding="utf-8"))
        scenarios.append(scenario)
    return scenarios


def validate_coverage(scenarios: list[dict[str, Any]], coverage: dict[str, Any]) -> None:
    required_tags = coverage.get("required_tags")
    if not isinstance(required_tags, dict):
        raise FixtureValidationError("coverage.required_tags must be an object")
    seen_by_client: dict[str, set[str]] = {"codex": set(), "claude": set()}
    for scenario in scenarios:
        client = scenario.get("client")
        if client in seen_by_client:
            seen_by_client[client].update(scenario.get("tags", []))
    missing: list[str] = []
    for client, tags in required_tags.items():
        if client not in seen_by_client or not isinstance(tags, list):
            raise FixtureValidationError(f"invalid required tag declaration for {client}")
        missing.extend(f"{client}:{tag}" for tag in tags if tag not in seen_by_client[client])
    if missing:
        raise FixtureValidationError("required matrix tags without fixtures: " + ", ".join(missing))


def _sanitize_record_url(record: dict[str, Any]) -> dict[str, Any]:
    result = dict(record)
    url = result.get("url")
    if not isinstance(url, str):
        return result
    parsed = urlsplit(url)
    pairs = [
        (
            key,
            "<redacted>"
            if any(part in key.lower() for part in ("key", "token", "secret", "signature", "code"))
            else value,
        )
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
    ]
    result["url"] = urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urlencode(pairs, doseq=True), "")
    )
    return result


def _load_capture_records(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        records = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        records = value if isinstance(value, list) else [value]
    if not all(isinstance(record, dict) for record in records):
        raise FixtureValidationError("capture must contain JSON objects")
    return records


def _write_private_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
    finally:
        # fdopen normally closes the descriptor; suppress the already-closed
        # case while retaining a narrow, permission-controlled write path.
        try:
            os.close(descriptor)
        except OSError:
            pass
    path.chmod(0o600)


def import_capture_file(
    source: str | Path,
    *,
    output: str | Path | None = None,
    delete_source: bool = False,
) -> list[dict[str, Any]]:
    """Import Codex wire, Claude MITM JSONL, or Claude debug records safely."""

    source_path = Path(source)
    if delete_source:
        source_mode = stat.S_IMODE(source_path.stat().st_mode)
        parent_mode = stat.S_IMODE(source_path.parent.stat().st_mode)
        if source_mode & 0o077 or parent_mode & 0o077:
            raise FixtureValidationError(
                "raw capture and its directory must be private before deletion/import"
            )
    records = [
        sanitize_capture_record(_sanitize_record_url(record))
        for record in _load_capture_records(source_path)
    ]
    assert_fixture_safe(records)
    if output is not None:
        _write_private_json(Path(output), records)
    if delete_source:
        source_path.unlink()
    return records
