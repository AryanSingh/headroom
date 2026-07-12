"""Build a quality/cost frontier from model-routing shadow evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cutctx.proxy.model_routing_evals import (
    ModelRoutingEvalStore,
    build_quality_cost_frontier,
    build_segmented_recommendations,
    recommend_confidence_threshold,
)


def evaluate(
    path: str | Path,
    *,
    minimum_mean_quality: float = 0.9,
    maximum_unsafe_rate: float = 0.01,
    quality_floor: float = 0.8,
    minimum_segment_samples: int = 20,
) -> dict[str, object]:
    records = ModelRoutingEvalStore(path).load()
    return {
        "schema_version": 1,
        "samples": len(records),
        "constraints": {
            "minimum_mean_quality": minimum_mean_quality,
            "maximum_unsafe_rate": maximum_unsafe_rate,
            "quality_floor": quality_floor,
        },
        "recommendation": recommend_confidence_threshold(
            records,
            minimum_mean_quality=minimum_mean_quality,
            maximum_unsafe_rate=maximum_unsafe_rate,
            quality_floor=quality_floor,
        ),
        "frontier": build_quality_cost_frontier(records, quality_floor=quality_floor),
        "segmented": build_segmented_recommendations(
            records,
            minimum_samples=minimum_segment_samples,
            minimum_mean_quality=minimum_mean_quality,
            maximum_unsafe_rate=maximum_unsafe_rate,
            quality_floor=quality_floor,
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--minimum-mean-quality", type=float, default=0.9)
    parser.add_argument("--maximum-unsafe-rate", type=float, default=0.01)
    parser.add_argument("--quality-floor", type=float, default=0.8)
    parser.add_argument("--minimum-segment-samples", type=int, default=20)
    args = parser.parse_args()

    result = evaluate(
        args.path,
        minimum_mean_quality=args.minimum_mean_quality,
        maximum_unsafe_rate=args.maximum_unsafe_rate,
        quality_floor=args.quality_floor,
        minimum_segment_samples=args.minimum_segment_samples,
    )
    rendered = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n")
    print(rendered)
    return 0 if result["recommendation"] is not None else 2


if __name__ == "__main__":
    raise SystemExit(main())
