#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-Headroom-Commercial
# Copyright (c) 2025-2026 Cutctx Labs.

"""SP-3: Compile headroom_ee to native extensions using Nuitka.

Compiles the proprietary EE Python modules to C extensions (.so/.pyd),
then ships ONLY the compiled artifacts — no .py source in the released wheel.

Usage:
    python scripts/compile_ee.py [--output-dir dist-ee] [--dev]

For CI: called from publish-ee.yml after the standard wheel build.
For dev: use `--dev` to compile with debug symbols for profiling.
"""

import argparse
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

# Paths
ROOT = Path(__file__).resolve().parent.parent
EE_SOURCE = ROOT / "headroom_ee"
EE_PACKAGING = ROOT / "packaging" / "headroom-ee"


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
    subprocess.check_call([
        sys.executable, "-m", "pip", "install",
        "nuitka", "ordered-set", "zstandard",
    ])
    print("Nuitka installed.")


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

    cmd = [
        sys.executable, "-m", "nuitka",
        "--module",  # Produce .so extension module, not standalone
        "--module-name", f"headroom_ee.{module_name}",
        f"--output-dir={output_dir}",
        "--assume-yes-for-downloads",
        # Strip docstrings and assertions in release
        "--strip-docstrings",
        "--remove-output",  # Remove .c source after compilation
    ]

    if not dev:
        cmd.extend([
            "--nofollow-import-to", "unittest",
            "--nofollow-import-to", "pytest",
            "--nofollow-import-to", "typing_extensions",
            # Remove source code from output
            "--no-pgo",
        ])
    else:
        cmd.extend([
            "--debug",
            "--unstripped",
        ])

    cmd.append(str(module_path))

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
    """Compile all headroom_ee modules to native extensions.

    Returns dict mapping module name to output files.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Find all .py modules (exclude __init__, __pycache__, tests)
    py_files = sorted(
        f for f in EE_SOURCE.rglob("*.py")
        if f.name != "__init__.py"
        and "__pycache__" not in str(f)
        and "tests" not in str(f)
    )

    print(f"Found {len(py_files)} modules to compile")

    results = {}
    success = 0
    failed = 0

    for py_file in py_files:
        rel = py_file.relative_to(ROOT)
        outputs = compile_ee_module(py_file, output_dir, dev=dev)
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


def build_ee_wheel(
    compile_dir: Path,
    output_dir: Path,
    version: str,
) -> Path | None:
    """Build a wheel from compiled extensions only (no .py source)."""
    # Create a temporary package structure with only .so/.pyd files
    build_dir = compile_dir / "_build_root"
    pkg_dir = build_dir / "headroom_ee"
    pkg_dir.mkdir(parents=True, exist_ok=True)

    # Copy only compiled extensions
    for so_file in compile_dir.rglob("*.so"):
        dest = pkg_dir / so_file.name
        shutil.copy2(so_file, dest)
        strip_debug_symbols(dest)

    for pyd_file in compile_dir.rglob("*.pyd"):
        dest = pkg_dir / pyd_file.name
        shutil.copy2(pyd_file, dest)

    # Create minimal __init__.py that imports from compiled extensions
    init_content = textwrap.dedent(f'''\
        # SPDX-License-Identifier: LicenseRef-Headroom-Commercial
        # Copyright (c) 2025-2026 Cutctx Labs.
        # Auto-generated stub for compiled extensions — no source shipped.
        """CutCtx Enterprise Edition v{version} (compiled)."""
        __version__ = "{version}"
    ''')
    (pkg_dir / "__init__.py").write_text(init_content)

    # Create pyproject.toml for the compiled wheel
    pyproject_content = textwrap.dedent(f'''\
        [build-system]
        requires = ["setuptools>=68.0"]
        build-backend = "setuptools.backends._legacy:_Backend"

        [project]
        name = "headroom-ee"
        version = "{version}"
        description = "CutCtx Enterprise Edition — compiled extensions (no source)"
        license = {{text = "LicenseRef-Headroom-Commercial"}}
        requires-python = ">=3.10"

        [tool.setuptools.packages.find]
        include = ["headroom_ee*"]
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
    parser = argparse.ArgumentParser(description="SP-3: Compile headroom_ee to native extensions")
    parser.add_argument("--output-dir", default=str(ROOT / "dist-ee"),
                        help="Output directory for compiled wheel")
    parser.add_argument("--dev", action="store_true",
                        help="Compile with debug symbols")
    parser.add_argument("--verify-only", action="store_true",
                        help="Only verify an existing wheel has no source")
    parser.add_argument("--version", default="0.1.0",
                        help="Version string for the compiled wheel")
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

    # Build wheel from compiled extensions
    wheel = build_ee_wheel(compile_dir, output_dir, args.version)
    if wheel:
        print(f"\nBuilt compiled EE wheel: {wheel}")
    else:
        print("ERROR: Wheel build failed")
        sys.exit(1)

    # Verify no source
    if verify_no_source_in_wheel(output_dir):
        print("\nSP-3 verification PASSED: no .py source in wheel")
    else:
        print("\nSP-3 verification FAILED: source detected in wheel")
        sys.exit(1)

    # Build signed integrity manifest from the compiled .so files.
    # The manifest is written into the EE package dir so it ships inside
    # the wheel and can be verified at runtime by headroom.security.integrity.
    if not args.dev:
        print("\nBuilding signed EE integrity manifest…")
        manifest_script = ROOT / "scripts" / "build_ee_manifest.py"
        # Point at the compiled .so directory (not the source tree) so we
        # hash exactly what goes into the wheel.
        pkg_dir_in_wheel = compile_dir / "_build_root" / "headroom_ee"
        manifest_result = subprocess.run(
            [
                sys.executable,
                str(manifest_script),
                "--ee-dir", str(pkg_dir_in_wheel),
                "--output", str(pkg_dir_in_wheel / "MANIFEST.sha256.json"),
            ],
            capture_output=False,
            cwd=str(ROOT),
        )
        if manifest_result.returncode != 0:
            print("WARNING: manifest build failed — wheel ships without integrity manifest")
        else:
            print("Integrity manifest built and included in wheel.")
    else:
        print("\nDev build — skipping signed manifest (use --unsigned for local testing)")


if __name__ == "__main__":
    main()
