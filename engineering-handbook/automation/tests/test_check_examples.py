from __future__ import annotations

import json
from pathlib import Path

import yaml
from check_examples import discover_examples, main, run_examples


def write_example(root: Path, manifest: dict, script: str = "print('pass')\n") -> Path:
    package = root / "examples" / manifest.get("id", "example")
    package.mkdir(parents=True)
    (package / "run.py").write_text(script, encoding="utf-8")
    (package / "README.md").write_text("# Example\n", encoding="utf-8")
    (package / "expected.txt").write_text("pass\n", encoding="utf-8")
    (package / "example.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )
    return package


def valid_manifest() -> dict:
    return {
        "schema_version": 1,
        "id": "offline-example",
        "title": "Offline example",
        "command": ["python3", "run.py"],
        "timeout_seconds": 5,
        "cleanup": [],
        "dependencies": ["Python 3"],
        "fixtures": [],
        "expected_output": "expected.txt",
        "offline": True,
        "mutable_network": False,
        "environment": {},
    }


def test_discovers_example_manifests(handbook: Path) -> None:
    package = write_example(handbook, valid_manifest())
    assert discover_examples(handbook) == [package / "example.yaml"]


def test_runs_offline_example_in_temporary_copy_and_captures_output(handbook: Path) -> None:
    package = write_example(
        handbook,
        valid_manifest(),
        "from pathlib import Path\nPath('created.txt').write_text('temporary')\nprint('pass')\n",
    )

    results = run_examples(handbook)

    assert results[0].status == "passed"
    assert results[0].stdout == "pass\n"
    assert results[0].stderr == ""
    assert results[0].exit_code == 0
    assert not (package / "created.txt").exists()


def test_timeout_and_cleanup_are_applied(handbook: Path) -> None:
    manifest = valid_manifest()
    manifest["timeout_seconds"] = 0.05
    manifest["cleanup"] = [
        ["python3", "-c", "from pathlib import Path; Path('cleaned').write_text('yes')"]
    ]
    write_example(handbook, manifest, "import time\ntime.sleep(2)\n")

    result = run_examples(handbook)[0]

    assert result.status == "failed"
    assert result.timed_out is True
    assert result.cleanup_exit_codes == [0]


def test_blocks_credentials_and_mutable_network_commands(handbook: Path) -> None:
    credential = valid_manifest()
    credential["environment"] = {"OPENAI_API_KEY": "secret"}
    write_example(handbook, credential)
    network = valid_manifest()
    network["id"] = "network-example"
    network["command"] = ["curl", "-X", "POST", "https://example.com"]
    write_example(handbook, network)

    results = run_examples(handbook)

    assert {result.status for result in results} == {"configuration-error"}
    assert any("credential" in result.message.lower() for result in results)
    assert any("network" in result.message.lower() for result in results)


def test_strips_inherited_credentials_and_blocks_runtime_network(handbook: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "parent-secret")
    script = (
        "import os, socket\n"
        "assert 'OPENAI_API_KEY' not in os.environ\n"
        "try:\n"
        "    socket.create_connection(('example.com', 443), timeout=0.1)\n"
        "except OSError:\n"
        "    print('blocked')\n"
        "else:\n"
        "    raise SystemExit('network allowed')\n"
    )
    package = write_example(handbook, valid_manifest(), script)
    (package / "expected.txt").write_text("blocked\n", encoding="utf-8")

    result = run_examples(handbook)[0]

    assert result.stdout == "blocked\n"
    assert result.status == "passed", result.to_dict()


def test_missing_manifest_fields_are_configuration_errors(handbook: Path) -> None:
    write_example(handbook, {"id": "incomplete"})
    result = run_examples(handbook)[0]
    assert result.status == "configuration-error"
    assert "command" in result.message


def test_human_and_json_cli_exit_codes(handbook: Path, capsys) -> None:
    write_example(handbook, valid_manifest())
    assert main([str(handbook), "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["status"] == "passed"

    (handbook / "examples" / "offline-example" / "run.py").write_text("raise SystemExit(7)\n")
    assert main([str(handbook), "--format", "human"]) == 1

    (handbook / "examples" / "offline-example" / "example.yaml").write_text("id: broken\n")
    assert main([str(handbook), "--format", "json"]) == 3
