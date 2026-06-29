#!/usr/bin/env python3
"""Replace .py source files in a wheel with compiled Cython .so extensions.

Usage:
    python scripts/inject_cython_into_wheel.py dist/cutctx_ai-*.whl

The script reads a .whl (zip archive), removes the .py files for any module
that has a compiled counterpart in build/cython/lib/, inserts the .so, and
rewrites the RECORD file. The original wheel is replaced in-place.
"""
from __future__ import annotations

import glob
import hashlib
import os
import re
import shutil
import sys
import tempfile
import zipfile
from base64 import urlsafe_b64encode
from pathlib import Path


def _sha256_record(path: Path) -> str:
    data = path.read_bytes()
    digest = hashlib.sha256(data).digest()
    return "sha256=" + urlsafe_b64encode(digest).rstrip(b"=").decode()


def inject(wheel_path: str, so_dir: str = "build/cython/lib") -> None:
    wheel = Path(wheel_path)
    so_root = Path(so_dir)
    if not so_root.exists():
        print(f"  SKIP {wheel.name}: no .so dir at {so_root}")
        return

    # Map base module name → .so path
    so_map: dict[str, Path] = {}
    for so in so_root.glob("*.so"):
        # strip cpython/abi tags: foo.cpython-312-darwin.so → foo
        base = re.sub(r"\.cpython-\d+.*|\.abi3.*", "", so.stem)
        so_map[base] = so

    if not so_map:
        print(f"  SKIP {wheel.name}: no .so files found in {so_root}")
        return

    print(f"Processing {wheel.name} ({len(so_map)} compiled modules)")

    tmp = Path(tempfile.mkdtemp())
    new_wheel = tmp / wheel.name

    try:
        with zipfile.ZipFile(wheel, "r") as zin, zipfile.ZipFile(new_wheel, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            record_name = None
            record_lines: list[str] = []
            extra_entries: list[tuple[str, Path]] = []  # (arcname, path)

            for info in zin.infolist():
                name = info.filename

                # Detect RECORD file
                if re.search(r"\.dist-info/RECORD$", name):
                    record_name = name
                    record_lines = zin.read(name).decode().splitlines()
                    continue  # rewrite later

                # Check if this .py has a compiled replacement
                if name.endswith(".py") and not name.endswith("__init__.py"):
                    stem = Path(name).stem
                    if stem in so_map:
                        print(f"  replace {name}")
                        # Schedule .so insertion with matching directory
                        pkg_dir = str(Path(name).parent)
                        so_arcname = f"{pkg_dir}/{so_map[stem].name}"
                        extra_entries.append((so_arcname, so_map[stem]))
                        continue  # drop original .py

                zout.writestr(info, zin.read(name))

            # Add compiled extensions
            for arcname, so_path in extra_entries:
                zout.write(so_path, arcname)

            # Rewrite RECORD
            if record_name:
                # Remove old entries for replaced files and their .pyc
                new_records: list[str] = []
                replaced_stems = {so_map[s].stem.split(".")[0] for s in so_map}
                for line in record_lines:
                    parts = line.split(",")
                    if not parts:
                        continue
                    fname = parts[0]
                    stem_check = Path(fname).stem
                    # drop .py and .pyc for replaced modules
                    if (fname.endswith(".py") or fname.endswith(".pyc")) and stem_check in replaced_stems:
                        continue
                    new_records.append(line)

                # Add entries for .so files
                for arcname, so_path in extra_entries:
                    size = so_path.stat().st_size
                    digest = _sha256_record(so_path)
                    new_records.append(f"{arcname},{digest},{size}")

                # RECORD itself has empty hash
                new_records.append(f"{record_name},,")

                zout.writestr(record_name, "\n".join(new_records) + "\n")

        shutil.move(str(new_wheel), str(wheel))
        print(f"  ✓ Wrote {wheel.name}")

    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    wheels = sys.argv[1:]
    if not wheels:
        wheels = glob.glob("dist/*.whl")

    if not wheels:
        print("Usage: inject_cython_into_wheel.py <wheel.whl> ...")
        sys.exit(1)

    for w in wheels:
        inject(w)
