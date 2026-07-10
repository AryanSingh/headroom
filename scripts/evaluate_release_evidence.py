from __future__ import annotations

import argparse
import json
from pathlib import Path

from cutctx.evals.release_evidence import evaluate_release_evidence


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Cutctx release evidence posture.")
    parser.add_argument("--partner-snapshot", action="append", default=[])
    parser.add_argument("--output", default="artifacts/release-evidence-status.json")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    payload = evaluate_release_evidence(
        root=root,
        partner_snapshot_paths=[Path(path) for path in args.partner_snapshot],
    )
    output = root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
