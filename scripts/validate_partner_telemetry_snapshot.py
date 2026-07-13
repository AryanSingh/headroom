"""Validate an anonymized seven-day Agent Context Report for release evidence."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from cutctx.evals.partner_telemetry import validate_partner_snapshot


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: validate_partner_telemetry_snapshot.py SNAPSHOT.json")
    payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    validate_partner_snapshot(payload)
    print(json.dumps({"status": "valid", "snapshot": sys.argv[1]}, indent=2))


if __name__ == "__main__":
    main()
