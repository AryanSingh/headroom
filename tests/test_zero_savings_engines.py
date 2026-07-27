"""Four opt-in engines reported 0%. None of them was "not applicable".

Each shipped enabled-but-inert, and each failed in a way that looked identical
from outside — a flag you could turn on, no error, no saving:

* **drain3** — ``miner.add_log_message()`` returns a dict, but the code read
  ``result.cluster_id``. Every line raised AttributeError into a per-line
  handler that assigned ``hash(line)`` as a fallback cluster, so 600
  identical-shaped lines became 600 clusters. Worse, the router assigned
  drain3's output unconditionally, making the standard log path unreachable:
  turning ``--drain3`` on took log compression from 99.8% to 0%.

* **difftastic** — invoked with difft's default side-by-side display, which is
  reliably ~2x larger than the unified diff it replaces, so the never-enlarge
  guard rejected 100% of results.

* **dedup** — skipped any message whose ``content`` was not a ``str``. Real
  Anthropic messages carry a list of blocks, and a repeated ``tool_result``
  is always a block, so it never saw the content it exists to collapse.

* **context_budget** — counted only ``block["text"]``. A ``tool_result``
  stores its payload under ``content``, so tool output counted as zero tokens,
  the controller never left the GREEN zone, and the ceiling was never
  enforced.

These tests pin each engine against a payload it is supposed to handle.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

import pytest

from cutctx.transforms.content_router import (
    ContentRouter,
    ContentRouterConfig,
    token_len,
)


def _wire(text: str) -> int:
    return token_len(json.dumps(text))


def _rows(n: int = 200) -> str:
    return json.dumps([{"id": i, "name": f"row-{i}", "state": "active"} for i in range(n)])


# ---------------------------------------------------------------------------
# drain3
# ---------------------------------------------------------------------------


def _uniform_logs(n: int = 600) -> str:
    return "\n".join(
        f"2026-07-27T10:{i // 60:02d}:{i % 60:02d}Z INFO worker-{i % 8} "
        f"handled req_{i} status=200 dur={i % 97}ms"
        for i in range(n)
    )


def test_drain3_clusters_similar_lines_instead_of_one_each() -> None:
    """600 lines of one shape must not produce 600 clusters."""
    pytest.importorskip("drain3")
    from cutctx.transforms.drain3_compressor import Drain3LogCompressor

    result = Drain3LogCompressor()._drain3_compress(_uniform_logs())

    assert result.original_line_count == 600
    assert result.clusters_found < 10, (
        f"expected a handful of clusters, got {result.clusters_found} — "
        "mined results are being read with the wrong accessor"
    )


def test_enabling_drain3_never_makes_log_compression_worse() -> None:
    """The regression that mattered: --drain3 took logs from 99.8% to 0%."""
    pytest.importorskip("drain3")
    logs = _uniform_logs()

    baseline = ContentRouter(ContentRouterConfig()).compress(logs)
    with_drain3 = ContentRouter(ContentRouterConfig(use_drain3=True)).compress(logs)

    baseline_saving = 1 - _wire(baseline.compressed) / _wire(logs)
    drain3_saving = 1 - _wire(with_drain3.compressed) / _wire(logs)
    assert baseline_saving > 0.9, "fixture should compress well without drain3"
    assert drain3_saving > 0.9, (
        f"enabling drain3 collapsed savings from {baseline_saving:.1%} to {drain3_saving:.1%}"
    )


def test_drain3_helps_on_heterogeneous_logs() -> None:
    """Mixed templates are drain3's actual purpose."""
    pytest.importorskip("drain3")
    mixed = "\n".join(
        (
            f"2026-07-27T10:00:{i % 60:02d}Z ERROR db timeout after {i}ms on shard-{i % 4}"
            if i % 5 == 0
            else f"2026-07-27T10:00:{i % 60:02d}Z INFO worker-{i % 8} handled req_{i} status=200"
        )
        for i in range(600)
    )

    baseline = ContentRouter(ContentRouterConfig()).compress(mixed)
    with_drain3 = ContentRouter(ContentRouterConfig(use_drain3=True)).compress(mixed)

    assert _wire(with_drain3.compressed) <= _wire(baseline.compressed)


# ---------------------------------------------------------------------------
# difftastic
# ---------------------------------------------------------------------------


def _unified_diff(old: str, new: str) -> str:
    tmp = Path(tempfile.mkdtemp())
    (tmp / "a.py").write_text(old)
    (tmp / "b.py").write_text(new)
    return subprocess.run(
        ["git", "diff", "--no-index", "--", str(tmp / "a.py"), str(tmp / "b.py")],
        capture_output=True,
        text=True,
    ).stdout


def test_difftastic_shrinks_a_reformatting_heavy_diff() -> None:
    """Its canonical win case, which side-by-side display always lost."""
    from cutctx.proxy.interceptors.difftastic_interceptor import DifftasticInterceptor

    interceptor = DifftasticInterceptor()
    if interceptor._get_exe() is None:
        pytest.skip("difft binary not available")
    diff = _unified_diff(
        "\n".join(f"def fn_{i}(a,b):\n    return a+b+{i}" for i in range(60)),
        "\n".join(
            f"def fn_{i}(\n    a,\n    b,\n):\n    return a + b + {i if i != 30 else 999}"
            for i in range(60)
        ),
    )

    out = interceptor.transform("Bash", {"command": "git diff"}, diff)

    assert out is not None, "difftastic declined a diff it should compress well"
    assert len(out) < len(diff) * 0.5


# ---------------------------------------------------------------------------
# dedup
# ---------------------------------------------------------------------------


def _tool_result_turns(block: str, turns: int = 3) -> list[dict]:
    return [
        {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": f"t{i}", "content": block}],
        }
        for i in range(turns)
    ]


def test_dedup_collapses_repeated_tool_results() -> None:
    from cutctx.dedup import SessionDeduplicator

    messages = _tool_result_turns(_rows())

    result = SessionDeduplicator().process(messages)

    assert result.dedup_count == 2, "the 2nd and 3rd identical tool_result should collapse"
    before = token_len(json.dumps(messages))
    after = token_len(json.dumps(result.messages))
    assert after < before * 0.6


def test_dedup_preserves_tool_use_ids() -> None:
    """Dropping tool_use_id makes the provider reject the turn outright."""
    from cutctx.dedup import SessionDeduplicator

    messages = _tool_result_turns(_rows())

    result = SessionDeduplicator().process(messages)

    ids = [
        block["tool_use_id"]
        for message in result.messages
        for block in message["content"]
        if block.get("type") == "tool_result"
    ]
    assert ids == ["t0", "t1", "t2"]


def test_dedup_leaves_distinct_content_alone() -> None:
    from cutctx.dedup import SessionDeduplicator

    messages = [
        {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "a", "content": _rows()}],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "b",
                    "content": json.dumps([{"id": i + 10_000} for i in range(200)]),
                }
            ],
        },
    ]

    assert SessionDeduplicator().process(messages).dedup_count == 0


def test_dedup_pointer_resolves_back_to_the_original() -> None:
    """A pointer nothing can resolve is data loss, not compression."""
    import re

    from cutctx.cache.compression_store import get_compression_store
    from cutctx.dedup import SessionDeduplicator

    store = get_compression_store()
    block = _rows()

    result = SessionDeduplicator(ccr_store=store).process(_tool_result_turns(block))

    pointers = [
        b["content"]
        for m in result.messages
        for b in m["content"]
        if isinstance(b, dict) and b.get("content") != block
    ]
    assert pointers, "expected at least one dedup pointer"
    digest = re.search(r"([0-9a-fA-F]{8,})", pointers[0])
    assert digest is not None
    entry = store.retrieve(digest.group(1))
    assert entry is not None, "dedup pointer does not resolve — content would be lost"
    assert entry.original_content == block


def test_pipeline_gives_the_deduplicator_a_store() -> None:
    """Without this wiring every pointer above becomes unresolvable."""
    from cutctx.proxy.intelligence_pipeline import IntelligencePipeline

    assert IntelligencePipeline()._get_deduplicator()._ccr_store is not None


# ---------------------------------------------------------------------------
# context_budget
# ---------------------------------------------------------------------------


def test_context_budget_counts_tool_result_payloads() -> None:
    """Tool output counted as zero, so the ceiling never engaged."""
    from cutctx.context_budget import ContextBudgetController

    messages = _tool_result_turns(_rows(400), turns=6)

    counted = ContextBudgetController(max_tokens=2000)._count_tokens(messages)

    assert counted > 10_000, f"tool_result payloads are not being counted (got {counted})"


def test_context_budget_trims_when_over_ceiling() -> None:
    from cutctx.context_budget import ContextBudgetController

    messages = _tool_result_turns(_rows(400), turns=6)
    before = token_len(json.dumps(messages))

    trimmed = ContextBudgetController(max_tokens=2000).apply(messages)

    assert token_len(json.dumps(trimmed)) < before


def test_context_budget_leaves_small_conversations_untouched() -> None:
    from cutctx.context_budget import ContextBudgetController

    messages = [{"role": "user", "content": [{"type": "text", "text": "hi"}]}]

    assert ContextBudgetController(max_tokens=100_000).apply(messages) == messages


# ---------------------------------------------------------------------------
# dedup threshold: it runs post-compression, so the floor has to account for
# blocks the compressors have already shrunk.
# ---------------------------------------------------------------------------


def test_dedup_still_collapses_blocks_the_compressors_shrank() -> None:
    """The floor is applied after compression, not to raw tool output.

    At the old 200-token floor, four identical 120-row tool results compressed
    to just under the threshold and then deduped to nothing — 85.7% where
    94.0% was available. This is the realistic shape: medium tool output that
    repeats across turns.
    """
    from cutctx.dedup import SessionDeduplicator
    from cutctx.transforms.content_router import ContentRouter

    block = json.dumps([{"id": i, "status": "active", "note": "N"} for i in range(120)])
    compressed = ContentRouter().compress(block).compressed
    messages = [
        {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": f"t{i}", "content": compressed}],
        }
        for i in range(4)
    ]

    result = SessionDeduplicator().process(messages)

    assert result.dedup_count == 3, (
        "compressed duplicates fell under the dedup floor and were not collapsed"
    )


def test_dedup_floor_still_ignores_small_content() -> None:
    """Lowering the floor must not start collapsing trivia."""
    from cutctx.dedup import SessionDeduplicator

    tiny = "ok"
    messages = [
        {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": f"t{i}", "content": tiny}],
        }
        for i in range(4)
    ]

    assert SessionDeduplicator().process(messages).dedup_count == 0


# ---------------------------------------------------------------------------
# code_aware: off by default, and these pin the two reasons why.
# ---------------------------------------------------------------------------


def test_code_aware_elides_implementation_not_just_formatting() -> None:
    """It drops statements from function bodies while keeping signatures.

    That shape is the hazard: an agent reading a file in order to edit it sees
    intact names and signatures with roughly a quarter of the logic missing,
    and nothing marks the gap. This test documents the behaviour so anyone
    flipping the default has to confront it deliberately.
    """
    import ast

    source = Path("cutctx/utils.py").read_text()
    out = ContentRouter(ContentRouterConfig(enable_code_aware=True)).compress(source)
    if out.compressed == source:
        pytest.skip("code-aware declined this file (invalid-syntax guard)")

    def body_statements(code: str) -> int:
        tree = ast.parse(code)
        return sum(
            len(
                [
                    s
                    for s in node.body
                    if not (
                        isinstance(s, ast.Expr)
                        and isinstance(s.value, ast.Constant)
                        and isinstance(s.value.value, str)
                    )
                ]
            )
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        )

    assert body_statements(out.compressed) < body_statements(source), (
        "expected code-aware to elide implementation; if this now round-trips "
        "losslessly the default is worth revisiting"
    )


def test_code_aware_output_is_always_syntactically_valid() -> None:
    """The guard must never let broken source reach the model.

    Code-aware emits invalid Python on some real files. That is a defect, but
    the guard turning it into a passthrough is the behaviour we depend on.
    """
    import ast

    router = ContentRouter(ContentRouterConfig(enable_code_aware=True))
    for path in ("cutctx/utils.py", "cutctx/dedup.py", "cutctx/context_budget.py"):
        compressed = router.compress(Path(path).read_text()).compressed
        ast.parse(compressed)  # raises SyntaxError if the guard ever leaks


# ---------------------------------------------------------------------------
# dedup across requests: the session hash index used to swallow the last copy
# ---------------------------------------------------------------------------


def _growing_convo(block: str, turns: int) -> list[dict]:
    return [
        {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": f"t{i}", "content": block}],
        }
        for i in range(turns)
    ]


def test_a_full_copy_survives_across_requests() -> None:
    """`_hash_index` persists for the session, so on the second request the
    first occurrence was already "seen" and became a pointer too. From that
    point the conversation carried no copy of the content at all and the model
    could only reach it through retrieval.
    """
    from cutctx.dedup import SessionDeduplicator

    block = json.dumps([{"id": i, "note": "SENTINEL"} for i in range(300)])
    dedup = SessionDeduplicator()

    for turns in range(1, 5):
        rendered = [
            m["content"][0]["content"] for m in dedup.process(_growing_convo(block, turns)).messages
        ]
        assert sum(1 for r in rendered if "SENTINEL" in r) == 1, (
            f"request {turns}: expected exactly one verbatim copy, got {rendered}"
        )


def test_dedup_keeps_the_cacheable_prefix_stable() -> None:
    """Each turn must render identically on every request.

    A turn that renders one way and then another moves the cacheable prefix,
    and the provider prompt cache is discarded from that point. Cache reads
    are billed at roughly a tenth of input, so churning the prefix to save raw
    tokens is a net loss.
    """
    from cutctx.dedup import SessionDeduplicator

    block = json.dumps([{"id": i, "note": "N"} for i in range(300)])
    dedup = SessionDeduplicator()
    previous: list[str] = []

    for turns in range(1, 6):
        rendered = [
            m["content"][0]["content"] for m in dedup.process(_growing_convo(block, turns)).messages
        ]
        assert rendered[: len(previous)] == previous, (
            f"request {turns} rewrote an earlier turn; prompt-cache prefix lost"
        )
        previous = rendered
