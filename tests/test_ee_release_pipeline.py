from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import tomllib

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
    workflow = (
        Path(__file__).resolve().parents[1] / ".github/workflows/publish-ee.yml"
    ).read_text()

    assert "scripts/compile_ee.py" in workflow
    assert "scripts/verify_ee_wheel.py" in workflow
    assert "scripts/ee_release_evidence.py" in workflow
    assert "CUTCTX_LICENSE_HMAC_SECRET" in workflow
    assert "python -I -c" in workflow
    assert "python -m twine upload" in workflow
    assert "secrets.PRIVATE_PYPI_URL" in workflow
    assert "secrets.PRIVATE_PYPI_TOKEN" in workflow
    assert "Configure PRIVATE_PYPI_URL" not in workflow
    assert "uv build" not in workflow
    assert 'pip install "$GITHUB_WORKSPACE"' not in workflow
    assert "import sqlalchemy" in workflow
    assert "from cutctx_ee.memory_service import models as memory_models" in workflow
    assert "Tamper test installed EE wheel" in workflow
    assert "if /tmp/cutctx-ee-smoke/bin/python -I -c 'import cutctx_ee'" in workflow
    assert 'test -n "$TWINE_REPOSITORY_URL"' in workflow
    assert 'test -n "$TWINE_PASSWORD"' in workflow


def test_editable_ee_package_version_matches_the_release_version() -> None:
    root = Path(__file__).resolve().parents[1]
    with (root / "pyproject.toml").open("rb") as handle:
        core_version = tomllib.load(handle)["project"]["version"]
    with (root / "packaging/cutctx-ee/pyproject.toml").open("rb") as handle:
        ee_version = tomllib.load(handle)["project"]["version"]

    assert ee_version == core_version


def test_manual_compile_workflow_uses_the_same_signing_and_verification_gates() -> None:
    workflow = (
        Path(__file__).resolve().parents[1] / ".github/workflows/compile-ee.yml"
    ).read_text()

    assert "CUTCTX_LICENSE_HMAC_SECRET" in workflow
    assert "scripts/verify_ee_wheel.py" in workflow
    assert "wheel-verification.json" in workflow
    assert "scripts/check_ee_freshness.py" in workflow
    assert "dist-ee-compiled" in workflow


def test_nuitka_module_command_uses_supported_runtime_module_naming(tmp_path: Path) -> None:
    module = tmp_path / "cutctx_ee" / "billing" / "license_db.py"
    module.parent.mkdir(parents=True)
    module.write_text("value = 1\n")

    command = compile_ee.nuitka_module_command(module, tmp_path / "output")

    assert "--module" in command
    assert "--module-name" not in command
    assert "--module-name-choice=runtime" not in command
    assert "--python-flag=no_docstrings" in command
    assert "--strip-docstrings" not in command
    assert "--no-pgo" not in command


def test_wheel_builder_uses_the_supported_setuptools_backend() -> None:
    source = Path(compile_ee.__file__).read_text()

    assert 'build-backend = "setuptools.build_meta"' in source
    assert "setuptools.backends._legacy" not in source


def test_native_wheel_tag_is_interpreter_and_platform_specific() -> None:
    python_tag, abi_tag, platform_tag = compile_ee.native_wheel_tag()

    assert python_tag.startswith("cp")
    assert abi_tag.startswith("cp")
    assert platform_tag != "any"


def test_wheel_builder_retags_the_native_artifact(monkeypatch, tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    package_dir = build_dir / "cutctx_ee"
    package_dir.mkdir(parents=True)
    output_dir = tmp_path / "dist"
    output_dir.mkdir()
    generic_wheel = output_dir / "cutctx_ee-1.2.3-py3-none-any.whl"
    generic_wheel.write_bytes(b"wheel")
    def fake_check_call(command, **_kwargs):
        if command[1:3] == ["-m", "build"]:
            generic_wheel.write_bytes(b"wheel")

    monkeypatch.setattr(compile_ee.subprocess, "check_call", fake_check_call)
    monkeypatch.setattr(
        compile_ee,
        "retag_native_wheel",
        lambda wheel: wheel.with_name("cutctx_ee-1.2.3-cp312-cp312-test_platform.whl"),
    )

    wheel = compile_ee.build_ee_wheel(build_dir, output_dir, "1.2.3")

    assert wheel is not None
    assert "none-any" not in wheel.name


def test_retag_preserves_an_existing_native_platform_tag(monkeypatch, tmp_path: Path) -> None:
    wheel = tmp_path / "cutctx_ee-1.2.3-cp312-cp312-macosx_11_0_arm64.whl"
    wheel.write_bytes(b"wheel")

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("a correctly tagged native wheel must not be retagged")

    monkeypatch.setattr(compile_ee.subprocess, "run", fail_if_called)

    assert compile_ee.retag_native_wheel(wheel) == wheel


def test_wheel_builder_includes_the_signed_manifest_as_package_data(
    monkeypatch, tmp_path: Path
) -> None:
    build_dir = tmp_path / "build"
    package_dir = build_dir / "cutctx_ee"
    package_dir.mkdir(parents=True)
    monkeypatch.setattr(compile_ee.subprocess, "check_call", lambda *args, **kwargs: None)

    compile_ee.build_ee_wheel(build_dir, tmp_path / "dist", "1.2.3")

    pyproject = (build_dir / "_build_root" / "pyproject.toml").read_text()
    assert "[tool.setuptools.package-data]" in pyproject
    assert '"MANIFEST.sha256.json"' in pyproject
    assert '"*.so"' in pyproject
    assert '"**/*.so"' in pyproject
    assert '"*.pyd"' in pyproject
    assert '"**/*.pyd"' in pyproject


def test_compile_module_ignores_previous_outputs_when_nuitka_creates_none(
    monkeypatch, tmp_path: Path
) -> None:
    module = tmp_path / "billing" / "license_token.py"
    output_dir = tmp_path / "output"
    module.parent.mkdir(parents=True)
    output_dir.mkdir()
    module.write_text("value = 1\n")
    (output_dir / "other.cpython-312-darwin.so").write_bytes(b"old native output")
    monkeypatch.setattr(
        compile_ee.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stderr=""),
    )

    assert compile_ee.compile_ee_module(module, output_dir) == []


def test_compile_all_fails_closed_when_any_module_does_not_compile(
    monkeypatch, tmp_path: Path
) -> None:
    ee_source = tmp_path / "cutctx_ee"
    for name in ("first.py", "second.py"):
        (ee_source / name).parent.mkdir(parents=True, exist_ok=True)
        (ee_source / name).write_text("value = 1\n")
    monkeypatch.setattr(compile_ee, "ROOT", tmp_path)
    monkeypatch.setattr(compile_ee, "EE_SOURCE", ee_source)
    monkeypatch.setattr(
        compile_ee,
        "compile_ee_module",
        lambda module, output_dir, dev: [output_dir / "first.so"]
        if module.name == "first.py"
        else [],
    )

    assert compile_ee.compile_all_ee(tmp_path / "output") == {}


def test_source_leak_check_allows_only_the_generated_package_initializer(tmp_path: Path) -> None:
    wheel = tmp_path / "cutctx_ee-1.2.3-py3-none-any.whl"
    with ZipFile(wheel, "w") as archive:
        archive.writestr("cutctx_ee/__init__.py", "__version__ = '1.2.3'\n")
        archive.writestr("cutctx_ee/billing/license_db.abi3.so", b"native")

    assert compile_ee.verify_no_source_in_wheel(tmp_path)
