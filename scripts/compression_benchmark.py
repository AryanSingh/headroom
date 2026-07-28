#!/usr/bin/env python3
"""Compare our compressors against published and trivial baselines.

Two things make a compression comparison meaningless, and this script avoids
both.

**Unmatched ratios.** Whoever compresses less looks better on quality. Every
system here is driven to the same per-case token budget, and the achieved
ratio is reported so you can confirm they actually landed together.

**No floor.** "We beat LLMLingua" means little without knowing what *nothing
clever at all* scores. Truncation and random selection are included for
exactly that: if a sophisticated compressor cannot beat keeping the first N
tokens, it is not earning its complexity.

Systems compared:

  head / tail        keep the first / last tokens (trivial controls)
  random             keep random sentences at the budget (chance floor)
  router             our default structural path, no ML
  router+kompress    our ML path (`--enable-kompress`)
  llmlingua2         Microsoft LLMLingua-2, the published baseline

Quality metric is information recall: probes generated from the original,
counted if they survive compression. Offline, no API key. It measures fidelity,
not downstream task accuracy.

Usage::

    python scripts/compression_benchmark.py --dataset hotpotqa -n 60
    python scripts/compression_benchmark.py --all -n 60 --json out.json
"""

from __future__ import annotations

import argparse
import json
import random
import re
import statistics
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from cutctx.evals.datasets import (  # noqa: E402
    generate_retrieval_probes,
    load_hotpotqa,
    load_longbench,
)
from cutctx.transforms.content_router import (  # noqa: E402
    ContentRouter,
    ContentRouterConfig,
    token_len,
)

_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE.split(text) if s.strip()]


def _fill_to_budget(units: list[str], budget: int) -> list[str]:
    out, spend = [], 0
    for unit in units:
        cost = token_len(unit)
        if spend + cost > budget:
            continue
        out.append(unit)
        spend += cost
    return out


def keep_head(text: str, _query: str, budget: int) -> str:
    return "\n\n".join(_fill_to_budget(_sentences(text), budget))


def keep_tail(text: str, _query: str, budget: int) -> str:
    kept = _fill_to_budget(list(reversed(_sentences(text))), budget)
    return "\n\n".join(reversed(kept))


def keep_random(text: str, _query: str, budget: int, *, seed: int = 42) -> str:
    units = _sentences(text)
    order = list(range(len(units)))
    random.Random(seed).shuffle(order)
    picked, spend = set(), 0
    for i in order:
        cost = token_len(units[i])
        if spend + cost > budget:
            continue
        picked.add(i)
        spend += cost
    return "\n\n".join(u for i, u in enumerate(units) if i in picked)


def _recall(original: str, compressed: str, probes: int = 8) -> float | None:
    found = generate_retrieval_probes(original, n_probes=probes)
    if not found:
        return None
    return sum(1 for p in found if p.lower() in compressed.lower()) / len(found)


def _measure(
    name: str, fn: Callable[[Any, int], str], cases: list[Any], budgets: list[int]
) -> dict[str, Any]:
    ratios, recalls, timings = [], [], []
    for case, budget in zip(cases, budgets, strict=True):
        started = time.perf_counter()
        out = fn(case, budget)
        timings.append((time.perf_counter() - started) * 1000)
        ratios.append(token_len(out) / max(1, token_len(case.context)))
        score = _recall(case.context, out)
        if score is not None:
            recalls.append(score)
    return {
        "system": name,
        "n": len(cases),
        "ratio": round(statistics.mean(ratios), 4),
        "recall": round(statistics.mean(recalls), 4) if recalls else None,
        "recall_stdev": round(statistics.stdev(recalls), 4) if len(recalls) > 1 else None,
        "ms_per_case": round(statistics.mean(timings), 1),
    }


def run_dataset(name: str, cases: list[Any], *, skip_slow: bool = False) -> list[dict[str, Any]]:
    router = ContentRouter(ContentRouterConfig())

    # Our default path runs first; its per-case output size becomes the budget
    # every other system must hit.
    budgets = [token_len(router.compress(c.context, context=c.query).compressed) for c in cases]

    systems: list[tuple[str, Callable[[Any, int], str]]] = [
        ("head", lambda c, b: keep_head(c.context, c.query, b)),
        ("tail", lambda c, b: keep_tail(c.context, c.query, b)),
        ("random", lambda c, b: keep_random(c.context, c.query, b)),
        ("router", lambda c, _b: router.compress(c.context, context=c.query).compressed),
    ]

    if not skip_slow:
        ml = ContentRouter(ContentRouterConfig(enable_kompress=True))
        systems.append(
            ("router+kompress", lambda c, _b: ml.compress(c.context, context=c.query).compressed)
        )
        try:
            from cutctx.transforms.llmlingua_compressor import LLMLinguaCompressor

            lingua = LLMLinguaCompressor()
            systems.append(
                (
                    "llmlingua2",
                    lambda c, b: lingua.compress(
                        c.context,
                        question=c.query,
                        target_ratio=b / max(1, token_len(c.context)),
                    ).compressed,
                )
            )
        except Exception as exc:  # pragma: no cover - optional dependency
            print(f"  (llmlingua unavailable: {type(exc).__name__})", file=sys.stderr)

    return [_measure(label, fn, cases, budgets) for label, fn in systems]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="hotpotqa", choices=["hotpotqa", "longbench"])
    parser.add_argument("--all", action="store_true", help="run every dataset")
    parser.add_argument("-n", type=int, default=60)
    parser.add_argument("--fast", action="store_true", help="skip the ML systems")
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()

    loaders = {"hotpotqa": load_hotpotqa, "longbench": load_longbench}
    chosen = list(loaders) if args.all else [args.dataset]

    everything: dict[str, list[dict[str, Any]]] = {}
    for name in chosen:
        try:
            cases = list(loaders[name](n=args.n))
        except Exception as exc:
            print(f"{name}: unavailable ({type(exc).__name__}) — skipped", file=sys.stderr)
            continue
        rows = run_dataset(name, cases, skip_slow=args.fast)
        everything[name] = rows
        print(f"\n{name} (n={len(cases)}, budgets matched per case)")
        print(f"  {'system':18}{'ratio':>8}{'recall':>9}{'stdev':>8}{'ms/case':>10}")
        for row in sorted(rows, key=lambda r: -(r["recall"] or 0)):
            stdev = f"{row['recall_stdev']:.3f}" if row["recall_stdev"] is not None else "  -  "
            print(
                f"  {row['system']:18}{row['ratio']:>8.3f}{row['recall']:>9.3f}"
                f"{stdev:>8}{row['ms_per_case']:>10.0f}"
            )

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(everything, indent=2))
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
