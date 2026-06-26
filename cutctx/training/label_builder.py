"""Label builder for the data flywheel.

Joins CompressionEpisodes, RetrievalLabels, and OutcomeEvents to infer
labels for training examples.

Rules:
1. If a compressed span was retrieved (RetrievalLabel exists) -> SHOULD_KEEP.
2. If a compressed span was never retrieved, AND the session outcome was SUCCESS -> SAFE_TO_DROP.
3. If outcome was FAILURE or UNKNOWN -> ignore (we can't safely say the drop was harmless).
"""

import logging
from collections.abc import Iterator

from cutctx.telemetry.episodes import CompressionEpisode, RetrievalLabel
from cutctx.telemetry.outcome import OutcomeEvent, OutcomeSignal
from cutctx.training.schema import ExampleLabel, TrainingExample

logger = logging.getLogger(__name__)


class LabelBuilder:
    """Builds training examples by joining telemetry events."""

    def build_examples(
        self,
        episodes: list[CompressionEpisode],
        retrievals: list[RetrievalLabel],
        outcomes: list[OutcomeEvent],
    ) -> Iterator[TrainingExample]:
        """Yield inferred training examples from the provided events."""

        # Index retrievals by episode_id
        retrieval_map = {}
        for r in retrievals:
            retrieval_map.setdefault(r.episode_id, []).append(r)

        # Index outcomes by tenant (for now, assuming 1 session per tenant for offline processing)
        # In a real system, episodes would be joined by session_id
        outcome_map = {}
        for o in outcomes:
            outcome_map[o.tenant_id] = o

        for ep in episodes:
            was_retrieved = ep.episode_id in retrieval_map
            outcome = outcome_map.get(ep.tenant_id)

            label = None
            if was_retrieved:
                # The LLM needed this data. We probably over-compressed.
                label = ExampleLabel.SHOULD_KEEP
            elif not was_retrieved and outcome and outcome.signal == OutcomeSignal.SUCCESS:
                # The LLM never needed this data, AND it succeeded.
                # It was safe to drop.
                label = ExampleLabel.SAFE_TO_DROP

            if label:
                yield TrainingExample(
                    episode_id=ep.episode_id,
                    tenant_id=ep.tenant_id,
                    label=label,
                    original_size=ep.original_size,
                    compressed_size=ep.compressed_size,
                    start_line=ep.start_line,
                    end_line=ep.end_line,
                    session_id=outcome.session_id if outcome else "unknown",
                    timestamp_ts=ep.timestamp_ts,
                )
