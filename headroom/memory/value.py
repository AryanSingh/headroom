"""Outcome-linked value scoring and decay for memories."""

import time

from headroom.memory.models import Memory


class ValueModel:
    """Manages the lifecycle and value scoring of memories."""

    # Exponential Weighted Moving Average (EWMA) factor
    ALPHA = 0.2

    # Rewards mapped from outcome labels
    REWARDS = {
        "success": 1.0,
        "unknown": 0.0,
        "fail": -0.5,
    }

    # Minimum value before a memory is considered for auto-archival
    VALUE_FLOOR = 0.1

    @classmethod
    def on_injection(cls, memory: Memory, citation_id: str) -> None:
        """Record that a memory was injected (cited) into a specific turn or episode.

        Args:
            memory: The memory being injected.
            citation_id: Unique ID of the turn or episode it was injected into.
        """
        if citation_id not in memory.citations:
            memory.citations.append(citation_id)
            # We don't update the score yet, just record the citation

    @classmethod
    def on_outcome(cls, memory: Memory, outcome_label: str, outcome_id: str) -> None:
        """Update the memory's value score based on an outcome.

        Args:
            memory: The memory to update.
            outcome_label: 'success', 'unknown', or 'fail'.
            outcome_id: Unique ID of the outcome event to prevent double counting.
        """
        if outcome_id in memory.outcome_links:
            # Prevent double counting for the same outcome event
            return

        reward = cls.REWARDS.get(outcome_label, 0.0)

        # Apply EWMA: V_new = (1 - alpha) * V_old + alpha * Reward
        memory.value_score = (1.0 - cls.ALPHA) * memory.value_score + cls.ALPHA * reward

        # Ensure it stays within bounds
        memory.value_score = max(0.0, min(1.0, memory.value_score))

        memory.outcome_links.append(outcome_id)
        memory.last_value_update = time.time()

    @classmethod
    def decay(cls, memory: Memory, current_time: float | None = None) -> bool:
        """Apply periodic time-based decay to uncited/old memories.

        Returns:
            bool: True if the memory's value dropped below the floor and should be archived.
        """
        if current_time is None:
            current_time = time.time()

        # Decay factor: e.g., drop value by 5% every 30 days
        days_since_update = (current_time - memory.last_value_update) / (60 * 60 * 24)

        if days_since_update > 30:
            # Reduce score slightly
            decay_amount = 0.05 * (days_since_update / 30)
            memory.value_score = max(0.0, memory.value_score - decay_amount)
            memory.last_value_update = current_time

        return memory.value_score < cls.VALUE_FLOOR
