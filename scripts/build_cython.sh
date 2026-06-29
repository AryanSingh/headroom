#!/usr/bin/env bash
# Compile core Python modules to native extensions via Cython.
#
# Run this after `maturin build` but before packaging the wheel.
# The resulting .so files replace their .py counterparts in the
# installed package, making the source non-trivially recoverable.
#
# Usage:
#   ./scripts/build_cython.sh [--inplace] [--output-dir <dir>]
#
# Options:
#   --inplace     Build .so files next to their source (dev mode)
#   --output-dir  Copy compiled extensions here (default: skip copy)
#
# Requirements:
#   pip install cython

set -euo pipefail

INPLACE=0
OUTPUT_DIR=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --inplace) INPLACE=1; shift ;;
    --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

PYTHON="${PYTHON:-python3}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! "$PYTHON" -c "import Cython" 2>/dev/null; then
  echo "ERROR: Cython not found. Install with: pip install cython" >&2
  exit 1
fi

# Core modules to compile — these contain algorithmic IP.
# Paths are relative to repo root.
TARGETS=(
  "cutctx/compression/universal.py"
  "cutctx/compression/detector.py"
  "cutctx/compression/handlers/code_handler.py"
  "cutctx/compression/handlers/json_handler.py"
  "cutctx/proxy/intelligence_pipeline.py"
)

BUILD_DIR="$REPO_ROOT/build/cython"
mkdir -p "$BUILD_DIR"

echo "── Cython compilation ─────────────────────────────────────────────"
echo "Targets: ${#TARGETS[@]} modules"

COMPILED=()

for target in "${TARGETS[@]}"; do
  src="$REPO_ROOT/$target"
  if [[ ! -f "$src" ]]; then
    echo "  SKIP (not found): $target"
    continue
  fi

  module_dir="$(dirname "$src")"
  module_base="$(basename "$src" .py)"

  echo "  Compiling: $target"

  # Step 1: .py → .c
  "$PYTHON" -m cython \
    --3str \
    --directive language_level=3 \
    --directive boundscheck=False \
    --directive wraparound=False \
    --directive cdivision=True \
    --directive embedsignature=False \
    --directive annotation_typing=False \
    -o "$BUILD_DIR/${module_base}.c" \
    "$src"

  # Step 2: .c → .so  (uses same Python/CC as the running interpreter)
  "$PYTHON" - <<PYEOF
import sys, os, sysconfig
from distutils.core import Distribution
from distutils.extension import Extension
from distutils.command.build_ext import build_ext

ext = Extension(
    name="$module_base",
    sources=["$BUILD_DIR/${module_base}.c"],
    extra_compile_args=["-O2", "-fvisibility=hidden"],
)

dist = Distribution(attrs={"name": "$module_base", "ext_modules": [ext]})
cmd = build_ext(dist)
cmd.inplace = ${INPLACE}
cmd.build_lib = "$BUILD_DIR/lib"
cmd.build_temp = "$BUILD_DIR/tmp"
cmd.ensure_finalized()
cmd.run()

# Find and report the output .so
import glob
so_pattern = "$BUILD_DIR/lib/${module_base}*.so"
found = glob.glob(so_pattern)
if not found:
    # distutils may put it inplace
    so_pattern2 = "$(dirname "$src")/${module_base}*.so"
    found = glob.glob(so_pattern2)
if found:
    print(f"    → {found[0]}")
PYEOF

  COMPILED+=("$target")
done

echo ""
echo "Compiled ${#COMPILED[@]}/${#TARGETS[@]} modules."

if [[ -n "$OUTPUT_DIR" ]]; then
  echo "Copying .so files → $OUTPUT_DIR"
  mkdir -p "$OUTPUT_DIR"
  find "$BUILD_DIR/lib" -name "*.so" -exec cp {} "$OUTPUT_DIR/" \; 2>/dev/null || true
fi

echo "── Done ───────────────────────────────────────────────────────────"
echo ""
echo "To replace .py with .so in a wheel, run:"
echo "  python scripts/inject_cython_into_wheel.py dist/*.whl"
