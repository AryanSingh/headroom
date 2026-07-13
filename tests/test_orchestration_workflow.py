"""Durable DAG workflow contracts for the orchestration runtime."""

from __future__ import annotations

import asyncio

import pytest

from cutctx.orchestration import workflow as workflow_module
from cutctx.orchestration.workflow import (
    TaskArtifact,
    TaskSpec,
    WorkflowConflictError,
    WorkflowRunner,
    WorkflowSpec,
    WorkflowStateStore,
    WorkflowValidationError,
)


def test_workflow_rejects_unknown_dependency_and_cycles(tmp_path) -> None:
    store = WorkflowStateStore(tmp_path / "workflows.json")
    unknown = WorkflowSpec(
        id="unknown", tasks=[TaskSpec(id="a", role="worker", depends_on=["missing"])]
    )
    with pytest.raises(WorkflowValidationError, match="unknown task"):
        store.submit(unknown)

    cycle = WorkflowSpec(
        id="cycle",
        tasks=[
            TaskSpec(id="a", role="worker", depends_on=["b"]),
            TaskSpec(id="b", role="worker", depends_on=["a"]),
        ],
    )
    with pytest.raises(WorkflowValidationError, match="cycle"):
        store.submit(cycle)


def test_workflow_submission_is_idempotent_and_survives_restart(tmp_path) -> None:
    path = tmp_path / "workflows.json"
    spec = WorkflowSpec(
        id="review", idempotency_key="same-input", tasks=[TaskSpec(id="plan", role="planner")]
    )
    first = WorkflowStateStore(path).submit(spec)
    second = WorkflowStateStore(path).submit(spec)
    assert first.id == second.id
    restored = WorkflowStateStore(path).get(first.id)
    assert restored is not None
    assert restored.status == "pending"
    assert restored.tasks["plan"].status == "pending"


def test_idempotency_key_rejects_a_different_workflow_definition(tmp_path) -> None:
    store = WorkflowStateStore(tmp_path / "workflows.json")
    store.submit(
        WorkflowSpec(
            id="first",
            idempotency_key="request-key",
            tasks=[TaskSpec(id="plan", role="planner", payload={"topic": "first"})],
        )
    )

    with pytest.raises(WorkflowConflictError, match="different workflow"):
        store.submit(
            WorkflowSpec(
                id="second",
                idempotency_key="request-key",
                tasks=[TaskSpec(id="plan", role="planner", payload={"topic": "second"})],
            )
        )


def test_cancellation_is_terminal_and_does_not_cancel_completed_tasks(tmp_path) -> None:
    store = WorkflowStateStore(tmp_path / "workflows.json")
    workflow = store.submit(
        WorkflowSpec(
            id="release",
            tasks=[
                TaskSpec(id="build", role="worker"),
                TaskSpec(id="test", role="qa", depends_on=["build"]),
            ],
        )
    )
    assert store.claim_ready_task(workflow.id, "build") is True
    store.mark_task_completed(workflow.id, "build", {"ok": True})
    cancelled = store.cancel(workflow.id)
    assert cancelled.status == "cancelled"
    assert cancelled.tasks["build"].status == "completed"
    assert cancelled.tasks["test"].status == "cancelled"


def test_task_claim_is_single_owner_and_requires_dependencies(tmp_path) -> None:
    store = WorkflowStateStore(tmp_path / "workflows.json")
    workflow = store.submit(
        WorkflowSpec(
            id="ordered",
            tasks=[
                TaskSpec(id="a", role="worker"),
                TaskSpec(id="b", role="worker", depends_on=["a"]),
            ],
        )
    )
    assert store.claim_ready_task(workflow.id, "b") is False
    assert store.claim_ready_task(workflow.id, "a") is True
    assert store.claim_ready_task(workflow.id, "a") is False


@pytest.mark.asyncio
async def test_workflow_artifact_and_manual_gates_require_explicit_human_transitions(
    tmp_path,
) -> None:
    store = WorkflowStateStore(tmp_path / "workflows.json")
    spec = WorkflowSpec(
        id="gated-handoff",
        tasks=[
            TaskSpec(
                id="implement",
                role="implementer",
                artifact=TaskArtifact(
                    repository_ref="git:example/repo@abc",
                    worktree_ref="worktree:feature-42",
                    allowed_tools=["read", "edit", "test"],
                    provenance={"source_harness": "codex"},
                ),
                requires_approval=True,
                requires_verification=True,
            )
        ],
    )
    workflow = store.submit(spec)
    assert workflow.tasks["implement"].status == "awaiting_approval"
    restored = WorkflowStateStore(store.path).get(workflow.id)
    assert restored.task_specs["implement"].artifact.repository_ref == "git:example/repo@abc"

    executed: list[str] = []

    async def execute(task_id, _task):
        executed.append(task_id)
        return {"patch_ref": "artifact:patch-1", "test_evidence_ref": "artifact:test-1"}

    awaiting_approval = await WorkflowRunner(store, execute).run(workflow.id)
    assert awaiting_approval.status == "pending"
    assert executed == []

    store.approve_task(workflow.id, "implement")
    awaiting_verification = await WorkflowRunner(store, execute).run(workflow.id)
    assert awaiting_verification.tasks["implement"].status == "awaiting_verification"
    assert executed == ["implement"]

    completed = store.verify_task(workflow.id, "implement")
    assert completed.status == "completed"
    assert completed.tasks["implement"].verification_approved is True


@pytest.mark.asyncio
async def test_runner_runs_dependencies_in_order_and_parallelizes_ready_tasks(tmp_path) -> None:
    store = WorkflowStateStore(tmp_path / "workflows.json")
    spec = WorkflowSpec(
        id="dag",
        tasks=[
            TaskSpec(id="a", role="worker"),
            TaskSpec(id="b", role="worker"),
            TaskSpec(id="c", role="reviewer", depends_on=["a", "b"]),
        ],
    )
    workflow = store.submit(spec)
    completed: list[str] = []

    async def execute(task_id, _task):
        completed.append(task_id)
        return {"task": task_id}

    state = await WorkflowRunner(store, execute, max_concurrency=2).run(workflow.id, spec)
    assert state.status == "completed"
    assert completed[-1] == "c"
    assert {task.status for task in state.tasks.values()} == {"completed"}


@pytest.mark.asyncio
async def test_runner_failure_cancels_parallel_work_and_prevents_late_completion(tmp_path) -> None:
    store = WorkflowStateStore(tmp_path / "workflows.json")
    spec = WorkflowSpec(
        id="failure",
        tasks=[TaskSpec(id="fails", role="worker"), TaskSpec(id="slow", role="worker")],
    )
    workflow = store.submit(spec)
    slow_started = asyncio.Event()
    slow_cancelled = asyncio.Event()

    async def execute(task_id, _task):
        if task_id == "fails":
            await slow_started.wait()
            raise RuntimeError("provider unavailable")
        slow_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            slow_cancelled.set()
            raise

    state = await WorkflowRunner(store, execute, max_concurrency=2).run(workflow.id)
    assert state.status == "failed"
    assert state.tasks["fails"].status == "failed"
    assert state.tasks["slow"].status == "cancelled"
    assert slow_cancelled.is_set()
    assert store.get(workflow.id).tasks["slow"].status == "cancelled"


@pytest.mark.asyncio
async def test_runner_cancellation_stops_running_tasks(tmp_path) -> None:
    store = WorkflowStateStore(tmp_path / "workflows.json")
    workflow = store.submit(WorkflowSpec(id="cancel", tasks=[TaskSpec(id="work", role="worker")]))
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def execute(_task_id, _task):
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    runner = WorkflowRunner(store, execute)
    future = asyncio.create_task(runner.run(workflow.id))
    await started.wait()
    state = store.cancel(workflow.id)
    assert state.tasks["work"].status == "cancelled"
    result = await future
    assert result.status == "cancelled"
    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_expired_lease_recovers_running_task_with_persisted_payload(
    tmp_path, monkeypatch
) -> None:
    path = tmp_path / "workflows.json"
    spec = WorkflowSpec(
        id="restart",
        tasks=[
            TaskSpec(
                id="implement",
                role="worker",
                payload={"messages": [{"role": "user", "content": "hi"}]},
            )
        ],
    )
    monkeypatch.setattr(workflow_module.time, "time", lambda: 100.0)
    workflow = WorkflowStateStore(path, worker_id="worker-a", lease_seconds=1).submit(spec)
    original = WorkflowStateStore(path, worker_id="worker-a", lease_seconds=1)
    assert original.claim_ready_task(workflow.id, "implement") is True

    recovered = WorkflowStateStore(path, worker_id="worker-b", lease_seconds=1)
    recovered_state = recovered.get(workflow.id)
    assert recovered_state.status == "running"
    assert recovered_state.tasks["implement"].status == "running"
    assert recovered_state.task_specs["implement"].payload == spec.tasks[0].payload

    monkeypatch.setattr(workflow_module.time, "time", lambda: 102.0)

    executed = []

    async def execute(task_id, task):
        executed.append((task_id, task.payload))
        return {"ok": True}

    complete = await WorkflowRunner(recovered, execute).run(workflow.id)
    assert complete.status == "completed"
    assert complete.tasks["implement"].attempts == 2
    assert executed == [("implement", spec.tasks[0].payload)]


def test_independent_workers_cannot_claim_the_same_unexpired_task(tmp_path) -> None:
    path = tmp_path / "workflows.json"
    first = WorkflowStateStore(path, worker_id="worker-a")
    workflow = first.submit(WorkflowSpec(id="shared", tasks=[TaskSpec(id="work", role="worker")]))
    second = WorkflowStateStore(path, worker_id="worker-b")

    assert first.claim_ready_task(workflow.id, "work") is True
    assert second.claim_ready_task(workflow.id, "work") is False
    with pytest.raises(WorkflowValidationError, match="task is not running"):
        second.mark_task_completed(workflow.id, "work", {"wrong": "worker"})


def test_expired_lease_fences_out_stale_worker_completion(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(workflow_module.time, "time", lambda: 10.0)
    path = tmp_path / "workflows.json"
    first = WorkflowStateStore(path, worker_id="worker-a", lease_seconds=1)
    workflow = first.submit(WorkflowSpec(id="fenced", tasks=[TaskSpec(id="work", role="worker")]))
    assert first.claim_ready_task(workflow.id, "work") is True
    first_epoch = first.get(workflow.id).tasks["work"].lease_epoch

    monkeypatch.setattr(workflow_module.time, "time", lambda: 12.0)
    second = WorkflowStateStore(path, worker_id="worker-b", lease_seconds=1)
    assert second.claim_ready_task(workflow.id, "work") is True
    second_epoch = second.get(workflow.id).tasks["work"].lease_epoch
    assert second_epoch > first_epoch

    with pytest.raises(WorkflowValidationError, match="task is not running"):
        first.mark_task_completed(workflow.id, "work", {"stale": True}, lease_epoch=first_epoch)
    second.mark_task_completed(workflow.id, "work", {"fresh": True}, lease_epoch=second_epoch)
    assert second.get(workflow.id).tasks["work"].result == {"fresh": True}


@pytest.mark.asyncio
async def test_runner_waits_for_another_workers_active_lease_without_failing_workflow(
    tmp_path,
) -> None:
    path = tmp_path / "workflows.json"
    owner = WorkflowStateStore(path, worker_id="owner")
    workflow = owner.submit(
        WorkflowSpec(id="shared-run", tasks=[TaskSpec(id="work", role="worker")])
    )
    assert owner.claim_ready_task(workflow.id, "work") is True
    observer = WorkflowStateStore(path, worker_id="observer")

    async def execute(_task_id, _task):
        return {"should": "not run"}

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(
            WorkflowRunner(observer, execute, cancellation_poll_seconds=0.01).run(workflow.id),
            timeout=0.05,
        )
    assert observer.get(workflow.id).status == "running"
    assert observer.get(workflow.id).tasks["work"].status == "running"


@pytest.mark.asyncio
async def test_runner_cancellation_cancels_child_and_releases_task_for_resume(tmp_path) -> None:
    store = WorkflowStateStore(tmp_path / "workflows.json")
    workflow = store.submit(WorkflowSpec(id="shutdown", tasks=[TaskSpec(id="work", role="worker")]))
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def execute(_task_id, _task):
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    future = asyncio.create_task(WorkflowRunner(store, execute).run(workflow.id))
    await started.wait()
    future.cancel()
    with pytest.raises(asyncio.CancelledError):
        await future

    state = store.get(workflow.id)
    assert cancelled.is_set()
    assert state.status == "running"
    assert state.tasks["work"].status == "pending"


@pytest.mark.asyncio
async def test_runner_retries_transient_task_failure_with_bounded_attempts(tmp_path) -> None:
    store = WorkflowStateStore(tmp_path / "workflows.json")
    spec = WorkflowSpec(
        id="retry",
        tasks=[TaskSpec(id="fetch", role="research", max_attempts=3, retry_delay_seconds=0)],
    )
    workflow = store.submit(spec)
    calls = 0

    async def execute(_task_id, _task):
        nonlocal calls
        calls += 1
        if calls < 3:
            raise RuntimeError("temporary rate limit")
        return {"source": "recovered"}

    state = await WorkflowRunner(store, execute).run(workflow.id)
    assert state.status == "completed"
    assert state.tasks["fetch"].attempts == 3
    assert state.tasks["fetch"].result == {"source": "recovered"}


@pytest.mark.asyncio
async def test_runner_times_out_hung_task_then_records_durable_failure(tmp_path) -> None:
    store = WorkflowStateStore(tmp_path / "workflows.json")
    spec = WorkflowSpec(
        id="timeout",
        tasks=[TaskSpec(id="hang", role="worker", max_attempts=1, timeout_seconds=0.01)],
    )
    workflow = store.submit(spec)
    cancelled = asyncio.Event()

    async def execute(_task_id, _task):
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    state = await WorkflowRunner(store, execute).run(workflow.id)
    assert state.status == "failed"
    assert state.tasks["hang"].status == "failed"
    assert "TimeoutError" in state.tasks["hang"].result["error"]
    assert cancelled.is_set()
