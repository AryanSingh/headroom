"""Tests for episode storage and label building."""

import time
from pathlib import Path

import pytest

from headroom.telemetry.episodes import CompressionEpisode, EpisodeStore, RetrievalLabel
from headroom.telemetry.outcome import OutcomeEvent, OutcomeSignal
from headroom.training.label_builder import LabelBuilder
from headroom.training.schema import ExampleLabel


@pytest.fixture
def temp_db(tmp_path: Path):
    db_path = tmp_path / "test_episodes.db"
    store = EpisodeStore(db_path=str(db_path))
    return store


def test_store_and_query_compression(temp_db):
    ep = CompressionEpisode(
        episode_id="ep_123",
        tenant_id="tenant_1",
        original_size=1000,
        compressed_size=100,
        start_line=0,
        end_line=50,
        timestamp_ts=time.time(),
    )
    temp_db.record_compression(ep)

    eps = temp_db.get_episodes(limit=10)
    assert len(eps) == 1
    assert eps[0].episode_id == "ep_123"


def test_label_builder_should_keep():
    builder = LabelBuilder()

    ep = CompressionEpisode(
        episode_id="ep_123",
        tenant_id="tenant_1",
        original_size=1000,
        compressed_size=100,
        start_line=0,
        end_line=50,
        timestamp_ts=time.time(),
    )

    retrieval = RetrievalLabel(
        episode_id="ep_123",
        tenant_id="tenant_1",
        retrieved_span_start=0,
        retrieved_span_end=50,
        timestamp_ts=time.time(),
    )

    outcome = OutcomeEvent(
        session_id="sess_1",
        tenant_id="tenant_1",
        signal=OutcomeSignal.SUCCESS,
        timestamp_ts=time.time(),
        context={},
    )

    examples = list(builder.build_examples([ep], [retrieval], [outcome]))
    assert len(examples) == 1
    assert examples[0].label == ExampleLabel.SHOULD_KEEP


def test_label_builder_safe_to_drop():
    builder = LabelBuilder()

    ep = CompressionEpisode(
        episode_id="ep_123",
        tenant_id="tenant_1",
        original_size=1000,
        compressed_size=100,
        start_line=0,
        end_line=50,
        timestamp_ts=time.time(),
    )

    outcome = OutcomeEvent(
        session_id="sess_1",
        tenant_id="tenant_1",
        signal=OutcomeSignal.SUCCESS,
        timestamp_ts=time.time(),
        context={},
    )

    examples = list(builder.build_examples([ep], [], [outcome]))
    assert len(examples) == 1
    assert examples[0].label == ExampleLabel.SAFE_TO_DROP
