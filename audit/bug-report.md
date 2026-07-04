# Bug Report: Memory Sub-Agent & Decision Trace Implementation

**Date:** 2026-07-04
**Scope:** `cutctx/memory/subagent.py`, `cutctx/memory/models.py` (DecisionTrace), `cutctx/memory/tools.py`, `cutctx/memory/system.py`, `tests/test_memory_superpowers.py`
**Auditor:** Bug Hunter

---

## Bug 1: `memory_save_decision_trace` LLM tool has no handler → silent failure

**Severity:** Critical
**Category:** Orphaned feature

### Reproduction Steps
1. Configure an LLM client with `MEMORY_TOOLS` or `MEMORY_TOOLS_OPTIMIZED` (both include `memory_save_decision_trace`)
2. The LLM calls `memory_save_decision_trace` with valid arguments
3. The request reaches `MemorySystem.process_tool_call()` in `cutctx/memory/system.py`
4. The handler dispatch dict only has 4 keys: `memory_save`, `memory_search`, `memory_update`, `memory_delete`

### Expected vs Actual Behavior
- **Expected:** The tool call is routed to a handler that creates a `DecisionTrace` memory and stores it
- **Actual:** The handler returns: `{"success": False, "error": "Unknown tool: memory_save_decision_trace", "message": "Tool 'memory_save_decision_trace' is not a valid memory tool. Available tools: ['memory_save', 'memory_search', 'memory_update', 'memory_delete']"}`

### Evidence

```python
# cutctx/memory/system.py lines 263-268
handlers = {
    "memory_save": self._handle_save,
    "memory_search": self._handle_search,
    "memory_update": self._handle_update,
    "memory_delete": self._handle_delete,
}
# No "memory_save_decision_trace" entry
```

The tool definition exists in `cutctx/memory/tools.py` lines 25-50 and is included in both `MEMORY_TOOLS` (line 307) and `MEMORY_TOOLS_OPTIMIZED` (line 455), but no code path processes it.

### Suggested Fix
Add a handler for `memory_save_decision_trace` in `process_tool_call()`. Two options:

**Option A (recommended):** Map directly to `handle_memory_save` after formatting arguments:
```python
"memory_save_decision_trace": self._handle_decision_trace_save,
```

With a new handler:
```python
async def _handle_decision_trace_save(self, args: dict) -> dict:
    # Format decision trace as content
    situation = args.get("situation", "")
    rationale = args.get("rationale", "")
    action = args.get("action", "")
    outcome = args.get("outcome", "")
    importance = args.get("importance", 0.5)
    
    content = (
        f"Decision Trace:\n"
        f"Situation: {situation}\n"
        f"Rationale: {rationale}\n"
        f"Action: {action}\n"
        f"Outcome: {outcome}"
    )
    
    return await self.handle_memory_save(
        content=content,
        importance=importance,
        metadata={"type": "decision_trace", "situation": situation, "rationale": rationale, "action": action, "outcome": outcome},
    )
```

**Option B:** Map `memory_save_decision_trace` to `handle_memory_save` with a transform layer. Simpler but loses structured fields.

---

## Bug 2: `DecisionTrace.to_dict()` silently drops `situation`, `rationale`, `action`, `outcome`

**Severity:** High
**Category:** Data loss

### Reproduction Steps
1. Create a `DecisionTrace` with all fields populated
2. Call `to_dict()` to serialize it
3. Call `DecisionTrace.from_dict()` to deserialize it back
4. The `situation`, `rationale`, `action`, and `outcome` fields are all empty strings

### Expected vs Actual Behavior
- **Expected:** Fields roundtrip faithfully through serialization/deserialization
- **Actual:** Fields are stored **only in `metadata` dict** (as a side effect in `__post_init__`), but `to_dict()` doesn't include them at the top level, and `from_dict()` doesn't read them from `metadata`

### Evidence

```
$ uv run python -c "
from cutctx.memory.models import DecisionTrace

dt = DecisionTrace(
    user_id='bob', situation='test situation',
    rationale='because reasons', action='did thing', outcome='it worked',
)
d = dt.to_dict()
print('MISSING:', [k for k in ['situation','rationale','action','outcome'] if k not in d])

dt2 = DecisionTrace.from_dict(d)
print('Roundtrip:', dt2.situation, dt2.rationale, dt2.action, dt2.outcome)
"
MISSING: ['situation', 'rationale', 'action', 'outcome']
Roundtrip: '' '' '' ''
```

The parent class `Memory.to_dict()` (lines 122-151 of `models.py`) has no awareness of subclass fields. `Memory.from_dict()` (lines 153-191) only reads fields defined in `Memory.__init__`, not `DecisionTrace.__init__`. The `DecisionTrace` subclass adds `situation`, `rationale`, `action`, `outcome` but never overrides `to_dict`/`from_dict`.

### Suggested Fix
Override `to_dict()` and `from_dict()` in `DecisionTrace`:

```python
@dataclass
class DecisionTrace(Memory):
    situation: str = ""
    rationale: str = ""
    action: str = ""
    outcome: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["situation"] = self.situation
        d["rationale"] = self.rationale
        d["action"] = self.action
        d["outcome"] = self.outcome
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DecisionTrace:
        # Extract subclass fields before delegating to Memory.from_dict
        situation = data.get("situation") or data.get("metadata", {}).get("situation", "")
        rationale = data.get("rationale") or data.get("metadata", {}).get("rationale", "")
        action = data.get("action") or data.get("metadata", {}).get("action", "")
        outcome = data.get("outcome") or data.get("metadata", {}).get("outcome", "")
        
        # Fallback to parent from_dict to avoid duplicating all field parsing
        base = Memory.from_dict(data)
        return cls(
            **{k: getattr(base, k) for k in Memory.__dataclass_fields__},
            situation=situation,
            rationale=rationale,
            action=action,
            outcome=outcome,
        )
```

---

## Bug 3: Test `test_subagent_bridge` has state persistence → fails on second run

**Severity:** Medium
**Category:** Test isolation

### Reproduction Steps
1. Run `pytest tests/test_memory_superpowers.py::test_subagent_bridge -v`
2. Run the same test again immediately
3. The second run fails

### Expected vs Actual Behavior
- **Expected:** Each test run is isolated and deterministic
- **Actual:** The in-memory backend (or SQLite fallback) retains state from the previous run. The query at line 68-71 returns 2 memories with `source=subagent_distillation` instead of 1, because both runs create a `SubAgentBridge.merge_result()` entry.

### Evidence

```
$ pytest tests/test_memory_superpowers.py::test_subagent_bridge -v
# First run: PASSED
# Second run: FAILED
tests/test_memory_superpowers.py:74: AssertionError: assert 2 == 1
```

The two memories have different IDs (`1174a125` and `67079276`) and different `created_at` timestamps (16:07:16 vs 16:03:07), confirming they were created in different test runs. The `HierarchicalMemory.create()` uses a default backend that persists across test invocations.

### Suggested Fix
Add explicit cleanup in the test:

```python
@pytest.mark.asyncio
async def test_subagent_bridge():
    # Use a unique session ID per test run
    import uuid
    test_session = f"test_session_{uuid.uuid4().hex[:8]}"
    
    memory = await HierarchicalMemory.create()
    
    await memory.add(
        content="Important architectural decision: use hexagonal architecture.",
        user_id="test_user",
        session_id=test_session,
        importance=0.9
    )
    
    bridge = SubAgentBridge(
        memory=memory,
        parent_session_id=test_session,
        user_id="test_user"
    )
    ...
```

Or better: ensure the test fixture cleans up after itself via `memory.reset()` or `memory.clear_session()`.

---

## Bug 4: `SubAgentBridge.provision_subagent()` returns empty context silently

**Severity:** Medium
**Category:** Error handling gap

### Reproduction Steps
1. Create a `SubAgentBridge` pointing to a session that has **no memories** (empty session or wrong session_id)
2. Call `provision_subagent(task="do something")`
3. The returned payload has an empty `context_summary` string

### Expected vs Actual Behavior
- **Expected:** Either a warning/error is returned indicating empty context, or the payload includes a flag like `context_empty: True`
- **Actual:** Returns success with empty context. The sub-agent receives a task with zero context and no indication that anything is wrong.

### Evidence

```python
# cutctx/memory/subagent.py lines 44-68
memories = await self.memory.query(MemoryFilter(
    user_id=self.user_id,
    session_id=self.parent_session_id,
    limit=100
))
# If no memories match: memories is empty list
memories.sort(key=lambda m: (m.importance, m.created_at.timestamp()), reverse=True)
# Empty list sorts fine, produces nothing
top_memories = memories[:limit]  # Empty list
top_memories.sort(key=lambda m: m.created_at.timestamp())  # Empty list sorts fine
context_summary = "\n".join([f"- {m.content}" for m in top_memories])  # ""
# Returns {"task": task, "context_summary": "", "ccr_scope": {...}}
```

No guard, no logging, no warning.

### Suggested Fix
Add a guard after the query:

```python
memories = await self.memory.query(...)

if not memories:
    logger.warning(
        "No context found for session %s when provisioning sub-agent task: %s",
        self.parent_session_id, task
    )
    return {
        "task": task,
        "context_summary": "",
        "ccr_scope": {"user_id": self.user_id, "session_id": self.parent_session_id},
        "warning": "No context found for this session. Sub-agent will start with zero context.",
    }
```

---

## Bug 5: `SubAgentBridge.merge_result()` doesn't validate inputs

**Severity:** Low
**Category:** Defensive gap

### Reproduction Steps
1. Call `merge_result(subagent_id="", distilled_result="")`
2. The empty result is stored as a valid memory

### Expected vs Actual Behavior
- **Expected:** Empty `subagent_id` or empty `distilled_result` should be rejected upfront
- **Actual:** The call succeeds and stores `[Sub-Agent  Result]: ` with importance 0.8

### Evidence

```python
# cutctx/memory/subagent.py lines 71-91
async def merge_result(self, subagent_id: str, distilled_result: str, importance: float = 0.8) -> None:
    content = f"[Sub-Agent {subagent_id} Result]: {distilled_result}"
    
    await self.memory.add(
        content=content,
        user_id=self.user_id,
        session_id=self.parent_session_id,
        importance=importance,
        metadata={
            "source": "subagent_distillation",
            "subagent_id": subagent_id,
        }
    )
```

No validation of `subagent_id` or `distilled_result`. An invalid call produces a meaningless but persistent memory with high importance (0.8 default).

### Suggested Fix
```python
async def merge_result(self, subagent_id: str, distilled_result: str, importance: float = 0.8) -> None:
    if not subagent_id or not subagent_id.strip():
        raise ValueError("subagent_id must be a non-empty string")
    if not distilled_result or not distilled_result.strip():
        raise ValueError("distilled_result must be a non-empty string")
    if not 0.0 <= importance <= 1.0:
        raise ValueError("importance must be between 0.0 and 1.0")
    # ... rest of method
```

---

## Bug 6: `test_decision_trace_creation` doesn't test serialization roundtrip

**Severity:** Low
**Category:** Test coverage gap

### Reproduction Steps
1. Run the existing test `test_decision_trace_creation`
2. Note that it only tests field assignment and content auto-generation
3. It never tests `to_dict()` / `from_dict()` roundtrip

### Expected vs Actual Behavior
- **Expected:** The test covers the serialization contract since persistence depends on it
- **Actual:** Bug 2 (serialization loss) is invisible to the existing test suite

### Evidence

```python
# tests/test_memory_superpowers.py lines 12-30
async def test_decision_trace_creation():
    trace = DecisionTrace(
        user_id="alice",
        situation="System is slow",
        rationale="Needs caching",
        action="Added Redis",
        outcome="Latency improved by 50%"
    )
    # Only tests field access and content generation
    assert trace.user_id == "alice"
    assert trace.situation == "System is slow"
    assert trace.rationale == "Needs caching"
    assert trace.action == "Added Redis"
    assert trace.outcome == "Latency improved by 50%"
    assert trace.metadata["type"] == "decision_trace"
    # Never calls to_dict()/from_dict()
```

### Suggested Fix
Add a roundtrip test:

```python
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
```

(This test currently fails due to Bug 2.)

---

## Summary

| # | Bug | Severity | File | Status |
|---|-----|----------|------|--------|
| 1 | `memory_save_decision_trace` has no handler → silent failure | **Critical** | `system.py:263` | Unfixed |
| 2 | `DecisionTrace.to_dict/from_dict` drops 4 fields | **High** | `models.py:122-191` | Unfixed |
| 3 | `test_subagent_bridge` non-isolated across runs | **Medium** | `test_memory_superpowers.py:34` | Unfixed |
| 4 | `provision_subagent()` returns empty context silently | **Medium** | `subagent.py:44-68` | Unfixed |
| 5 | `merge_result()` doesn't validate empty inputs | **Low** | `subagent.py:71-91` | Unfixed |
| 6 | Roundtrip serialization untested → Bug 2 invisible | **Low** | `test_memory_superpowers.py:12` | Unfixed |

**Fixes 1-2 are required before the decision trace feature can function correctly.** Fixes 3-5 are quality/defensive improvements. Fix 6 is test coverage.
