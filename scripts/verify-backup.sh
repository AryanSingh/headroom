#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Cutctx Backup Verification Script
#
# Verifies SQLite backup integrity for the durable workspace databases that
# the k8s/backup-cronjob.yaml daily backup targets.
#
# The backup job now covers all known persistent SQLite stores in the
# workspace root, not just the original three critical files.
#
# Can check local files or download the latest backup from S3.
# Exits non-zero if any check fails — suitable for CI/cron monitoring.
#
# Usage:
#   ./scripts/verify-backup.sh                              # check local DBs
#   ./scripts/verify-backup.sh --s3-bucket cutctx-backups   # check latest S3 backups
#   ./scripts/verify-backup.sh /path/to/backup.db            # check one file
#   ./scripts/verify-backup.sh --strict                      # fail if expected DBs missing
#   ./scripts/verify-backup.sh --dry-run                     # dry-run mode
#   ./scripts/verify-backup.sh --help                        # this message
#
# Dependencies: sqlite3, aws-cli (only for --s3-bucket), date
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Config defaults ─────────────────────────────────────────────────────────
S3_BUCKET=""
DRY_RUN=false
VERBOSE=false
STRICT=false
EXIT_CODE=0
CHECKED_COUNT=0
TMPDIR="${TMPDIR:-/tmp}/cutctx-backup-verify"

# Clean up temp files on exit
cleanup() { rm -rf "$TMPDIR" 2>/dev/null; }
trap cleanup EXIT

# Default local paths (overridable via CUTCTX_DATA_DIR env var)
DATA_DIR="${CUTCTX_DATA_DIR:-${HOME:-/tmp}/.cutctx}"
DB_NAMES=(
  "cutctx.db"
  "cutctx_memory.db"
  "cutctx_memory_graph.db"
  "cutctx_memory_vectors.db"
  "spend_ledger.db"
  "audit.db"
  "rbac.db"
  "org.db"
  "fleet.db"
  "scim.db"
  "ccr.db"
  "prefix_tracker.db"
  "assurance.ledger.db"
  "episodes.db"
  "policies.db"
  "secrets.db"
  "webhooks.db"
  "webhook_dlq.db"
)

DEFAULT_DBS=()
for db_name in "${DB_NAMES[@]}"; do
  DEFAULT_DBS+=("${DATA_DIR}/${db_name}")
done

# ── Help ────────────────────────────────────────────────────────────────────
show_help() {
  sed -n '2,24p' "$0"
  exit 0
}

# ── Logging helpers ─────────────────────────────────────────────────────────
info()  { printf "  [INFO]  %s\n" "$*"; }
warn()  { printf "  [WARN]  %s\n" "$*" >&2; }
fail()  { printf "  [FAIL]  %s\n" "$*" >&2; EXIT_CODE=1; }
ok()    { printf "  [OK]    %s\n" "$*"; }
dry()   { printf "  [DRY]   %s\n" "$*"; }

# ── Parse arguments ─────────────────────────────────────────────────────────
FILES=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h)    show_help ;;
    --dry-run)    DRY_RUN=true; shift ;;
    --strict|--require-all) STRICT=true; shift ;;
    --verbose|-v) VERBOSE=true; shift ;;
    --s3-bucket)  S3_BUCKET="$2"; shift 2 ;;
    --*)          warn "Unknown option: $1"; shift ;;
    *)            FILES+=("$1"); shift ;;
  esac
done

# ── Verify a single SQLite database ─────────────────────────────────────────
verify_db() {
  local db_path="$1"
  local label="$2"

  if [[ ! -f "$db_path" ]]; then
    if $STRICT; then
      fail "${label}: required file not found: ${db_path}"
    else
      warn "File not found: ${db_path} (${label}) — skipping"
    fi
    return
  fi

  local size
  size=$(stat -f%z "$db_path" 2>/dev/null || stat -c%s "$db_path" 2>/dev/null || echo "0")
  if [[ "$size" -lt 100 ]]; then
    fail "${label}: file too small (${size} bytes) — likely corrupt or empty"
    return
  fi

  if $DRY_RUN; then
    CHECKED_COUNT=$((CHECKED_COUNT + 1))
    dry "Would verify: ${label} (${db_path}, ${size} bytes)"
    return
  fi

  # Run integrity check
  local result
  result=$(sqlite3 "$db_path" "PRAGMA integrity_check;" 2>&1) || true

  if [[ "$result" == "ok" ]]; then
    CHECKED_COUNT=$((CHECKED_COUNT + 1))
    ok "${label}: integrity check passed (${db_path}, $(numfmt_size $size))"
  else
    fail "${label}: integrity check FAILED — ${result}"
  fi

  # Quick structural check: verify the DB has at least one table
  if [[ "$result" == "ok" ]]; then
    local table_count
    table_count=$(sqlite3 "$db_path" "SELECT COUNT(*) FROM sqlite_master WHERE type='table';" 2>/dev/null || echo "0")
    if [[ "$table_count" -eq 0 ]]; then
      warn "${label}: database has no tables (might be empty or wrong format)"
    fi
  fi
}

# ── numfmt_size: format bytes to human-readable ─────────────────────────────
numfmt_size() {
  local bytes=$1
  if (( bytes >= 1073741824 )); then
    echo "$(( bytes / 1073741824 ))G"
  elif (( bytes >= 1048576 )); then
    echo "$(( bytes / 1048576 ))M"
  elif (( bytes >= 1024 )); then
    echo "$(( bytes / 1024 ))K"
  else
    echo "${bytes}B"
  fi
}

# ── Fetch and verify S3 backups ─────────────────────────────────────────────
verify_s3_backups() {
  local bucket="$1"

  if ! command -v aws &>/dev/null; then
    fail "aws-cli is required for --s3-bucket mode"
    return
  fi

  # DB name patterns that match backup-cronjob.yaml
  local db_names=(
    "cutctx.db"
    "cutctx_memory.db"
    "cutctx_memory_graph.db"
    "cutctx_memory_vectors.db"
    "spend_ledger.db"
    "audit.db"
    "rbac.db"
    "org.db"
    "fleet.db"
    "scim.db"
    "ccr.db"
    "prefix_tracker.db"
    "assurance.ledger.db"
    "episodes.db"
    "policies.db"
    "secrets.db"
    "webhooks.db"
    "webhook_dlq.db"
  )

  for db_name in "${db_names[@]}"; do
    info "Fetching latest ${db_name} backup from s3://${bucket}/ ..."

    local latest_key
    latest_key=$(aws s3api list-objects-v2 \
      --bucket "$bucket" \
      --prefix "${db_name}-" \
      --query "sort_by(Contents, &LastModified)[-1].Key" \
      --output text 2>&1) || {
      fail "S3 query failed for database '${db_name}' (s3://${bucket}/) — check credentials and bucket permissions"
      continue
    }

    if [[ -z "$latest_key" || "$latest_key" == "None" ]]; then
      if $STRICT; then
        fail "No backup found for required database '${db_name}' in s3://${bucket}/"
      else
        warn "No backup found for database '${db_name}' in s3://${bucket}/"
      fi
      continue
    fi

    mkdir -p "$TMPDIR"
    local local_path="${TMPDIR}/$(basename "$latest_key")"

    if $DRY_RUN; then
      dry "Would download s3://${bucket}/${latest_key} → ${local_path}"
      continue
    fi

    aws s3 cp "s3://${bucket}/${latest_key}" "$local_path" --quiet
    info "Downloaded s3://${bucket}/${latest_key} (${local_path})"

    verify_db "$local_path" "S3-backup:${db_name}"
  done
}

# ── Main ────────────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════"
echo "  Cutctx Backup Verification"
echo "═══ $(date -u '+%Y-%m-%d %H:%M:%S UTC') ═══"
echo ""

if ${DRY_RUN}; then
  echo "  MODE: dry-run (no changes made)"
  echo ""
fi

# Determine what to check
if [[ -n "$S3_BUCKET" ]]; then
  # S3 mode
  verify_s3_backups "$S3_BUCKET"

elif [[ ${#FILES[@]} -gt 0 ]]; then
  # Explicit file list
  for file in "${FILES[@]}"; do
    verify_db "$file" "$(basename "$file")"
  done

else
  # Default: check local data directory
  info "Checking default locations under DATA_DIR=${DATA_DIR}"
  for db in "${DEFAULT_DBS[@]}"; do
    verify_db "$db" "$(basename "$db" .db)"
  done
fi

# Summary
echo ""
if [[ "$CHECKED_COUNT" -eq 0 ]]; then
  fail "No databases were verified"
fi

if [[ "$EXIT_CODE" -eq 0 ]]; then
  echo "  ✅ All checks passed"
else
  echo "  ❌ Some checks failed (exit code ${EXIT_CODE})"
fi
echo "═══════════════════════════════════════════════════════"
echo ""

exit "$EXIT_CODE"
