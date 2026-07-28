from __future__ import annotations

from pathlib import Path

import pytest

from cutctx.orchestration.agent_packages import (
    AGENT_PACKAGE_API_VERSION,
    AgentPackage,
    compute_package_hash,
    parse_agent_package_yaml,
)


EXAMPLE = """\
apiVersion: cutctx.dev/agent/v1
id: implementer-codex
version: 1
harness: codex_cli
role: implementer
tools:
  - shell
  - apply_patch
policy_refs:
  - contract:implementation
"""


def test_parse_agent_package_yaml() -> None:
    pkg = parse_agent_package_yaml(EXAMPLE)
    assert pkg.id == "implementer-codex"
    assert pkg.harness == "codex_cli"
    assert pkg.role == "implementer"
    assert pkg.tools == ["shell", "apply_patch"]
    assert pkg.policy_refs == ["contract:implementation"]


def test_package_hash_is_stable_across_key_order() -> None:
    a = parse_agent_package_yaml(EXAMPLE)
    b = parse_agent_package_yaml(EXAMPLE.replace("implementer-codex", "implementer-codex"))
    assert compute_package_hash(a) == compute_package_hash(b)
    assert len(compute_package_hash(a)) == 64


def test_rejects_unknown_api_version() -> None:
    bad = EXAMPLE.replace(AGENT_PACKAGE_API_VERSION, "cutctx.dev/agent/v0")
    with pytest.raises(ValueError, match="apiVersion"):
        parse_agent_package_yaml(bad)


def test_example_fixture_on_disk() -> None:
    text = Path(".cutctx/agents/example-implementer.yaml").read_text(encoding="utf-8")
    pkg = parse_agent_package_yaml(text)
    assert pkg.id == "implementer-codex"
