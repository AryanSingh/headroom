# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs
"""WS19 Compression autopilot (closed feedback loop).

Per artifacts/savings-moat-expansion-specs.md WS19.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


DEFAULT_MIN_LEVEL = 1
DEFAULT_MAX_LEVEL = 5
DEFAULT_HYSTERESIS_WINDOW = 10


@dataclass
class AutopilotConfig:
    enabled: bool = False
    min_level: int = DEFAULT_MIN_LEVEL
    max_level: int = DEFAULT_MAX_LEVEL
    hysteresis_window: int = DEFAULT_HYSTERESIS_WINDOW


@dataclass
class QualitySignal:
    task_type: str
    outcome: str
    timestamp_seconds: float = 0.0


@dataclass
class LevelAdjustment:
    task_type: str
    old_level: int
    new_level: int
    signal_kind: str
    timestamp_seconds: float = 0.0


@dataclass
class AutopilotStats:
    signal_count: int = 0
    clean_count: int = 0
    adjustment_count: int = 0


class AutopilotController:
    """Closed-feedback-loop controller for compression aggressiveness.

    Per-task-type state. Starts at max_level. A bad signal (retrieval
    or guard_failure) drops the level by 1. A clean signal increments
    the clean counter; when the counter reaches hysteresis_window, the
    level is raised by 1 and the counter resets. The clean counter
    also resets on any bad signal.

    The controller is a PURE function of the signal window: same
    input sequence -> same level trajectory. No ML. No randomness.
    """

    def __init__(self, config: AutopilotConfig | None = None) -> None:
        self.config = config or AutopilotConfig()
        self._levels: dict[str, int] = {}
        self._clean_counters: dict[str, int] = defaultdict(int)
        self._stats: dict[str, AutopilotStats] = {}

    def current_level(self, task_type: str) -> int:
        return self._levels.get(task_type, self.config.max_level)

    def ingest(self, signal: QualitySignal) -> LevelAdjustment | None:
        if not self.config.enabled:
            return None

        task_type = signal.task_type
        self._bump_signal(task_type)

        old_level = self.current_level(task_type)
        new_level = old_level

        if signal.outcome in ("retrieval", "guard_failure"):
            new_level = max(self.config.min_level, old_level - 1)
            self._clean_counters[task_type] = 0
        elif signal.outcome == "clean":
            self._bump_clean(task_type)
            # Increment the per-task-type clean counter
            self._clean_counters[task_type] = self._clean_counters[task_type] + 1
            if self._clean_counters[task_type] >= self.config.hysteresis_window:
                new_level = min(self.config.max_level, old_level + 1)
                self._clean_counters[task_type] = 0
        else:
            return None

        if new_level != old_level:
            self._levels[task_type] = new_level
            self._bump_adjustment(task_type)
            return LevelAdjustment(
                task_type=task_type,
                old_level=old_level,
                new_level=new_level,
                signal_kind=signal.outcome,
                timestamp_seconds=signal.timestamp_seconds,
            )
        return None

    def stats_for(self, task_type: str) -> AutopilotStats:
        return self._stats.setdefault(task_type, AutopilotStats())

    def _bump_signal(self, task_type: str) -> None:
        self._stats.setdefault(task_type, AutopilotStats()).signal_count += 1

    def _bump_clean(self, task_type: str) -> None:
        self._stats.setdefault(task_type, AutopilotStats()).clean_count += 1

    def _bump_adjustment(self, task_type: str) -> None:
        self._stats.setdefault(task_type, AutopilotStats()).adjustment_count += 1


__all__ = [
    "DEFAULT_HYSTERESIS_WINDOW",
    "DEFAULT_MAX_LEVEL",
    "DEFAULT_MIN_LEVEL",
    "AutopilotConfig",
    "AutopilotController",
    "AutopilotStats",
    "LevelAdjustment",
    "QualitySignal",
]
