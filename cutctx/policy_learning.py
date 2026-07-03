"""Local learned compression policy table for WS18 Phase A."""

from __future__ import annotations

import json
import os
import sqlite3
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cutctx.hooks import CompressContext, CompressionHooks

DEFAULT_DB_PATH = Path("~/.cutctx/policies.db")
_DB_ENV = "CUTCTX_POLICIES_DB"
_MIN_POLICY_BIAS = 0.5
_MAX_POLICY_BIAS = 1.5
_AGGRESSIVENESS_BIAS = {
    "aggressive": 0.75,
    "balanced": 1.0,
    "conservative": 1.25,
}


@dataclass(frozen=True)
class PolicySelector:
    tool_name: str
    content_type: str
    repo: str

    @classmethod
    def from_event(cls, event: dict[str, object]) -> PolicySelector:
        return cls(
            tool_name=str(event.get("tool_name") or "unknown"),
            content_type=str(event.get("content_type") or "unknown"),
            repo=str(event.get("repo") or "default"),
        )


@dataclass(frozen=True)
class LearnedPolicy:
    selector: PolicySelector
    aggressiveness: str
    algorithm_hint: str
    protected_patterns: tuple[str, ...]
    samples: int
    avg_ratio: float
    retrieval_rate: float
    guard_failure_rate: float
    updated_at: float

    def to_dict(self) -> dict[str, object]:
        return {
            "selector": {
                "tool_name": self.selector.tool_name,
                "content_type": self.selector.content_type,
                "repo": self.selector.repo,
            },
            "aggressiveness": self.aggressiveness,
            "algorithm_hint": self.algorithm_hint,
            "protected_patterns": list(self.protected_patterns),
            "samples": self.samples,
            "avg_ratio": self.avg_ratio,
            "retrieval_rate": self.retrieval_rate,
            "guard_failure_rate": self.guard_failure_rate,
            "updated_at": self.updated_at,
        }


def default_policy_db_path() -> Path:
    return Path(os.environ.get(_DB_ENV, str(DEFAULT_DB_PATH))).expanduser()


def init_db(path: Path | None = None) -> Path:
    db_path = path or default_policy_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS learned_policies (
                tool_name TEXT NOT NULL,
                content_type TEXT NOT NULL,
                repo TEXT NOT NULL,
                aggressiveness TEXT NOT NULL,
                algorithm_hint TEXT NOT NULL,
                protected_patterns_json TEXT NOT NULL,
                samples INTEGER NOT NULL,
                avg_ratio REAL NOT NULL,
                retrieval_rate REAL NOT NULL,
                guard_failure_rate REAL NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY (tool_name, content_type, repo)
            )
            """
        )
    return db_path


def _ratio(event: dict[str, object]) -> float:
    original = max(float(event.get("original_tokens") or 0), 1.0)
    compressed = max(float(event.get("compressed_tokens") or 0), 0.0)
    return max(0.0, min(1.0, compressed / original))


def _algorithm_hint(content_type: str) -> str:
    normalized = content_type.lower()
    if "json" in normalized or "tool" in normalized:
        return "smart_crusher"
    if "code" in normalized or "diff" in normalized:
        return "code_aware"
    if "log" in normalized:
        return "drain3"
    return "universal"


def _protected_patterns(events: list[dict[str, object]]) -> tuple[str, ...]:
    patterns: set[str] = set()
    for event in events:
        value = event.get("protected_patterns")
        if isinstance(value, str):
            patterns.add(value)
        elif isinstance(value, list):
            patterns.update(str(item) for item in value if item)
    return tuple(sorted(patterns))


def _policy_for(selector: PolicySelector, events: list[dict[str, object]]) -> LearnedPolicy:
    samples = len(events)
    avg_ratio = sum(_ratio(event) for event in events) / max(samples, 1)
    retrieval_rate = sum(1 for event in events if event.get("retrieved")) / max(samples, 1)
    guard_failure_rate = sum(1 for event in events if event.get("guard_failed")) / max(samples, 1)

    if guard_failure_rate > 0 or retrieval_rate >= 0.05:
        aggressiveness = "conservative"
    elif avg_ratio <= 0.35 and samples >= 20:
        aggressiveness = "aggressive"
    else:
        aggressiveness = "balanced"

    return LearnedPolicy(
        selector=selector,
        aggressiveness=aggressiveness,
        algorithm_hint=_algorithm_hint(selector.content_type),
        protected_patterns=_protected_patterns(events),
        samples=samples,
        avg_ratio=avg_ratio,
        retrieval_rate=retrieval_rate,
        guard_failure_rate=guard_failure_rate,
        updated_at=time.time(),
    )


def train_from_events(
    events: Iterable[dict[str, object]], path: Path | None = None
) -> list[LearnedPolicy]:
    db_path = init_db(path)
    grouped: dict[PolicySelector, list[dict[str, object]]] = {}
    for event in events:
        grouped.setdefault(PolicySelector.from_event(event), []).append(event)

    policies = [_policy_for(selector, rows) for selector, rows in sorted(grouped.items(), key=str)]
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO learned_policies (
                tool_name, content_type, repo, aggressiveness, algorithm_hint,
                protected_patterns_json, samples, avg_ratio, retrieval_rate,
                guard_failure_rate, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(tool_name, content_type, repo) DO UPDATE SET
                aggressiveness=excluded.aggressiveness,
                algorithm_hint=excluded.algorithm_hint,
                protected_patterns_json=excluded.protected_patterns_json,
                samples=excluded.samples,
                avg_ratio=excluded.avg_ratio,
                retrieval_rate=excluded.retrieval_rate,
                guard_failure_rate=excluded.guard_failure_rate,
                updated_at=excluded.updated_at
            """,
            [
                (
                    policy.selector.tool_name,
                    policy.selector.content_type,
                    policy.selector.repo,
                    policy.aggressiveness,
                    policy.algorithm_hint,
                    json.dumps(list(policy.protected_patterns), sort_keys=True),
                    policy.samples,
                    policy.avg_ratio,
                    policy.retrieval_rate,
                    policy.guard_failure_rate,
                    policy.updated_at,
                )
                for policy in policies
            ],
        )
    return policies


def load_policies(path: Path | None = None) -> list[LearnedPolicy]:
    db_path = init_db(path)
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT tool_name, content_type, repo, aggressiveness, algorithm_hint,
                   protected_patterns_json, samples, avg_ratio, retrieval_rate,
                   guard_failure_rate, updated_at
            FROM learned_policies
            ORDER BY repo, tool_name, content_type
            """
        ).fetchall()
    return [
        LearnedPolicy(
            selector=PolicySelector(tool_name=row[0], content_type=row[1], repo=row[2]),
            aggressiveness=row[3],
            algorithm_hint=row[4],
            protected_patterns=tuple(json.loads(row[5])),
            samples=row[6],
            avg_ratio=row[7],
            retrieval_rate=row[8],
            guard_failure_rate=row[9],
            updated_at=row[10],
        )
        for row in rows
    ]


def _message_tool_name(message: dict[str, Any]) -> str:
    for key in ("tool_name", "name"):
        value = message.get(key)
        if value:
            return str(value)
    return "unknown"


def _message_content_type(message: dict[str, Any]) -> str:
    explicit = message.get("content_type")
    if explicit:
        return str(explicit)
    role = str(message.get("role") or "")
    if role == "tool":
        return "tool_output"
    content = message.get("content")
    if isinstance(content, str):
        stripped = content.lstrip()
        if stripped.startswith("{") or stripped.startswith("["):
            return "json"
        if "\n+" in content or "\n-" in content:
            return "diff"
    return "unknown"


def _clamp_bias(value: float) -> float:
    return max(_MIN_POLICY_BIAS, min(_MAX_POLICY_BIAS, value))


def bias_for_policy(policy: LearnedPolicy) -> float:
    return _clamp_bias(_AGGRESSIVENESS_BIAS.get(policy.aggressiveness, 1.0))


def evict_unsafe_policies(
    path: Path | None = None,
    *,
    max_retrieval_rate: float = 0.5,
    max_guard_failure_rate: float = 0.0,
) -> int:
    """Remove learned rows that are no longer safe to apply automatically."""
    db_path = init_db(path)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            """
            DELETE FROM learned_policies
            WHERE retrieval_rate > ? OR guard_failure_rate > ?
            """,
            (max_retrieval_rate, max_guard_failure_rate),
        )
    return int(cursor.rowcount)


class LearnedPolicyHooks(CompressionHooks):
    """Apply learned policy rows through the existing compression bias hook."""

    def __init__(
        self,
        path: Path | None = None,
        *,
        repo: str | None = None,
        policies: list[LearnedPolicy] | None = None,
    ) -> None:
        self.path = path
        self.repo = repo or Path.cwd().name
        self._policies = policies

    def _load(self) -> list[LearnedPolicy]:
        if self._policies is not None:
            return self._policies
        self._policies = load_policies(self.path)
        return self._policies

    def compute_biases(
        self, messages: list[dict[str, Any]], ctx: CompressContext
    ) -> dict[int, float]:
        policies = self._load()
        if not policies:
            return {}

        by_selector = {
            (
                policy.selector.tool_name,
                policy.selector.content_type,
                policy.selector.repo,
            ): policy
            for policy in policies
        }
        biases: dict[int, float] = {}
        ctx_tools = set(ctx.tool_calls or [])
        for index, message in enumerate(messages):
            tool_name = _message_tool_name(message)
            content_type = _message_content_type(message)
            if ctx_tools and tool_name == "unknown":
                tool_name = next(iter(sorted(ctx_tools)))
            policy = by_selector.get((tool_name, content_type, self.repo))
            if policy is not None:
                biases[index] = bias_for_policy(policy)
        return biases


def reset_policies(path: Path | None = None) -> int:
    db_path = init_db(path)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute("DELETE FROM learned_policies")
    return int(cursor.rowcount)


def read_jsonl(path: Path) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_no}: expected JSON object")
        events.append(value)
    return events
