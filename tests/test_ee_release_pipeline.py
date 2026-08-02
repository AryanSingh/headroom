from __future__ import annotations

from pathlib import Path

from scripts import compile_ee


def test_prepare_package_copies_modules_before_manifest_generation(tmp_path: Path) -> None:
    compile_dir = tmp_path / "compiled"
    native = compile_dir / "license_db.cpython-311-x86_64-linux-gnu.so"
    native.parent.mkdir(parents=True)
    native.write_bytes(b"native")

    package = compile_ee.prepare_ee_package(compile_dir, "1.2.3")

    assert (package / native.name).read_bytes() == b"native"
    assert (package / "__init__.py").exists()


def test_publish_workflow_builds_and_verifies_a_compiled_release_candidate() -> None:
    workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/publish-ee.yml").read_text()

    assert "scripts/compile_ee.py" in workflow
    assert "scripts/verify_ee_wheel.py" in workflow
    assert "scripts/ee_release_evidence.py" in workflow
    assert "CUTCTX_LICENSE_HMAC_SECRET" in workflow
    assert "python -I -c" in workflow
    assert "uv build" not in workflow
