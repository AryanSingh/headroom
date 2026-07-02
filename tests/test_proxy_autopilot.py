# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs
"""TDD tests for the WS19 compression autopilot (closed feedback loop).

Per artifacts/savings-moat-expansion-specs.md WS19.
TDD: written first.
"""

from __future__ import annotations

import pytest

from cutctx.proxy.autopilot import (
    DEFAULT_HYSTERESIS_WINDOW,
    DEFAULT_MAX_LEVEL,
    DEFAULT_MIN_LEVEL,
    AutopilotConfig,
    AutopilotController,
    QualitySignal,
    LevelAdjustment,
)


def test_default_config_is_all_off() -> None:
    cfg = AutopilotConfig()
    assert cfg.enabled is False
    assert cfg.min_level == DEFAULT_MIN_LEVEL
    assert cfg.max_level == DEFAULT_MAX_LEVEL
    assert cfg.hysteresis_window == DEFAULT_HYSTERESIS_WINDOW


def test_flag_off_does_not_grow_state() -> None:
    cfg = AutopilotConfig()
    controller = AutopilotController(cfg)
    for i in range(50):
        signal = QualitySignal(
            task_type="general", outcome="retrieval", timestamp_seconds=float(i)
        )
        adjustment = controller.ingest(signal)
        assert adjustment is None
    s = controller.stats_for("general")
    assert s.clean_count == 0
    assert s.signal_count == 0


def test_quality_signal_outcomes() -> None:
    s1 = QualitySignal(task_type="code_edit", outcome="clean", timestamp_seconds=0.0)
    assert s1.outcome == "clean"
    s2 = QualitySignal(task_type="code_edit", outcome="retrieval", timestamp_seconds=1.0)
    assert s2.outcome == "retrieval"
    s3 = QualitySignal(task_type="code_edit", outcome="guard_failure", timestamp_seconds=2.0)
    assert s3.outcome == "guard_failure"


def test_controller_starts_at_max_level() -> None:
    cfg = AutopilotConfig(enabled=True)
    controller = AutopilotController(cfg)
    assert controller.current_level("code_edit") == cfg.max_level


def test_retrieval_lowers_level() -> None:
    cfg = AutopilotConfig(enabled=True, min_level=1, max_level=5)
    controller = AutopilotController(cfg)
    start = controller.current_level("code_edit")
    signal = QualitySignal(task_type="code_edit", outcome="retrieval", timestamp_seconds=1.0)
    adjustment = controller.ingest(signal)
    assert adjustment is not None
    assert adjustment.new_level == start - 1


def test_guard_failure_lowers_level() -> None:
    cfg = AutopilotConfig(enabled=True, min_level=1, max_level=5)
    controller = AutopilotController(cfg)
    start = controller.current_level("code_edit")
    signal = QualitySignal(task_type="code_edit", outcome="guard_failure", timestamp_seconds=1.0)
    adjustment = controller.ingest(signal)
    assert adjustment is not None
    assert adjustment.new_level == start - 1


def test_clean_signal_does_not_lower_level() -> None:
    cfg = AutopilotConfig(enabled=True, min_level=1, max_level=5)
    controller = AutopilotController(cfg)
    start = controller.current_level("code_edit")
    signal = QualitySignal(task_type="code_edit", outcome="clean", timestamp_seconds=1.0)
    adjustment = controller.ingest(signal)
    assert adjustment is None
    assert controller.current_level("code_edit") == start


def test_level_clamps_to_min_level() -> None:
    cfg = AutopilotConfig(enabled=True, min_level=2, max_level=5)
    controller = AutopilotController(cfg)
    for i in range(20):
        controller.ingest(
            QualitySignal(task_type="code_edit", outcome="retrieval", timestamp_seconds=float(i))
        )
    assert controller.current_level("code_edit") == 2


def test_level_clamps_to_max_level() -> None:
    cfg = AutopilotConfig(enabled=True, min_level=1, max_level=5)
    controller = AutopilotController(cfg)
    for i in range(20):
        controller.ingest(
            QualitySignal(task_type="code_edit", outcome="clean", timestamp_seconds=float(i))
        )
    assert controller.current_level("code_edit") <= 5


def test_max_level_default_is_5() -> None:
    assert DEFAULT_MAX_LEVEL == 5


def test_min_level_default_is_1() -> None:
    assert DEFAULT_MIN_LEVEL == 1


def test_hysteresis_default_window_is_10() -> None:
    assert DEFAULT_HYSTERESIS_WINDOW == 10


def test_hysteresis_does_not_raise_until_k_clean_signals() -> None:
    cfg = AutopilotConfig(
        enabled=True, min_level=1, max_level=5, hysteresis_window=10
    )
    controller = AutopilotController(cfg)
    controller.ingest(
        QualitySignal(task_type="code_edit", outcome="retrieval", timestamp_seconds=1.0)
    )
    level_after_drop = controller.current_level("code_edit")
    for i in range(9):
        controller.ingest(
            QualitySignal(task_type="code_edit", outcome="clean", timestamp_seconds=float(10 + i))
        )
    assert controller.current_level("code_edit") == level_after_drop
    controller.ingest(
        QualitySignal(task_type="code_edit", outcome="clean", timestamp_seconds=20.0)
    )
    assert controller.current_level("code_edit") == level_after_drop + 1


def test_hysteresis_resets_on_bad_signal() -> None:
    cfg = AutopilotConfig(
        enabled=True, min_level=1, max_level=5, hysteresis_window=10
    )
    controller = AutopilotController(cfg)
    controller.ingest(
        QualitySignal(task_type="code_edit", outcome="retrieval", timestamp_seconds=1.0)
    )
    for i in range(5):
        controller.ingest(
            QualitySignal(task_type="code_edit", outcome="clean", timestamp_seconds=float(10 + i))
        )
    controller.ingest(
        QualitySignal(task_type="code_edit", outcome="retrieval", timestamp_seconds=20.0)
    )
    for i in range(9):
        controller.ingest(
            QualitySignal(task_type="code_edit", outcome="clean", timestamp_seconds=float(30 + i))
        )
    # After 1 retrieval dropped 5->4, 5 cleans then another retrieval
    # dropped 4->3, 9 cleans (counter at 9, below hysteresis of 10) so
    # the level stays at 3.
    assert controller.current_level("code_edit") == 3


def test_per_task_type_isolation() -> None:
    cfg = AutopilotConfig(enabled=True, min_level=1, max_level=5)
    controller = AutopilotController(cfg)
    controller.ingest(
        QualitySignal(task_type="code_edit", outcome="retrieval", timestamp_seconds=1.0)
    )
    code_level = controller.current_level("code_edit")
    search_level = controller.current_level("search")
    assert code_level < search_level
    assert search_level == 5


def test_controller_is_deterministic() -> None:
    cfg = AutopilotConfig(enabled=True, min_level=1, max_level=5, hysteresis_window=3)
    c1 = AutopilotController(cfg)
    c2 = AutopilotController(cfg)
    signals = [
        QualitySignal(task_type="code_edit", outcome="retrieval", timestamp_seconds=1.0),
        QualitySignal(task_type="code_edit", outcome="clean", timestamp_seconds=2.0),
        QualitySignal(task_type="code_edit", outcome="clean", timestamp_seconds=3.0),
        QualitySignal(task_type="code_edit", outcome="clean", timestamp_seconds=4.0),
        QualitySignal(task_type="code_edit", outcome="retrieval", timestamp_seconds=5.0),
    ]
    for s in signals:
        c1.ingest(s)
        c2.ingest(s)
    assert c1.current_level("code_edit") == c2.current_level("code_edit")


def test_bdd_scenario_autopilot_drops_level_on_retrieval_storm() -> None:
    cfg = AutopilotConfig(enabled=True, min_level=1, max_level=5)
    controller = AutopilotController(cfg)
    for i in range(10):
        controller.ingest(
            QualitySignal(task_type="code_edit", outcome="retrieval", timestamp_seconds=float(i))
        )
    assert controller.current_level("code_edit") == 1


def test_bdd_scenario_autopilot_recovers_on_clean_streak() -> None:
    cfg = AutopilotConfig(enabled=True, min_level=1, max_level=5, hysteresis_window=3)
    controller = AutopilotController(cfg)
    for i in range(5):
        controller.ingest(
            QualitySignal(task_type="code_edit", outcome="retrieval", timestamp_seconds=float(i))
        )
    assert controller.current_level("code_edit") == 1
    for i in range(3):
        controller.ingest(
            QualitySignal(task_type="code_edit", outcome="clean", timestamp_seconds=float(10 + i))
        )
    assert controller.current_level("code_edit") == 2


def test_bdd_scenario_autopilot_emits_audit_record_on_adjustment() -> None:
    cfg = AutopilotConfig(enabled=True, min_level=1, max_level=5)
    controller = AutopilotController(cfg)
    records: list[LevelAdjustment] = []
    for i in range(5):
        signal = QualitySignal(task_type="code_edit", outcome="retrieval", timestamp_seconds=float(i))
        adj = controller.ingest(signal)
        if adj is not None:
            records.append(adj)
    assert len(records) >= 4
    for r in records:
        assert r.task_type == "code_edit"
        assert r.signal_kind == "retrieval"
        assert 0 < r.old_level <= cfg.max_level
        assert 0 < r.new_level <= cfg.max_level


def test_stats_track_signals_per_task_type() -> None:
    cfg = AutopilotConfig(enabled=True)
    controller = AutopilotController(cfg)
    for i in range(3):
        controller.ingest(
            QualitySignal(task_type="code_edit", outcome="retrieval", timestamp_seconds=float(i))
        )
    s = controller.stats_for("code_edit")
    assert s.signal_count == 3
    assert s.adjustment_count >= 2


def test_stats_track_clean_count_separately() -> None:
    cfg = AutopilotConfig(enabled=True)
    controller = AutopilotController(cfg)
    for i in range(3):
        controller.ingest(
            QualitySignal(task_type="code_edit", outcome="clean", timestamp_seconds=float(i))
        )
    s = controller.stats_for("code_edit")
    assert s.clean_count == 3
    assert s.signal_count == 3
    assert s.adjustment_count == 0
