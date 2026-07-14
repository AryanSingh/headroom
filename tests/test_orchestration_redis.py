from cutctx.orchestration.workflow import TaskSpec, WorkflowSpec, WorkflowStateStore
from cutctx.proxy.model_routing_evals import ModelRoutingEvalRecord, ModelRoutingEvalStore


def test_redis_workflow_state_is_shared_across_workers():
    url = "redis://127.0.0.1:6379/15"
    first = WorkflowStateStore("unused.json", worker_id="one", redis_url=url)
    second = WorkflowStateStore("unused.json", worker_id="two", redis_url=url)
    first.clear_redis_state()
    state = first.submit(WorkflowSpec(id="shared", tasks=[TaskSpec(id="task", role="worker")]))

    assert second.get(state.id) is not None
    assert second.claim_ready_task(state.id, "task") is True
    assert first.claim_ready_task(state.id, "task") is False


def test_redis_routing_evidence_is_shared_across_workers():
    url = "redis://127.0.0.1:6379/15"
    writer = ModelRoutingEvalStore("unused.jsonl", redis_url=url)
    reader = ModelRoutingEvalStore("unused.jsonl", redis_url=url)
    writer.clear_redis_state()
    writer.append(
        ModelRoutingEvalRecord(
            request_id="shared", prompt_hash="hash", source_model="strong", candidate_model="mini",
            scorer="test", confidence=0.9, quality_score=1.0, source_cost_usd=1.0,
            candidate_cost_usd=0.1,
        )
    )

    assert [record.request_id for record in reader.load()] == ["shared"]
