"""Regression tests for the compiled EE artifact builder."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


def _load_compile_script():
    spec = importlib.util.spec_from_file_location("compile_ee", ROOT / "scripts" / "compile_ee.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_nested_module_uses_nuitka_4_command_and_preserves_package_path(
    tmp_path, monkeypatch
) -> None:
    module = _load_compile_script()
    source = module.EE_SOURCE / "memory_service" / "api.py"
    commands: list[list[str]] = []

    def fake_run(command, **_kwargs):
        commands.append(command)
        output_arg = next(arg for arg in command if arg.startswith("--output-dir="))
        output_dir = Path(output_arg.split("=", 1)[1])
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "api.cpython-test.so").write_bytes(b"compiled")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    outputs = module.compile_ee_module(source, tmp_path)

    assert outputs == [tmp_path / "cutctx_ee" / "memory_service" / "api.cpython-test.so"]
    assert not any(arg.startswith("--module-name") for arg in commands[0])
    assert "--python-flag=no_docstrings" in commands[0]
    assert "--strip-docstrings" not in commands[0]
    assert "--nofollow-import-to=pytest" in commands[0]
    assert "--no-pgo" not in commands[0]


def test_wheel_staging_preserves_nested_extensions_without_recursing_into_itself(
    tmp_path, monkeypatch
) -> None:
    module = _load_compile_script()
    compile_dir = tmp_path / "compiled"
    nested = compile_dir / "cutctx_ee" / "memory_service"
    nested.mkdir(parents=True)
    extension = nested / "api.cpython-test.so"
    extension.write_bytes(b"compiled")

    commands: list[list[str]] = []

    def fake_check_call(command, **_kwargs):
        commands.append(command)

    monkeypatch.setattr(module, "strip_debug_symbols", lambda _path: None)
    monkeypatch.setattr(module.subprocess, "check_call", fake_check_call)

    module.build_ee_wheel(compile_dir, tmp_path / "dist", "0.31.0")

    staged = compile_dir / "_build_root" / "cutctx_ee" / "memory_service"
    assert (staged / extension.name).read_bytes() == b"compiled"
    pyproject = (compile_dir / "_build_root" / "pyproject.toml").read_text()
    assert 'build-backend = "setuptools.build_meta"' in pyproject
    assert "setuptools.backends._legacy" not in pyproject
    setup = (compile_dir / "_build_root" / "setup.py").read_text()
    assert "class BinaryDistribution" in setup
    assert '"*.so"' in setup
    assert "MANIFEST.sha256.json" in setup
    init_stub = (compile_dir / "_build_root" / "cutctx_ee" / "__init__.py").read_text()
    assert "verify_ee_manifest(strict=True)" in init_stub
    assert "guard_ee_entry()" in init_stub
    assert commands[0][1].endswith("scripts/build_ee_manifest.py")
    assert "--unsigned" not in commands[0]
    assert commands[1][1:3] == ["-m", "build"]


def test_development_wheel_marks_manifest_unsigned(tmp_path, monkeypatch) -> None:
    module = _load_compile_script()
    compiled = tmp_path / "compiled" / "cutctx_ee"
    compiled.mkdir(parents=True)
    (compiled / "module.cpython-test.so").write_bytes(b"compiled")
    commands: list[list[str]] = []

    monkeypatch.setattr(module, "strip_debug_symbols", lambda _path: None)
    monkeypatch.setattr(
        module.subprocess,
        "check_call",
        lambda command, **_kwargs: commands.append(command),
    )

    module.build_ee_wheel(tmp_path / "compiled", tmp_path / "dist", "0.31.0", dev=True)

    assert "--unsigned" in commands[0]
    assert commands[1][1:3] == ["-m", "build"]
