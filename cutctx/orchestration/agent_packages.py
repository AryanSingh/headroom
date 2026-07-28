from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

import yaml

AGENT_PACKAGE_API_VERSION = "cutctx.dev/agent/v1"


@dataclass
class AgentPackage:
    id: str
    version: int
    harness: str
    role: str
    tools: list[str] = field(default_factory=list)
    policy_refs: list[str] = field(default_factory=list)
    package_hash: str = ""


def parse_agent_package_yaml(text: str) -> AgentPackage:
    raw = yaml.safe_load(text)
    if not isinstance(raw, dict):
        raise ValueError("agent package must be a mapping")
    if raw.get("apiVersion") != AGENT_PACKAGE_API_VERSION:
        raise ValueError(f"unsupported apiVersion: {raw.get('apiVersion')!r}")
    pkg = AgentPackage(
        id=str(raw["id"]),
        version=int(raw["version"]),
        harness=str(raw["harness"]),
        role=str(raw["role"]),
        tools=[str(item) for item in raw.get("tools", [])],
        policy_refs=[str(item) for item in raw.get("policy_refs", [])],
    )
    pkg.package_hash = compute_package_hash(pkg)
    return pkg


def canonical_package_bytes(package: AgentPackage) -> bytes:
    payload = {
        "apiVersion": AGENT_PACKAGE_API_VERSION,
        "id": package.id,
        "version": package.version,
        "harness": package.harness,
        "role": package.role,
        "tools": list(package.tools),
        "policy_refs": list(package.policy_refs),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def compute_package_hash(package: AgentPackage) -> str:
    return hashlib.sha256(canonical_package_bytes(package)).hexdigest()
