import time

from cutctx.memory.models import Memory
from cutctx.memory.value import ValueModel


def test_value_model_injection():
    memory = Memory(content="Test memory")
    assert memory.citations == []

    # First injection
    ValueModel.on_injection(memory, "turn_123")
    assert "turn_123" in memory.citations

    # Duplicate injection does not append again
    ValueModel.on_injection(memory, "turn_123")
    assert memory.citations.count("turn_123") == 1


def test_value_model_outcome_success():
    memory = Memory(content="Test memory", value_score=0.5)

    ValueModel.on_outcome(memory, "success", "outcome_1")

    # EWMA calculation: V_new = 0.8 * 0.5 + 0.2 * 1.0 = 0.4 + 0.2 = 0.6
    import math

    assert math.isclose(memory.value_score, 0.6)
    assert "outcome_1" in memory.outcome_links

    # Duplicate outcome ID does not apply twice
    ValueModel.on_outcome(memory, "success", "outcome_1")
    assert math.isclose(memory.value_score, 0.6)


def test_value_model_outcome_fail():
    memory = Memory(content="Test memory", value_score=0.5)

    ValueModel.on_outcome(memory, "fail", "outcome_2")

    # EWMA calculation: V_new = 0.8 * 0.5 + 0.2 * (-0.5) = 0.4 - 0.1 = 0.3
    import math

    assert math.isclose(memory.value_score, 0.3)


def test_value_model_decay():
    memory = Memory(content="Test memory", value_score=0.5)

    # Set last update to 60 days ago
    sixty_days_sec = 60 * 60 * 24 * 60
    current_time = time.time()
    memory.last_value_update = current_time - sixty_days_sec

    # Should decay
    is_archived = ValueModel.decay(memory, current_time)

    # Decay factor: 0.05 * (60 / 30) = 0.1
    # New score = 0.5 - 0.1 = 0.4
    assert memory.value_score == 0.4
    assert not is_archived

    # If it decays below 0.1, it should be archived
    memory.value_score = 0.15
    memory.last_value_update = current_time - sixty_days_sec
    is_archived = ValueModel.decay(memory, current_time)

    # New score = 0.15 - 0.1 = 0.05
    # Value floor is 0.1
    assert memory.value_score < 0.1
    assert is_archived
