"""Durable, bounded DAG execution for role-bound orchestration work."""

from __future__ import annotations

import asyncio
import copy
import fcntl
import hashlib
import json
import os
import tempfile
import threading
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


class WorkflowValidationError(ValueError):
    """A workflow cannot be safely scheduled."""


class WorkflowConflictError(WorkflowValidationError):
    """An idempotency key was reused for a different immutable submission."""


@dataclass
class TaskArtifact:
    """Explicit, harness-neutral handoff metadata; never hidden chat state."""

    version: int = 1
    repository_ref: str = ""
    worktree_ref: str = ""
    allowed_tools: list[str] = field(default_factory=list)
    patch_ref: str = ""
    test_evidence_ref: str = ""
    review_evidence_ref: str = ""
    provenance: dict[str, str] = field(default_factory=dict)


@dataclass
class TaskSpec:
    id: str
    role: str
    depends_on: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
    max_attempts: int = 3
    retry_delay_seconds: float = 0.25
    timeout_seconds: float | None = None
    artifact: TaskArtifact = field(default_factory=TaskArtifact)
    requires_approval: bool = False
    requires_verification: bool = False


@dataclass
class WorkflowSpec:
    id: str
    tasks: list[TaskSpec]
    idempotency_key: str = ""


@dataclass
class TaskState:
    status: str = "pending"
    result: dict[str, Any] | None = None
    attempts: int = 0
    retry_at_epoch: float | None = None
    lease_owner: str = ""
    lease_expires_at_epoch: float | None = None
    lease_epoch: int = 0
    approval_granted: bool = False
    verification_approved: bool = False


@dataclass
class WorkflowState:
    id: str
    status: str
    tasks: dict[str, TaskState]
    idempotency_key: str = ""
    dependencies: dict[str, list[str]] = field(default_factory=dict)
    task_specs: dict[str, TaskSpec] = field(default_factory=dict)
    definition_hash: str = ""


class WorkflowStateStore:
    """JSON-backed workflow state with atomic transitions.

    Workers take a renewable lease for each claimed task. An expired lease is
    reclaimed at-least-once, so callers must provide an idempotency key to any
    underlying side effect that can mutate an external system.
    """

    def __init__(
        self,
        path: Path | str,
        *,
        worker_id: str | None = None,
        lease_seconds: float = 30.0,
        redis_url: str | None = None,
    ) -> None:
        self.path = Path(path)
        self.lock_path = self.path.with_suffix(f"{self.path.suffix}.lock")
        self.worker_id = worker_id or uuid.uuid4().hex
        self.lease_seconds = max(1.0, lease_seconds)
        self._lock = threading.RLock()
        self._states: dict[str, WorkflowState] = {}
        self._redis = None
        self._redis_key = ""
        configured_redis_url = redis_url or os.environ.get("CUTCTX_ORCHESTRATION_REDIS_URL")
        if configured_redis_url:
            try:
                import redis
            except ImportError as exc:
                raise WorkflowValidationError("Redis orchestration state requires the redis package") from exc
            self._redis = redis.Redis.from_url(configured_redis_url, decode_responses=True)
            self._redis_key = os.environ.get("CUTCTX_ORCHESTRATION_REDIS_KEY", "cutctx:orchestration:workflows")
            self._redis.ping()
        self._load()

    @staticmethod
    def _clone(state: WorkflowState) -> WorkflowState:
        return copy.deepcopy(state)

    def _load(self) -> None:
        if self._redis is not None:
            raw = self._redis.get(self._redis_key)
            if raw is None:
                self._states = {}
                return
            payload = json.loads(raw)
        else:
            if not self.path.exists():
                self._states = {}
                return
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise WorkflowValidationError(f"cannot load workflow state: {exc}") from exc

        states: dict[str, WorkflowState] = {}
        try:
            for item in payload.get("workflows", []):
                specs = {
                    task_id: TaskSpec(
                        **{
                            **task,
                            "artifact": TaskArtifact(**task.get("artifact", {})),
                        }
                    )
                    for task_id, task in item.get("task_specs", {}).items()
                }
                state = WorkflowState(
                    id=item["id"],
                    status=item["status"],
                    tasks={task_id: TaskState(**task) for task_id, task in item["tasks"].items()},
                    idempotency_key=item.get("idempotency_key", ""),
                    dependencies=item.get("dependencies", {}),
                    task_specs=specs,
                    definition_hash=item.get("definition_hash", ""),
                )
                states[state.id] = state
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowValidationError(f"invalid workflow state schema: {exc}") from exc
        self._states = states

    def _transaction(self):
        """Serialize state transitions across independent local workers."""

        if self._redis is not None:
            class _RedisTransaction:
                def __init__(transaction, store: WorkflowStateStore) -> None:
                    transaction.store = store
                    transaction.lock: Any | None = None

                def __enter__(transaction) -> None:
                    transaction.lock = transaction.store._redis.lock(f"{transaction.store._redis_key}:lock", timeout=15, blocking_timeout=10)
                    if not transaction.lock.acquire():
                        raise WorkflowValidationError("could not acquire Redis workflow lock")
                    transaction.store._load()

                def __exit__(transaction, exc_type, exc, traceback) -> None:
                    if transaction.lock is not None:
                        transaction.lock.release()

            return _RedisTransaction(self)

        class _Transaction:
            def __init__(transaction, store: WorkflowStateStore) -> None:
                transaction.store = store
                transaction.handle: Any | None = None

            def __enter__(transaction) -> None:
                transaction.store._lock.acquire()
                try:
                    transaction.store.lock_path.parent.mkdir(parents=True, exist_ok=True)
                    transaction.handle = transaction.store.lock_path.open("a+", encoding="utf-8")
                    fcntl.flock(transaction.handle.fileno(), fcntl.LOCK_EX)
                    transaction.store._load()
                except Exception:
                    if transaction.handle is not None:
                        fcntl.flock(transaction.handle.fileno(), fcntl.LOCK_UN)
                        transaction.handle.close()
                    transaction.store._lock.release()
                    raise

            def __exit__(transaction, exc_type, exc, traceback) -> None:
                try:
                    if transaction.handle is not None:
                        fcntl.flock(transaction.handle.fileno(), fcntl.LOCK_UN)
                        transaction.handle.close()
                finally:
                    transaction.store._lock.release()

        return _Transaction(self)

    def _save(self) -> None:
        if self._redis is not None:
            self._redis.set(self._redis_key, json.dumps({"workflows": [asdict(state) for state in self._states.values()]}))
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=self.path.parent, prefix=f".{self.path.name}.")
        temp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({"workflows": [asdict(state) for state in self._states.values()]}, handle)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.path)
            try:
                directory_fd = os.open(self.path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            except OSError:
                # Directory fsync is unavailable on some platforms; the file
                # rename above still prevents a torn JSON write.
                pass
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def clear_redis_state(self) -> None:
        if self._redis is None:
            raise WorkflowValidationError("Redis workflow state is not configured")
        self._redis.delete(self._redis_key)

    @staticmethod
    def _validate(spec: WorkflowSpec) -> None:
        if not spec.tasks:
            raise WorkflowValidationError("workflow requires at least one task")
        task_ids = [task.id for task in spec.tasks]
        if any(not task_id for task_id in task_ids):
            raise WorkflowValidationError("task id is required")
        if len(set(task_ids)) != len(task_ids):
            raise WorkflowValidationError("duplicate task id")
        if any(task.max_attempts < 1 for task in spec.tasks):
            raise WorkflowValidationError("max_attempts must be at least one")
        if any(task.retry_delay_seconds < 0 for task in spec.tasks):
            raise WorkflowValidationError("retry_delay_seconds cannot be negative")
        if any(
            task.timeout_seconds is not None and task.timeout_seconds <= 0 for task in spec.tasks
        ):
            raise WorkflowValidationError("timeout_seconds must be positive")
        if any(task.artifact.version != 1 for task in spec.tasks):
            raise WorkflowValidationError("unsupported task artifact version")
        if any(not isinstance(task.artifact.allowed_tools, list) for task in spec.tasks):
            raise WorkflowValidationError("task artifact allowed_tools must be a list")
        known = set(task_ids)
        if any(dependency not in known for task in spec.tasks for dependency in task.depends_on):
            raise WorkflowValidationError("unknown task dependency")

        dependencies = {task.id: task.depends_on for task in spec.tasks}
        visited: set[str] = set()
        active: set[str] = set()

        def visit(task_id: str) -> None:
            if task_id in active:
                raise WorkflowValidationError("dependency cycle")
            if task_id in visited:
                return
            active.add(task_id)
            for dependency in dependencies[task_id]:
                visit(dependency)
            active.remove(task_id)
            visited.add(task_id)

        for task_id in task_ids:
            visit(task_id)

    @staticmethod
    def _definition_hash(spec: WorkflowSpec) -> str:
        payload = {
            "id": spec.id,
            "tasks": [asdict(task) for task in spec.tasks],
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def submit(self, spec: WorkflowSpec) -> WorkflowState:
        self._validate(spec)
        definition_hash = self._definition_hash(spec)
        with self._transaction():
            if spec.idempotency_key:
                for state in self._states.values():
                    if state.idempotency_key == spec.idempotency_key:
                        if state.definition_hash != definition_hash:
                            raise WorkflowConflictError(
                                "idempotency key is already associated with a different workflow"
                            )
                        return self._clone(state)
            state = WorkflowState(
                id=uuid.uuid4().hex,
                status="pending",
                tasks={
                    task.id: TaskState(
                        status="awaiting_approval" if task.requires_approval else "pending"
                    )
                    for task in spec.tasks
                },
                idempotency_key=spec.idempotency_key,
                dependencies={task.id: list(task.depends_on) for task in spec.tasks},
                task_specs={task.id: copy.deepcopy(task) for task in spec.tasks},
                definition_hash=definition_hash,
            )
            self._states[state.id] = state
            self._save()
            return self._clone(state)

    def get(self, workflow_id: str) -> WorkflowState | None:
        with self._transaction():
            state = self._states.get(workflow_id)
            return self._clone(state) if state is not None else None

    def attach_definition(self, workflow_id: str, spec: WorkflowSpec) -> WorkflowState:
        """Reject unsafe legacy records that lack immutable task definitions."""
        del spec
        with self._transaction():
            if workflow_id not in self._states:
                raise WorkflowValidationError("unknown workflow")
            raise WorkflowValidationError("legacy workflow definition cannot be resumed safely")

    def _task(self, workflow_id: str, task_id: str) -> tuple[WorkflowState, TaskState]:
        state = self._states.get(workflow_id)
        if state is None:
            raise WorkflowValidationError("unknown workflow")
        task = state.tasks.get(task_id)
        if task is None:
            raise WorkflowValidationError("unknown workflow task")
        return state, task

    def _owns_active_lease(self, task: TaskState, lease_epoch: int | None) -> bool:
        expected_epoch = task.lease_epoch if lease_epoch is None else lease_epoch
        return (
            task.status == "running"
            and task.lease_owner == self.worker_id
            and task.lease_epoch == expected_epoch
            and task.lease_expires_at_epoch is not None
            and task.lease_expires_at_epoch > time.time()
        )

    def mark_task_completed(
        self,
        workflow_id: str,
        task_id: str,
        result: dict[str, Any],
        *,
        lease_epoch: int | None = None,
    ) -> None:
        with self._transaction():
            state, task = self._task(workflow_id, task_id)
            if state.status != "running" or not self._owns_active_lease(task, lease_epoch):
                raise WorkflowValidationError("task is not running")
            task_spec = state.task_specs.get(task_id)
            task.status = (
                "awaiting_verification"
                if task_spec and task_spec.requires_verification
                else "completed"
            )
            task.result = copy.deepcopy(result)
            task.lease_owner = ""
            task.lease_expires_at_epoch = None
            if all(item.status == "completed" for item in state.tasks.values()):
                state.status = "completed"
            self._save()

    def mark_task_failed(
        self,
        workflow_id: str,
        task_id: str,
        error: str,
        *,
        lease_epoch: int | None = None,
    ) -> None:
        with self._transaction():
            state, task = self._task(workflow_id, task_id)
            if state.status != "running" or not self._owns_active_lease(task, lease_epoch):
                return
            task_spec = state.task_specs.get(task_id)
            if task_spec is not None and task.attempts < task_spec.max_attempts:
                task.status = "pending"
                task.result = {"error": error, "retrying": True}
                task.retry_at_epoch = time.time() + task_spec.retry_delay_seconds
                task.lease_owner = ""
                task.lease_expires_at_epoch = None
                self._save()
                return
            task.status = "failed"
            task.result = {"error": error, "retrying": False}
            task.retry_at_epoch = None
            task.lease_owner = ""
            task.lease_expires_at_epoch = None
            state.status = "failed"
            for candidate in state.tasks.values():
                if candidate.status in {"pending", "running"}:
                    candidate.status = "cancelled"
                    candidate.lease_owner = ""
                    candidate.lease_expires_at_epoch = None
            self._save()

    def claim_ready_task(self, workflow_id: str, task_id: str) -> bool:
        """Atomically claim one dependency-ready task for a worker."""
        with self._transaction():
            state, task = self._task(workflow_id, task_id)
            if state.status not in {"pending", "running"}:
                return False
            if task.status == "running" and (
                task.lease_expires_at_epoch is None or task.lease_expires_at_epoch <= time.time()
            ):
                task.status = "pending"
                task.lease_owner = ""
                task.lease_expires_at_epoch = None
            if task.status != "pending":
                return False
            if task.retry_at_epoch is not None and task.retry_at_epoch > time.time():
                return False
            if any(
                state.tasks[dependency].status != "completed"
                for dependency in state.dependencies[task_id]
            ):
                return False
            state.status = "running"
            task.status = "running"
            task.attempts += 1
            task.retry_at_epoch = None
            task.lease_owner = self.worker_id
            task.lease_expires_at_epoch = time.time() + self.lease_seconds
            task.lease_epoch += 1
            self._save()
            return True

    def approve_task(self, workflow_id: str, task_id: str) -> WorkflowState:
        """Release an explicit human approval gate without changing task inputs."""
        with self._transaction():
            state, task = self._task(workflow_id, task_id)
            if task.status != "awaiting_approval":
                raise WorkflowValidationError("task is not awaiting approval")
            task.status = "pending"
            task.approval_granted = True
            self._save()
            return self._clone(state)

    def verify_task(self, workflow_id: str, task_id: str) -> WorkflowState:
        """Accept a completed result after out-of-band verification evidence."""
        with self._transaction():
            state, task = self._task(workflow_id, task_id)
            if task.status != "awaiting_verification":
                raise WorkflowValidationError("task is not awaiting verification")
            task.status = "completed"
            task.verification_approved = True
            if all(item.status == "completed" for item in state.tasks.values()):
                state.status = "completed"
            self._save()
            return self._clone(state)

    def has_manual_gates(self, workflow_id: str) -> bool:
        with self._transaction():
            state = self._states.get(workflow_id)
            return bool(
                state
                and any(
                    task.status in {"awaiting_approval", "awaiting_verification"}
                    for task in state.tasks.values()
                )
            )

    def renew_task_lease(
        self, workflow_id: str, task_id: str, *, lease_epoch: int | None = None
    ) -> bool:
        """Keep a claimed task exclusively owned while a worker is alive."""
        with self._transaction():
            state, task = self._task(workflow_id, task_id)
            if state.status != "running" or not self._owns_active_lease(task, lease_epoch):
                return False
            task.lease_expires_at_epoch = time.time() + self.lease_seconds
            self._save()
            return True

    def release_task(self, workflow_id: str, task_id: str, *, lease_epoch: int) -> bool:
        """Relinquish an owned lease after local runner shutdown/cancellation."""
        with self._transaction():
            state, task = self._task(workflow_id, task_id)
            if state.status != "running" or not self._owns_active_lease(task, lease_epoch):
                return False
            task.status = "pending"
            task.result = {"error": "runner_cancelled", "retrying": True}
            task.retry_at_epoch = None
            task.lease_owner = ""
            task.lease_expires_at_epoch = None
            self._save()
            return True

    def cancel(self, workflow_id: str) -> WorkflowState:
        with self._transaction():
            state = self._states.get(workflow_id)
            if state is None:
                raise WorkflowValidationError("unknown workflow")
            if state.status in {"completed", "failed"}:
                return self._clone(state)
            state.status = "cancelled"
            for task in state.tasks.values():
                if task.status in {
                    "pending",
                    "running",
                    "awaiting_approval",
                    "awaiting_verification",
                }:
                    task.status = "cancelled"
                    task.lease_owner = ""
                    task.lease_expires_at_epoch = None
            self._save()
            return self._clone(state)

    def fail_deadlocked_workflow(self, workflow_id: str) -> None:
        with self._transaction():
            state = self._states.get(workflow_id)
            if state is None or state.status not in {"pending", "running"}:
                return
            state.status = "failed"
            for task in state.tasks.values():
                if task.status == "pending":
                    task.status = "cancelled"
            self._save()

    def has_pending_tasks(self, workflow_id: str) -> bool:
        with self._transaction():
            state = self._states.get(workflow_id)
            return bool(state and any(task.status == "pending" for task in state.tasks.values()))

    def has_active_task_leases(self, workflow_id: str) -> bool:
        """Whether another local worker may still legitimately complete work."""
        with self._transaction():
            state = self._states.get(workflow_id)
            if state is None:
                return False
            now = time.time()
            return any(
                task.status == "running"
                and task.lease_expires_at_epoch is not None
                and task.lease_expires_at_epoch > now
                for task in state.tasks.values()
            )


class WorkflowRunner:
    """Bounded, dependency-aware runner over durable workflow state."""

    def __init__(
        self,
        store: WorkflowStateStore,
        execute: Callable[[str, TaskSpec], Awaitable[dict[str, Any]]],
        *,
        max_concurrency: int = 4,
        cancellation_poll_seconds: float = 0.05,
    ) -> None:
        self.store = store
        self.execute = execute
        self.max_concurrency = max(1, max_concurrency)
        self.cancellation_poll_seconds = max(0.01, cancellation_poll_seconds)

    async def run(self, workflow_id: str, spec: WorkflowSpec | None = None) -> WorkflowState:
        """Run or resume a workflow using its durable task definition.

        ``spec`` is accepted for backwards compatibility but is not trusted for
        resumed work: the persisted submission is the canonical task contract.
        """
        state = self.store.get(workflow_id)
        if state is None:
            raise WorkflowValidationError("unknown workflow")
        if spec is not None and {task.id for task in spec.tasks} != set(state.tasks):
            raise WorkflowValidationError("workflow definition does not match persisted state")
        if not state.task_specs:
            if spec is None:
                raise WorkflowValidationError("workflow definition is unavailable after restart")
            state = self.store.attach_definition(workflow_id, spec)

        in_flight: dict[asyncio.Task[None], tuple[str, int]] = {}
        try:
            while True:
                state = self.store.get(workflow_id)
                if state is None:
                    raise WorkflowValidationError("workflow disappeared")
                if state.status in {"cancelled", "failed", "completed"}:
                    break

                now = time.time()
                renewal_threshold = now + (self.store.lease_seconds / 2)
                for task_id, lease_epoch in in_flight.values():
                    lease_expires_at = state.tasks[task_id].lease_expires_at_epoch
                    if lease_expires_at is None or lease_expires_at <= renewal_threshold:
                        if not self.store.renew_task_lease(
                            workflow_id, task_id, lease_epoch=lease_epoch
                        ):
                            next(
                                future
                                for future, claim in in_flight.items()
                                if claim == (task_id, lease_epoch)
                            ).cancel()

                for task_id, task in state.task_specs.items():
                    if len(in_flight) >= self.max_concurrency:
                        break
                    if self.store.claim_ready_task(workflow_id, task_id):
                        claimed = self.store.get(workflow_id)
                        if claimed is None:
                            raise WorkflowValidationError("workflow disappeared")
                        lease_epoch = claimed.tasks[task_id].lease_epoch
                        future = asyncio.create_task(
                            self._run_one(workflow_id, task_id, task, lease_epoch)
                        )
                        in_flight[future] = (task_id, lease_epoch)

                if not in_flight:
                    if self.store.has_manual_gates(workflow_id):
                        break
                    if self.store.has_pending_tasks(
                        workflow_id
                    ) or self.store.has_active_task_leases(workflow_id):
                        await asyncio.sleep(self.cancellation_poll_seconds)
                        continue
                    # A valid submitted DAG should always have a task ready
                    # unless all work is terminal. Treat an impossible state as
                    # a durable failure rather than leaving a zombie workflow.
                    self.store.fail_deadlocked_workflow(workflow_id)
                    break

                done, _ = await asyncio.wait(
                    in_flight,
                    timeout=self.cancellation_poll_seconds,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for future in done:
                    in_flight.pop(future)
                    await future
        finally:
            for future in in_flight:
                future.cancel()
            if in_flight:
                await asyncio.gather(*in_flight, return_exceptions=True)
                for task_id, lease_epoch in in_flight.values():
                    self.store.release_task(workflow_id, task_id, lease_epoch=lease_epoch)
        return self.store.get(workflow_id) or state  # type: ignore[return-value]

    async def _run_one(
        self, workflow_id: str, task_id: str, task: TaskSpec, lease_epoch: int
    ) -> None:
        try:
            execution = self.execute(task_id, task)
            result = (
                await asyncio.wait_for(execution, timeout=task.timeout_seconds)
                if task.timeout_seconds is not None
                else await execution
            )
            self.store.mark_task_completed(workflow_id, task_id, result, lease_epoch=lease_epoch)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.store.mark_task_failed(
                workflow_id,
                task_id,
                f"{type(exc).__name__}: {exc}",
                lease_epoch=lease_epoch,
            )
