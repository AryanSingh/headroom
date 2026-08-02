from __future__ import annotations

from pathlib import Path

from scripts import compile_ee


def test_prepare_package_copies_modules_before_manifest_generation(tmp_path: Path) -> None:
    compile_dir = tmp_path / "compiled"
    native = compile_dir / "billing" / "license_db.cpython-311-x86_64-linux-gnu.so"
    native.parent.mkdir(parents=True)
    native.write_bytes(b"native")

    package = compile_ee.prepare_ee_package(compile_dir, "1.2.3")

    assert (package / "billing" / native.name).read_bytes() == b"native"
    assert (package / "__init__.py").exists()


def test_prepare_package_ignores_a_previous_staging_directory(tmp_path: Path) -> None:
    compile_dir = tmp_path / "compiled"
    native = compile_dir / "module.abi3.so"
    stale = compile_dir / "_build_root" / "cutctx_ee" / "stale.abi3.so"
    native.parent.mkdir(parents=True)
    stale.parent.mkdir(parents=True)
    native.write_bytes(b"native")
    stale.write_bytes(b"stale")

    package = compile_ee.prepare_ee_package(compile_dir, "1.2.3")

    assert (package / native.name).exists()
    assert not (package / "_build_root").exists()


def test_publish_workflow_builds_and_verifies_a_compiled_release_candidate() -> None:
    workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/publish-ee.yml").read_text()

    assert "scripts/compile_ee.py" in workflow
    assert "scripts/verify_ee_wheel.py" in workflow
    assert "scripts/ee_release_evidence.py" in workflow
    assert "CUTCTX_LICENSE_HMAC_SECRET" in workflow
    assert "python -I -c" in workflow
    assert "uv build" not in workflow


def test_nuitka_module_command_uses_supported_runtime_module_naming(tmp_path: Path) -> None:
    module = tmp_path / "cutctx_ee" / "billing" / "license_db.py"
    module.parent.mkdir(parents=True)
    module.write_text("value = 1\n")

    command = compile_ee.nuitka_module_command(module, tmp_path / "output")

    assert "--module" in command
    assert "--module-name" not in command
    assert "--module-name-choice=runtime" in command
    assert "--python-flag=no_docstrings" in command
    assert "--strip-docstrings" not in command
    assert "--no-pgo" not in command
