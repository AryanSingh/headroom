#!/usr/bin/env bash
# Compatibility shim for the retired standalone-binary installer.
#
# The repository does not publish a standalone binary that implements the full
# public `cutctx` CLI. In particular, the Rust `cutctx-proxy` binary is not a
# replacement for the Python CLI and must never be installed under that name.

set -euo pipefail

VERSION=""
PREFIX=""
SEEN_VERSION=0
SEEN_PREFIX=0

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<'EOF'
Usage: install-binary.sh [--version VERSION] [--prefix PATH]

This compatibility shim does not download or execute binaries. The former
standalone artifact did not implement the full public `cutctx` CLI.

Options:
  --version VERSION  Pin the supported package-manager command to VERSION.
  --prefix PATH      Show a prefix-aware pipx command.
  -h, --help         Show this help text.
EOF
}

shell_quote() {
  local escaped
  escaped="${1//\'/\'\\\'\'}"
  printf "'%s'" "$escaped"
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --version)
      [[ "$SEEN_VERSION" -eq 0 ]] || die "Duplicate option: --version"
      [[ "$#" -ge 2 && -n "$2" && "$2" != -* ]] || die "--version requires a value"
      VERSION="$2"
      SEEN_VERSION=1
      shift 2
      ;;
    --version=*)
      [[ "$SEEN_VERSION" -eq 0 ]] || die "Duplicate option: --version"
      VERSION="${1#*=}"
      [[ -n "$VERSION" && "$VERSION" != -* ]] || die "--version requires a value"
      SEEN_VERSION=1
      shift
      ;;
    --prefix)
      [[ "$SEEN_PREFIX" -eq 0 ]] || die "Duplicate option: --prefix"
      [[ "$#" -ge 2 && -n "$2" && "$2" != -* ]] || die "--prefix requires a value"
      PREFIX="$2"
      SEEN_PREFIX=1
      shift 2
      ;;
    --prefix=*)
      [[ "$SEEN_PREFIX" -eq 0 ]] || die "Duplicate option: --prefix"
      PREFIX="${1#*=}"
      [[ -n "$PREFIX" && "$PREFIX" != -* ]] || die "--prefix requires a value"
      SEEN_PREFIX=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown option: $1"
      ;;
  esac
done

if [[ -n "$VERSION" && ! "$VERSION" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]]; then
  die "Invalid version: $VERSION"
fi

PACKAGE='cutctx-ai[proxy]'
if [[ -n "$VERSION" ]]; then
  PACKAGE="${PACKAGE}==${VERSION}"
fi

{
  printf '%s\n\n' 'ERROR: Standalone binary installation is not supported.'
  printf '%s\n' 'The previously advertised binary did not implement the full cutctx CLI.'
  printf '%s\n\n' 'Install the supported Python package with one of these commands:'
  printf '  uv tool install --python 3.13 "%s"\n' "$PACKAGE"
  printf '  pipx install --python python3.13 "%s"\n' "$PACKAGE"

  if [[ -n "$PREFIX" ]]; then
    printf '\nFor the requested prefix:\n'
    printf '  PIPX_BIN_DIR=%s PIPX_HOME=%s pipx install --python python3.13 "%s"\n' \
      "$(shell_quote "$PREFIX/bin")" \
      "$(shell_quote "$PREFIX/share/pipx")" \
      "$PACKAGE"
  fi

  printf '\nThen verify the full CLI with: cutctx --help\n'
} >&2

exit 1
