"""Train a calibrated model-routing confidence artifact from shadow evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cutctx.proxy.model_routing_evals import ModelRoutingEvalStore
from cutctx.proxy.model_routing_training import train_linear_routing_artifact


def train(
    evidence_path: str | Path,
    output_path: str | Path,
    *,
    quality_floor: float = 0.8,
    minimum_samples: int = 20,
    minimum_mean_quality: float = 0.9,
    maximum_unsafe_rate: float = 0.01,
    minimum_segment_samples: int = 20,
) -> dict[str, object]:
    records = ModelRoutingEvalStore(evidence_path).load()
    artifact = train_linear_routing_artifact(
        records,
        quality_floor=quality_floor,
        minimum_samples=minimum_samples,
        minimum_mean_quality=minimum_mean_quality,
        maximum_unsafe_rate=maximum_unsafe_rate,
        minimum_segment_samples=minimum_segment_samples,
    )
    artifact.save(output_path)
    return artifact.to_dict()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--quality-floor", type=float, default=0.8)
    parser.add_argument("--minimum-samples", type=int, default=20)
    parser.add_argument("--minimum-mean-quality", type=float, default=0.9)
    parser.add_argument("--maximum-unsafe-rate", type=float, default=0.01)
    parser.add_argument("--minimum-segment-samples", type=int, default=20)
    args = parser.parse_args()
    try:
        result = train(
            args.evidence,
            args.output,
            quality_floor=args.quality_floor,
            minimum_samples=args.minimum_samples,
            minimum_mean_quality=args.minimum_mean_quality,
            maximum_unsafe_rate=args.maximum_unsafe_rate,
            minimum_segment_samples=args.minimum_segment_samples,
        )
    except ValueError as exc:
        print(json.dumps({"promoted": False, "reason": str(exc)}, indent=2))
        return 2
    print(json.dumps({"promoted": True, "artifact": result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
