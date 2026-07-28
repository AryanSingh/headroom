from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

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


class AgentPackageRegistry:
    def __init__(self, agents_dir: Path | str) -> None:
        self.agents_dir = Path(agents_dir)
        self.agents_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, package_id: str) -> Path:
        if not package_id or "/" in package_id or ".." in package_id:
            raise ValueError(f"invalid package id: {package_id!r}")
        return self.agents_dir / f"{package_id}.yaml"

    def list(self) -> list[AgentPackage]:
        packages: list[AgentPackage] = []
        for path in sorted(self.agents_dir.glob("*.yaml")):
            packages.append(parse_agent_package_yaml(path.read_text(encoding="utf-8")))
        return packages

    def get(self, package_id: str) -> AgentPackage:
        path = self._path_for(package_id)
        if not path.exists():
            raise KeyError(package_id)
        return parse_agent_package_yaml(path.read_text(encoding="utf-8"))

    def put(self, text: str) -> AgentPackage:
        package = parse_agent_package_yaml(text)
        self._path_for(package.id).write_text(
            text if text.endswith("\n") else text + "\n", encoding="utf-8"
        )
        return package

    def delete(self, package_id: str) -> bool:
        path = self._path_for(package_id)
        if not path.exists():
            return False
        path.unlink()
        return True
