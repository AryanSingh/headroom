"""Discover and safely execute offline handbook example packages."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml
from schema import EXAMPLE_MANIFEST_FIELDS, ExampleResult

CREDENTIAL = re.compile(r"(?:API[_-]?KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|PRIVATE[_-]?KEY)", re.I)
NETWORK_TOOLS = {"curl", "wget", "http", "https", "nc", "netcat"}
MUTATING_FLAGS = {"-x", "--request", "-d", "--data", "--data-raw", "--upload-file", "-f", "--form"}
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
OFFLINE_RUNNERS = {"python", "python3", "node"}


def discover_examples(root: Path) -> list[Path]:
    return (
        sorted((root / "examples").glob("**/example.yaml")) if (root / "examples").is_dir() else []
    )


def _load_manifest(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        raise ValueError("manifest must be a mapping")
    missing = [field for field in EXAMPLE_MANIFEST_FIELDS if field not in loaded]
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")
    if not isinstance(loaded["command"], list) or not all(
        isinstance(part, str) for part in loaded["command"]
    ):
        raise ValueError("command must be a list of strings")
    if not isinstance(loaded["cleanup"], list):
        raise ValueError("cleanup must be a list")
    if not isinstance(loaded["timeout_seconds"], int | float) or loaded["timeout_seconds"] <= 0:
        raise ValueError("timeout_seconds must be greater than zero")
    if loaded["offline"] is not True or loaded["mutable_network"] is not False:
        raise ValueError("baseline examples must declare offline: true and mutable_network: false")
    if not isinstance(loaded["environment"], dict):
        raise ValueError("environment must be a mapping")
    return loaded


def _unsafe_environment(environment: dict[str, Any]) -> str | None:
    for key, value in environment.items():
        if CREDENTIAL.search(str(key)) or CREDENTIAL.search(str(value)):
            return f"production credential-like environment value is prohibited: {key}"
    return None


def _unsafe_network(command: list[str]) -> str | None:
    if not command:
        return "command cannot be empty"
    tool = Path(command[0]).name.lower()
    if tool not in OFFLINE_RUNNERS:
        return "network-safe offline examples may only use python or node runners"
    upper = {part.upper() for part in command}
    if tool in NETWORK_TOOLS or upper & MUTATING_METHODS or set(command) & MUTATING_FLAGS:
        return "network command is prohibited"
    return None


def _offline_environment(workdir: Path, manifest_environment: dict[str, Any]) -> dict[str, str]:
    guard_dir = workdir / ".offline-guard"
    guard_dir.mkdir()
    (guard_dir / "sitecustomize.py").write_text(
        "import socket\n"
        "def _blocked(*args, **kwargs):\n"
        "    raise OSError('network disabled by handbook example runner')\n"
        "_socket_type = socket.socket\n"
        "class _OfflineSocket(_socket_type):\n"
        "    def connect(self, *args, **kwargs):\n"
        "        _blocked(*args, **kwargs)\n"
        "    def connect_ex(self, *args, **kwargs):\n"
        "        _blocked(*args, **kwargs)\n"
        "socket.socket = _OfflineSocket\n"
        "socket.create_connection = _blocked\n",
        encoding="utf-8",
    )
    node_guard = guard_dir / "node-offline-guard.cjs"
    node_guard.write_text(
        "const blocked = () => { throw new Error('network disabled by handbook example runner'); };\n"
        "for (const name of ['net', 'tls', 'http', 'https', 'http2', 'dgram']) {\n"
        "  const mod = require(name);\n"
        "  for (const key of ['connect', 'request', 'get', 'createConnection', 'createServer']) {\n"
        "    if (typeof mod[key] === 'function') mod[key] = blocked;\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    environment = {
        "PATH": os.defpath,
        "HOME": str(workdir / ".home"),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(guard_dir),
        "NODE_OPTIONS": f"--require {node_guard}",
        "HANDBOOK_EXAMPLE_OFFLINE": "1",
    }
    environment.update({str(key): str(value) for key, value in manifest_environment.items()})
    return environment


def _configuration_error(path: Path, example_id: str, message: str) -> ExampleResult:
    return ExampleResult(
        example_id=example_id, manifest=path, status="configuration-error", message=message
    )


def _run_one(root: Path, manifest_path: Path) -> ExampleResult:
    relative_manifest = manifest_path.relative_to(root)
    try:
        manifest = _load_manifest(manifest_path)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        return _configuration_error(relative_manifest, manifest_path.parent.name, str(exc))
    example_id = str(manifest["id"])
    unsafe = _unsafe_environment(manifest["environment"]) or _unsafe_network(manifest["command"])
    if unsafe:
        return _configuration_error(relative_manifest, example_id, unsafe)
    expected_path = manifest_path.parent / str(manifest["expected_output"])
    if not expected_path.is_file():
        return _configuration_error(
            relative_manifest, example_id, "expected_output fixture does not exist"
        )
    package = manifest_path.parent
    cleanup_codes: list[int] = []
    stdout = ""
    stderr = ""
    exit_code: int | None = None
    timed_out = False
    with tempfile.TemporaryDirectory(prefix=f"handbook-example-{example_id}-") as temp:
        workdir = Path(temp) / package.name
        shutil.copytree(package, workdir)
        environment = _offline_environment(workdir, manifest["environment"])
        try:
            completed = subprocess.run(
                manifest["command"],
                cwd=workdir,
                env=environment,
                capture_output=True,
                text=True,
                timeout=float(manifest["timeout_seconds"]),
                check=False,
            )
            stdout, stderr, exit_code = completed.stdout, completed.stderr, completed.returncode
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            timed_out = True
        finally:
            for cleanup in manifest["cleanup"]:
                if not isinstance(cleanup, list) or not all(
                    isinstance(part, str) for part in cleanup
                ):
                    cleanup_codes.append(3)
                    continue
                if _unsafe_network(cleanup):
                    cleanup_codes.append(3)
                    continue
                try:
                    completed = subprocess.run(
                        cleanup,
                        cwd=workdir,
                        env=environment,
                        capture_output=True,
                        text=True,
                        timeout=30,
                        check=False,
                    )
                    cleanup_codes.append(completed.returncode)
                except (OSError, subprocess.TimeoutExpired):
                    cleanup_codes.append(3)
    expected = expected_path.read_text(encoding="utf-8")
    passed = (
        not timed_out
        and exit_code == 0
        and stdout == expected
        and all(code == 0 for code in cleanup_codes)
    )
    if passed:
        return ExampleResult(
            example_id,
            relative_manifest,
            "passed",
            "example matched expected output",
            stdout,
            stderr,
            exit_code,
            False,
            cleanup_codes,
        )
    reasons = []
    if timed_out:
        reasons.append("timed out")
    if exit_code not in (None, 0):
        reasons.append(f"exit code {exit_code}")
    if stdout != expected:
        reasons.append("stdout did not match expected_output")
    if any(code != 0 for code in cleanup_codes):
        reasons.append("cleanup failed")
    return ExampleResult(
        example_id,
        relative_manifest,
        "failed",
        "; ".join(reasons),
        stdout,
        stderr,
        exit_code,
        timed_out,
        cleanup_codes,
    )


def run_examples(root: Path) -> list[ExampleResult]:
    root = root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Handbook root does not exist: {root}")
    return [_run_one(root, path) for path in discover_examples(root)]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--format", choices=("human", "json"), default="human")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        results = run_examples(Path(args.root))
    except Exception as exc:
        if args.format == "json":
            print(json.dumps({"error": str(exc)}, indent=2))
        else:
            print(f"configuration failure: {exc}", file=sys.stderr)
        return 3
    if args.format == "json":
        print(json.dumps([result.to_dict() for result in results], indent=2))
    else:
        for result in results:
            print(f"{result.status.upper()} {result.example_id}: {result.message}")
        if not results:
            print("No example manifests found.")
    if any(result.status == "configuration-error" for result in results):
        return 3
    if any(result.status == "failed" for result in results):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
