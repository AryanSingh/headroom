from datetime import UTC, datetime

import pytest

pytest.importorskip("sentence_transformers", reason="requires the optional memory extra")

from cutctx.memory.config import MemoryConfig
from cutctx.memory.core import HierarchicalMemory
from cutctx.memory.models import DecisionTrace
from cutctx.memory.ports import MemoryFilter
from cutctx.memory.subagent import SubAgentBridge


@pytest.mark.asyncio
async def test_decision_trace_creation():
    trace = DecisionTrace(
        user_id="alice",
        situation="System is slow",
        rationale="Needs caching",
        action="Added Redis",
        outcome="Latency improved by 50%"
    )
    
    assert trace.user_id == "alice"
    assert trace.situation == "System is slow"
    assert trace.rationale == "Needs caching"
    assert trace.action == "Added Redis"
    assert trace.outcome == "Latency improved by 50%"
    assert trace.metadata["type"] == "decision_trace"
    
    # Assert content was auto-generated
    assert "Situation: System is slow" in trace.content
    assert "Action: Added Redis" in trace.content


@pytest.mark.asyncio
async def test_decision_trace_roundtrip():
    trace = DecisionTrace(
        user_id="alice",
        situation="System is slow",
        rationale="Needs caching",
        action="Added Redis",
        outcome="Latency improved by 50%"
    )
    d = trace.to_dict()
    restored = DecisionTrace.from_dict(d)
    
    assert restored.situation == "System is slow"
    assert restored.rationale == "Needs caching"
    assert restored.action == "Added Redis"
    assert restored.outcome == "Latency improved by 50%"
    assert restored.user_id == "alice"


@pytest.mark.asyncio
async def test_subagent_bridge():
    import uuid
    test_session = f"test_session_{uuid.uuid4().hex[:8]}"
    
    # Use create factory method to initialize the in-memory backend
    memory = await HierarchicalMemory.create()
    
    # Add some memory to the session
    await memory.add(
        content="Important architectural decision: use hexagonal architecture.",
        user_id="test_user",
        session_id=test_session,
        importance=0.9
    )
    
    # Create bridge
    bridge = SubAgentBridge(
        memory=memory,
        parent_session_id=test_session,
        user_id="test_user"
    )
    
    # Provision subagent
    payload = await bridge.provision_subagent(task="Refactor login module")
    
    assert payload["task"] == "Refactor login module"
    assert "hexagonal architecture" in payload["context_summary"]
    assert payload["ccr_scope"]["session_id"] == test_session
    assert payload["ccr_scope"]["user_id"] == "test_user"
    
    # Merge result
    await bridge.merge_result(
        subagent_id="refactor_agent_1",
        distilled_result="Extracted auth logic into domain layer."
    )
    
    # Verify result in memory
    results = await memory.query(MemoryFilter(
        user_id="test_user",
        session_id=test_session
    ))
    
    merged_memories = [m for m in results if m.metadata.get("source") == "subagent_distillation"]
    assert len(merged_memories) == 1
    assert "Extracted auth logic" in merged_memories[0].content
    assert merged_memories[0].metadata["subagent_id"] == "refactor_agent_1"
