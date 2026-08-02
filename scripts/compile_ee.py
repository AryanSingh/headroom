#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-Cutctx-Commercial
# Copyright (c) 2025-2026 Cutctx Labs.

"""SP-3: Compile cutctx_ee to native extensions using Nuitka.

Compiles the proprietary EE Python modules to C extensions (.so/.pyd),
then ships ONLY the compiled artifacts — no .py source in the released wheel.

Usage:
    python scripts/compile_ee.py [--output-dir dist-ee] [--dev]

For CI: called from publish-ee.yml after the standard wheel build.
For dev: use `--dev` to compile with debug symbols for profiling.
"""

import argparse
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

try:
    import tomllib
except ImportError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib

# Paths
ROOT = Path(__file__).resolve().parent.parent
EE_SOURCE = ROOT / "cutctx_ee"
EE_PACKAGING = ROOT / "packaging" / "cutctx-ee"


def _read_project_version() -> str:
    """Read the canonical package version from pyproject.toml."""
    with open(ROOT / "pyproject.toml", "rb") as handle:
        return str(tomllib.load(handle)["project"]["version"])


def check_nuitka_installed() -> str:
    """Check if Nuitka is installed and return its path."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "nuitka", "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return result.stdout.strip().split("\n")[0]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return ""


def install_nuitka():
    """Install Nuitka and its C compiler backend."""
    print("Installing Nuitka...")
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "nuitka",
            "ordered-set",
            "zstandard",
        ]
    )
    print("Nuitka installed.")


def nuitka_module_command(module_path: Path, output_dir: Path, *, dev: bool = False) -> list[str]:
    """Return the supported Nuitka command for one importable EE module."""
    command = [
        sys.executable,
        "-m",
        "nuitka",
        "--module",
        "--module-name-choice=runtime",
        f"--output-dir={output_dir}",
        "--assume-yes-for-downloads",
        "--python-flag=no_docstrings",
        "--remove-output",
    ]
    if not dev:
        command.extend(
            [
                "--nofollow-import-to=unittest",
                "--nofollow-import-to=pytest",
                "--nofollow-import-to=typing_extensions",
            ]
        )
    else:
        command.extend(["--debug", "--unstripped"])
    command.append(str(module_path))
    return command


def compile_ee_module(
    module_path: Path,
    output_dir: Path,
    dev: bool = False,
) -> list[Path]:
    """Compile a single .py module to a .so using Nuitka.

    Returns list of output files (.so + .pyi stubs).
    """
    module_name = module_path.stem
    print(f"  Compiling {module_path.name}...")

    cmd = nuitka_module_command(module_path, output_dir, dev=dev)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(ROOT),
        )
        if result.returncode != 0:
            print(f"  WARNING: Nuitka compilation failed for {module_name}:")
            print(f"  {result.stderr[:500]}")
            return []
    except subprocess.TimeoutExpired:
        print(f"  WARNING: Nuitka timed out for {module_name}")
        return []

    # Find output .so files
    outputs = []
    for ext in ("*.so", "*.pyd", "*.pyi"):
        outputs.extend(output_dir.rglob(ext))
    return outputs


def compile_all_ee(
    output_dir: Path,
    dev: bool = False,
) -> dict[str, list[Path]]:
    """Compile all cutctx_ee modules to native extensions.

    Returns dict mapping module name to output files.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Find all .py modules (exclude __init__, __pycache__, tests)
    py_files = sorted(
        f
        for f in EE_SOURCE.rglob("*.py")
        if f.name != "__init__.py" and "__pycache__" not in str(f) and "tests" not in str(f)
    )

    print(f"Found {len(py_files)} modules to compile")

    results = {}
    success = 0
    failed = 0

    for py_file in py_files:
        rel = py_file.relative_to(ROOT)
        module_output_dir = output_dir / py_file.relative_to(EE_SOURCE).parent
        outputs = compile_ee_module(py_file, module_output_dir, dev=dev)
        if outputs:
            results[str(rel)] = outputs
            success += 1
        else:
            failed += 1

    print(f"\nCompilation complete: {success} succeeded, {failed} failed")
    return results


def verify_no_source_in_wheel(wheel_dir: Path) -> bool:
    """SP-7/V-7: Verify the compiled wheel contains no .py source."""
    import zipfile

    ok = True
    for whl in wheel_dir.glob("*.whl"):
        with zipfile.ZipFile(whl) as z:
            py_files = [n for n in z.namelist() if n.endswith(".py")]
            pyc_files = [n for n in z.namelist() if n.endswith(".pyc")]

            if py_files:
                print(f"FAIL: {whl.name} contains .py source files:")
                for f in py_files[:10]:
                    print(f"  {f}")
                ok = False

            if pyc_files:
                print(f"FAIL: {whl.name} contains .pyc bytecode files:")
                for f in pyc_files[:10]:
                    print(f"  {f}")
                ok = False

            # Should contain .so native extensions
            so_files = [n for n in z.namelist() if n.endswith((".so", ".pyd"))]
            if not so_files:
                print(f"WARNING: {whl.name} contains no .so/.pyd native extensions")
            else:
                print(f"PASS: {whl.name} has {len(so_files)} native extensions, no source")

    return ok


def strip_debug_symbols(module_path: Path):
    """Strip debug symbols from a compiled .so file."""
    if module_path.suffix in (".so", ".pyd"):
        try:
            subprocess.run(
                ["strip", "-s", str(module_path)],
                capture_output=True,
                timeout=30,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass  # strip not available on all platforms


def prepare_ee_package(compile_dir: Path, version: str) -> Path:
    """Stage compiled EE modules in the exact package directory to be signed."""
    build_dir = compile_dir / "_build_root"

    def is_final_native_module(path: Path) -> bool:
        """Exclude artifacts from a previous staging or Nuitka temporary build."""
        return build_dir not in path.parents and not any(
            parent.name.endswith(".build") for parent in path.parents
        )

    so_files = [
        path for path in compile_dir.rglob("*.so") if is_final_native_module(path)
    ]
    pyd_files = [
        path for path in compile_dir.rglob("*.pyd") if is_final_native_module(path)
    ]
    if build_dir.exists():
        shutil.rmtree(build_dir)
    pkg_dir = build_dir / "cutctx_ee"
    pkg_dir.mkdir(parents=True, exist_ok=True)

    # Copy only compiled extensions
    for so_file in so_files:
        dest = pkg_dir / so_file.relative_to(compile_dir)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(so_file, dest)
        strip_debug_symbols(dest)

    for pyd_file in pyd_files:
        dest = pkg_dir / pyd_file.relative_to(compile_dir)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pyd_file, dest)

    # Create minimal __init__.py that imports from compiled extensions
    init_content = textwrap.dedent(f'''\
        # SPDX-License-Identifier: LicenseRef-Cutctx-Commercial
        # Copyright (c) 2025-2026 Cutctx Labs.
        # Auto-generated stub for compiled extensions — no source shipped.
        """Cutctx Enterprise Edition v{version} (compiled)."""
        __version__ = "{version}"
    ''')
    (pkg_dir / "__init__.py").write_text(init_content)

    return pkg_dir


def build_ee_wheel(build_dir: Path, output_dir: Path, version: str) -> Path | None:
    """Build a wheel from a prepared EE package directory."""

    # Create pyproject.toml for the compiled wheel
    pyproject_content = textwrap.dedent(f'''\
        [build-system]
        requires = ["setuptools>=68.0"]
        build-backend = "setuptools.backends._legacy:_Backend"

        [project]
        name = "cutctx-ee"
        version = "{version}"
        description = "Cutctx Enterprise Edition — compiled extensions (no source)"
        license = {{text = "LicenseRef-Cutctx-Commercial"}}
        requires-python = ">=3.10"

        [tool.setuptools.packages.find]
        include = ["cutctx_ee*"]
    ''')
    (build_dir / "pyproject.toml").write_text(pyproject_content)

    # Build wheel
    output_dir.mkdir(parents=True, exist_ok=True)
    subprocess.check_call(
        [sys.executable, "-m", "build", "--wheel", f"--outdir={output_dir}", str(build_dir)],
        timeout=120,
    )

    # Find and return the built wheel
    wheels = list(output_dir.glob("*.whl"))
    return wheels[0] if wheels else None


def main():
    parser = argparse.ArgumentParser(description="SP-3: Compile cutctx_ee to native extensions")
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "dist-ee"),
        help="Output directory for the compiled wheel",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Compile with debug symbols",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify an existing wheel has no source",
    )
    parser.add_argument(
        "--version",
        default=_read_project_version(),
        help="Version string for the compiled wheel",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)

    if args.verify_only:
        ok = verify_no_source_in_wheel(output_dir)
        sys.exit(0 if ok else 1)

    # Check/install Nuitka
    nuitka_ver = check_nuitka_installed()
    if not nuitka_ver:
        install_nuitka()
    else:
        print(f"Using Nuitka: {nuitka_ver}")

    # Compile
    compile_dir = output_dir / "_compiled"
    results = compile_all_ee(compile_dir, dev=args.dev)

    if not results:
        print("ERROR: No modules compiled successfully")
        sys.exit(1)

    pkg_dir_in_wheel = prepare_ee_package(compile_dir, args.version)

    # Build signed integrity manifest from the compiled .so files.
    # The manifest is written into the EE package dir so it ships inside
    # the wheel and can be verified at runtime by cutctx.security.integrity.
    if not args.dev:
        print("\nBuilding signed EE integrity manifest…")
        manifest_script = ROOT / "scripts" / "build_ee_manifest.py"
        # Hash the prepared package directory so the manifest covers exactly
        # the native modules that will be added to the wheel.
        manifest_result = subprocess.run(
            [
                sys.executable,
                str(manifest_script),
                "--ee-dir",
                str(pkg_dir_in_wheel),
                "--output",
                str(pkg_dir_in_wheel / "MANIFEST.sha256.json"),
            ],
            capture_output=False,
            cwd=str(ROOT),
        )
        if manifest_result.returncode != 0:
            print("ERROR: manifest build failed — refusing to ship an unverifiable EE wheel")
            sys.exit(1)
        else:
            print("Integrity manifest built and included in wheel.")
    else:
        print("\nDev build — skipping signed manifest (use --unsigned for local testing)")

    wheel = build_ee_wheel(pkg_dir_in_wheel.parent, output_dir, args.version)
    if wheel:
        print(f"\nBuilt compiled EE wheel: {wheel}")
    else:
        print("ERROR: Wheel build failed")
        sys.exit(1)

    if verify_no_source_in_wheel(output_dir):
        print("\nSP-3 verification PASSED: no source in wheel")
    else:
        print("\nSP-3 verification FAILED: source detected in wheel")
        sys.exit(1)


if __name__ == "__main__":
    main()
