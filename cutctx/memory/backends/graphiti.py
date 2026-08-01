"""Graphiti OSS backend adapter for Cutctx hierarchical memory.

Maps Cutctx ``Memory`` objects onto Graphiti episodes / entity edges so
temporal knowledge-graph provenance (episode lineage, validity windows)
is available behind the same easy ``Memory(backend="graphiti")`` API.

Requires the optional ``graphiti-core`` package::

    pip install 'cutctx-ai[graphiti]'

Neo4j (or FalkorDB via Graphiti drivers) must be reachable. Connection
defaults come from ``NEO4J_URI``, ``NEO4J_USER``, ``NEO4J_PASSWORD``.

CutCtx-side supersession and deletion use the transactional SQLite episode
ledger (Graphiti's ``previous_episode_uuids`` is extraction context, not
invalidation).
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import logging
import os
import re
import uuid
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cutctx.memory.models import Memory, Provenance
from cutctx.memory.ports import MemorySearchResult

# Re-exported here so Graphiti callers have one stable migration-error import.
from .graphiti_ledger import (  # noqa: F401
    GraphitiLegacyMigrationRequired,
    SQLiteEpisodeLedger,
)

logger = logging.getLogger(__name__)

_GRAPHITI_INSTALL_HINT = (
    "graphiti-core is required for the Graphiti memory backend. "
    "Install with: pip install 'cutctx-ai[graphiti]'"
)
_GRAPHITI_VERSION_REQUIREMENT = "graphiti-core>=0.21,<0.23"


class GraphitiIdempotencyConflict(ValueError):
    """A retry key was reused for a different Graphiti write."""


class GraphitiWriteRecoveryRequired(RuntimeError):
    """Graphiti accepted a write but its ownership record was not activated."""

    def __init__(self, episode_id: str, partition_id: str, idempotency_key: str) -> None:
        self.episode_id = episode_id
        self.partition_id = partition_id
        self.idempotency_key = idempotency_key
        super().__init__(f"Graphiti write recovery required for episode {episode_id}")


class GraphitiDeletionError(RuntimeError):
    """Graphiti did not confirm that an episode was erased."""


class GraphitiUnsafeDeletionError(GraphitiDeletionError):
    """Removing an episode could erase a fact still supported elsewhere."""


class GraphitiClearError(GraphitiDeletionError):
    """A clear operation completed only part of its safe deletion set."""

    def __init__(self, confirmed: int, failed: int, failures: dict[str, Exception]) -> None:
        self.confirmed = confirmed
        self.failed = failed
        self.failures = failures
        super().__init__(f"Graphiti clear confirmed {confirmed} deletions; {failed} failed")


def _scope_partition(user_id: str, session_id: str | None) -> str:
    """Return a stable, opaque Graphiti-safe partition for a memory scope."""
    digest = hashlib.sha256()
    digest.update(b"cutctx.graphiti.scope.v1\0")
    for value in (user_id, session_id or ""):
        encoded = value.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return f"cutctx_{digest.hexdigest()[:32]}"


def _validate_graphiti_version(version: str) -> None:
    """Reject Graphiti releases outside the adapter's tested contract."""
    if not re.fullmatch(r"^0\.(?:21|22)(?:\.\d+)?$", version):
        raise RuntimeError(
            f"Unsupported graphiti-core version {version!r}; "
            f"requires {_GRAPHITI_VERSION_REQUIREMENT}"
        )


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _import_graphiti() -> tuple[Any, Any]:
    """Import Graphiti client class and EpisodeType enum.

    Returns:
        ``(Graphiti, EpisodeType)``

    Raises:
        ImportError: When ``graphiti-core`` is not installed.
    """
    try:
        from graphiti_core import Graphiti
        from graphiti_core.nodes import EpisodeType
    except ImportError as exc:
        raise ImportError(_GRAPHITI_INSTALL_HINT) from exc
    return Graphiti, EpisodeType


@dataclass
class GraphitiConfig:
    """Configuration for the Graphiti OSS memory backend."""

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    default_source_description: str = "cutctx"
    episode_source: str = "text"
    # Persist CutCtx supersession/deletion across restarts.
    ledger_path: Path | None = None

    def __post_init__(self) -> None:
        if isinstance(self.ledger_path, str):
            self.ledger_path = Path(self.ledger_path)
        if not self.neo4j_password:
            logger.warning(
                "Graphiti Neo4j password is empty. Set NEO4J_PASSWORD or "
                "GraphitiConfig.neo4j_password for a working connection."
            )

    @classmethod
    def from_env(cls, **overrides: Any) -> GraphitiConfig:
        """Build config from ``NEO4J_*`` environment variables."""
        values: dict[str, Any] = {
            "neo4j_uri": os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
            "neo4j_user": os.environ.get("NEO4J_USER", "neo4j"),
            "neo4j_password": os.environ.get("NEO4J_PASSWORD", ""),
        }
        ledger = os.environ.get("CUTCTX_GRAPHITI_LEDGER")
        if ledger:
            values["ledger_path"] = Path(ledger)
        values.update(overrides)
        return cls(**values)


class GraphitiBackend:
    """Memory backend backed by Graphiti's temporal context graph."""

    def __init__(
        self,
        config: GraphitiConfig | None = None,
        client: Any | None = None,
    ) -> None:
        self._config = config or GraphitiConfig.from_env()
        if self._config.ledger_path is None:
            # Default ledger under workspace so supersessions survive restarts.
            try:
                from cutctx import paths as _paths

                default_dir = _paths.memory_db_path().parent
            except Exception:
                default_dir = Path.home() / ".cutctx"
            self._config.ledger_path = default_dir / "graphiti_ledger.json"
        self._client = client
        self._episode_type: Any | None = None
        self._initialized = client is not None
        self._ledger = SQLiteEpisodeLedger(self._config.ledger_path)

    async def _ensure_initialized(self) -> None:
        if self._initialized and self._client is not None:
            return

        Graphiti, EpisodeType = _import_graphiti()
        self._episode_type = EpisodeType
        if self._client is None:
            _validate_graphiti_version(importlib.metadata.version("graphiti-core"))
            self._client = Graphiti(
                self._config.neo4j_uri,
                self._config.neo4j_user,
                self._config.neo4j_password,
            )
            build = getattr(self._client, "build_indices_and_constraints", None)
            if callable(build):
                result = build()
                if hasattr(result, "__await__"):
                    await result
        self._initialized = True

    def _resolve_episode_source(self) -> Any:
        if self._episode_type is None:
            return SimpleEpisodeType(self._config.episode_source)
        name = self._config.episode_source
        return getattr(self._episode_type, name, self._episode_type.text)

    async def close(self) -> None:
        if self._client is not None and hasattr(self._client, "close"):
            close = self._client.close
            result = close()
            if hasattr(result, "__await__"):
                await result

    async def save(
        self,
        memory: Memory,
        *,
        idempotency_key: str | None = None,
        _activate: bool = True,
        _lock: bool = True,
    ) -> Memory:
        """Persist a Cutctx Memory as a Graphiti episode."""
        await self._ensure_initialized()
        assert self._client is not None

        source_description = str(
            (memory.metadata or {}).get(
                "source_description", self._config.default_source_description
            )
        )
        reference_time = memory.valid_from or memory.created_at or _utcnow()
        if reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=timezone.utc)
        partition_id = _scope_partition(memory.user_id or "", memory.session_id)
        retry_key = idempotency_key or str(uuid.uuid4())
        existing = self._ledger.find_by_idempotency_key(retry_key) if idempotency_key else None
        if existing is not None and existing.provider_reference_time is not None:
            reference_time = existing.provider_reference_time

        meta = dict(memory.metadata or {})
        if memory.session_id:
            meta.setdefault("session_id", memory.session_id)
        memory.metadata = meta

        episode_candidate = memory.id or str(uuid.uuid4())
        kwargs: dict[str, Any] = {
            "name": f"cutctx:{episode_candidate}",
            "episode_body": memory.content,
            "source_description": source_description,
            "reference_time": reference_time,
            "source": self._resolve_episode_source(),
            "group_id": partition_id,
            "uuid": episode_candidate,
        }
        if memory.supersedes:
            kwargs["previous_episode_uuids"] = [memory.supersedes]

        payload = json.dumps(
            {
                "episode_body": memory.content,
                "source_description": source_description,
                "reference_time": reference_time.isoformat(),
                "episode_source": self._config.episode_source,
                "previous_episode_uuids": kwargs.get("previous_episode_uuids", []),
                "user_id": memory.user_id,
                "session_id": memory.session_id,
                "partition_id": partition_id,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        try:
            reserved = self._ledger.reserve_write(
                episode_id=episode_candidate,
                user_key=memory.user_id or "",
                session_key=memory.session_id,
                partition_id=partition_id,
                idempotency_key=retry_key,
                payload=payload,
                provider_reference_time=reference_time,
            )
        except ValueError as exc:
            raise GraphitiIdempotencyConflict(str(exc)) from exc
        episode_uuid = reserved.episode_id
        kwargs["name"] = f"cutctx:{episode_uuid}"
        kwargs["uuid"] = episode_uuid

        if reserved.state == "write_pending":
            # filelock is an optional transitive dependency of Graphiti's
            # mutation path; searching a durable ledger must remain usable
            # without importing it.
            from .graphiti_lock import PartitionOperationLock

            ledger_path = self._config.ledger_path
            assert ledger_path is not None
            client = self._client
            assert client is not None

            async def write_and_activate() -> None:
                await client.add_episode(**kwargs)
                if _activate:
                    try:
                        self._ledger.activate(episode_uuid)
                    except Exception as exc:
                        raise GraphitiWriteRecoveryRequired(
                            episode_uuid, partition_id, retry_key
                        ) from exc

            if _lock:
                async with PartitionOperationLock(ledger_path, partition_id, timeout=30):
                    await write_and_activate()
            else:
                await write_and_activate()

        memory.id = episode_uuid
        if memory.provenance is None:
            memory.provenance = Provenance(
                created_by_session=memory.session_id,
                created_by_agent=memory.agent_id,
                source="graphiti",
                commit_sha=None,
                created_at=reference_time.timestamp(),
            )
        return memory

    async def save_memory(
        self,
        content: str,
        user_id: str,
        importance: float = 0.5,
        entities: list[str] | None = None,
        relationships: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
        session_id: str | None = None,
        agent_id: str | None = None,
        turn_id: str | None = None,
        facts: list[str] | None = None,
        extracted_entities: list[dict[str, str]] | None = None,
        extracted_relationships: list[dict[str, str]] | None = None,
        idempotency_key: str | None = None,
        **_: Any,
    ) -> Memory:
        """Easy-API compatible save (matches LocalBackend / DirectMem0).

        When ``facts`` is provided, each fact is stored as its own episode
        (same as LocalBackend). Returns the primary (first) memory.
        """
        entity_refs: list[str] = list(entities or [])
        if extracted_entities:
            for ent in extracted_entities:
                name = ent.get("entity", "")
                if name and name not in entity_refs:
                    entity_refs.append(name)

        base_meta = dict(metadata or {})
        if relationships or extracted_relationships:
            base_meta["relationships"] = relationships or extracted_relationships
        if session_id:
            base_meta["session_id"] = session_id

        bodies = list(facts) if facts else [content]
        created: list[Memory] = []
        for i, body in enumerate(bodies):
            now = _utcnow()
            fact_meta = {**base_meta}
            if facts:
                fact_meta["_fact_index"] = i
                fact_meta["_fact_count"] = len(bodies)
            memory = Memory(
                id=str(uuid.uuid4()),
                content=body,
                user_id=user_id,
                session_id=session_id,
                agent_id=agent_id,
                turn_id=turn_id,
                importance=importance,
                entity_refs=entity_refs,
                metadata=fact_meta,
                created_at=now,
                valid_from=now,
            )
            fact_key = (
                f"{idempotency_key}:{i}" if idempotency_key and len(bodies) > 1 else idempotency_key
            )
            created.append(await self.save(memory, idempotency_key=fact_key))
        return created[0]

    def _edge_to_memory(self, edge: Any, user_id: str, episode_ids: list[str]) -> Memory:
        valid_at = getattr(edge, "valid_at", None)
        if isinstance(valid_at, datetime) and valid_at.tzinfo is None:
            valid_at = valid_at.replace(tzinfo=timezone.utc)
        invalid_at = getattr(edge, "invalid_at", None)
        if isinstance(invalid_at, datetime) and invalid_at.tzinfo is None:
            invalid_at = invalid_at.replace(tzinfo=timezone.utc)
        edge_uuid = str(getattr(edge, "uuid", "") or uuid.uuid4())
        fact = str(getattr(edge, "fact", "") or "")

        memory_id = episode_ids[0] if episode_ids else edge_uuid

        if valid_at is None:
            reference_times = [
                record.provider_reference_time
                for episode_id in episode_ids
                if (record := self._ledger.get(episode_id)) is not None
                and record.provider_reference_time is not None
            ]
            if reference_times:
                valid_at = min(reference_times)

        # Multi-parent semantics: hide only when ALL retained supporting episodes close.
        ledger_invalid = self._ledger.invalid_at_for(episode_ids or [memory_id])
        if ledger_invalid is not None:
            if invalid_at is None or ledger_invalid < invalid_at:
                invalid_at = ledger_invalid

        return Memory(
            id=memory_id,
            content=fact,
            user_id=user_id,
            session_id=None,
            valid_from=valid_at or _utcnow(),
            valid_until=invalid_at,
            metadata={
                "graphiti_edge_uuid": edge_uuid,
                "graphiti_episode_uuids": episode_ids,
                "backend": "graphiti",
            },
            provenance=Provenance(
                created_by_session=None,
                created_by_agent=None,
                source="graphiti",
                commit_sha=None,
                created_at=(valid_at or _utcnow()).timestamp(),
            ),
        )

    async def search_memories(
        self,
        query: str,
        user_id: str,
        top_k: int = 10,
        entities: list[str] | None = None,
        include_related: bool = True,
        session_id: str | None = None,
        include_superseded: bool = False,
        valid_at: datetime | None = None,
        **_: Any,
    ) -> list[MemorySearchResult]:
        """Search Graphiti and map entity edges back to Cutctx memories.

        ``include_related`` is accepted for API parity with LocalBackend.
        Graphiti hybrid search already returns graph-neighborhood facts; no
        extra expansion pass is performed.
        """
        await self._ensure_initialized()
        assert self._client is not None

        allowed_partitions = self._ledger.partitions_for_scope(user_id, session_id)
        if not allowed_partitions:
            return []

        # Over-fetch slightly so post-filters still fill top_k.
        fetch_n = max(top_k * 3, top_k)
        edges = await self._client.search(
            query=query,
            group_ids=allowed_partitions,
            num_results=fetch_n,
        )

        if valid_at is not None and valid_at.tzinfo is None:
            valid_at = valid_at.replace(tzinfo=timezone.utc)

        results: list[MemorySearchResult] = []
        edge_list = list(edges or [])
        for rank, edge in enumerate(edge_list):
            raw_episodes = getattr(edge, "episodes", None) or []
            if not isinstance(raw_episodes, list):
                raw_episodes = list(raw_episodes) if raw_episodes else []
            episode_ids = [str(episode_id) for episode_id in raw_episodes]
            owned_episode_ids = [
                episode_id
                for episode_id in episode_ids
                if (record := self._ledger.get(episode_id)) is not None
                and record.partition_id in allowed_partitions
                and record.state in {"active", "delete_pending"}
            ]
            historical_episode_ids = [
                episode_id
                for episode_id in episode_ids
                if (record := self._ledger.get(episode_id)) is not None
                and record.partition_id in allowed_partitions
                and record.state == "superseded"
            ]
            visible_episode_ids = owned_episode_ids
            if not visible_episode_ids and (include_superseded or valid_at is not None):
                visible_episode_ids = historical_episode_ids
            if not visible_episode_ids:
                continue
            memory = self._edge_to_memory(edge, user_id=user_id, episode_ids=visible_episode_ids)
            if valid_at is None and not include_superseded and memory.valid_until is not None:
                continue
            if valid_at is not None:
                vf = memory.valid_from
                if vf is not None and vf.tzinfo is None:
                    vf = vf.replace(tzinfo=timezone.utc)
                vu = memory.valid_until
                if vu is not None and vu.tzinfo is None:
                    vu = vu.replace(tzinfo=timezone.utc)
                if vf is not None and vf > valid_at:
                    continue
                if vu is not None and vu <= valid_at:
                    continue

            if entities:
                content_l = memory.content.lower()
                if not any(e.lower() in content_l for e in entities):
                    continue

            raw_score = getattr(edge, "score", None)
            if raw_score is None:
                # Rank-based fallback when Graphiti edges lack .score
                score = 1.0 - (rank / max(len(edge_list), 1))
            else:
                score = float(raw_score or 0.0)
            results.append(
                MemorySearchResult(
                    memory=memory,
                    score=score,
                    related_entities=list(entities or []),
                    related_memories=[],
                )
            )
            if len(results) >= top_k:
                break

        return results

    async def supersede(
        self,
        old_memory_id: str,
        new_memory: Memory,
        supersede_time: datetime | None = None,
    ) -> Memory:
        """Supersede by writing a new episode and closing the prior episode."""
        when = supersede_time or _utcnow()
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        new_memory.supersedes = old_memory_id
        new_memory.valid_from = when
        meta = dict(new_memory.metadata or {})
        meta["supersedes_episode_uuid"] = old_memory_id
        new_memory.metadata = meta
        partition_id = _scope_partition(new_memory.user_id or "", new_memory.session_id)
        retry_key = hashlib.sha256(
            f"cutctx.graphiti.supersede.v1\0{old_memory_id}\0{new_memory.id}\0{new_memory.content}".encode()
        ).hexdigest()
        async with self._partition_locks({partition_id}):
            replacement = await self.save(
                new_memory, idempotency_key=retry_key, _activate=False, _lock=False
            )
            try:
                self._ledger.record_replacement(old_memory_id, replacement.id, when)
            except Exception as exc:
                raise GraphitiWriteRecoveryRequired(
                    replacement.id, partition_id, retry_key
                ) from exc
            return replacement

    @asynccontextmanager
    async def _partition_locks(self, partition_ids: set[str]) -> Any:
        """Acquire all scope locks in a stable order, avoiding cross-scope deadlocks."""
        from .graphiti_lock import PartitionOperationLock

        ledger_path = self._config.ledger_path
        assert ledger_path is not None
        async with AsyncExitStack() as stack:
            for partition_id in sorted(partition_ids):
                await stack.enter_async_context(
                    PartitionOperationLock(ledger_path, partition_id, timeout=30)
                )
            yield

    async def _preflight_deletion(self, episode_ids: set[str]) -> list[str]:
        """Refuse deletion if provenance cannot prove every shared fact survives.

        Graphiti orders an edge's episodes with its origin first.  A non-origin
        supporter can always be removed independently; an origin cannot be
        removed while an external active supporter still refers to it.
        """
        assert self._client is not None
        targets = set(episode_ids)
        records = {episode_id: self._ledger.get(episode_id) for episode_id in targets}
        if any(record is None for record in records.values()):
            raise GraphitiUnsafeDeletionError("unknown episode provenance")
        partition_ids = {record.partition_id for record in records.values() if record is not None}
        if len(partition_ids) != 1:
            raise GraphitiUnsafeDeletionError("deletion set spans foreign scopes")
        try:
            result = await self._client.get_nodes_and_edges_by_episode(sorted(targets))
        except GraphitiUnsafeDeletionError:
            raise
        except Exception as exc:
            raise GraphitiDeletionError("Graphiti deletion preflight failed") from exc
        edges = (
            result[1]
            if isinstance(result, tuple) and len(result) > 1
            else getattr(result, "edges", [])
        )
        origins: set[str] = set()
        partition_id = next(iter(partition_ids))
        for edge in edges or []:
            supporters = [str(value) for value in (getattr(edge, "episodes", None) or [])]
            if not supporters or supporters[0] not in targets:
                continue
            origin = supporters[0]
            origins.add(origin)
            for supporter in supporters[1:]:
                if supporter in targets:
                    continue
                record = self._ledger.get(supporter)
                if record is None or record.partition_id != partition_id:
                    raise GraphitiUnsafeDeletionError("unknown or foreign supporter provenance")
                if record.state in {"write_pending", "delete_pending"}:
                    raise GraphitiUnsafeDeletionError("supporter lifecycle is unresolved")
                if record.state not in {"deleted", "superseded"}:
                    raise GraphitiUnsafeDeletionError("origin has an active external supporter")
        return sorted(targets, key=lambda episode_id: (episode_id in origins, episode_id))

    async def _deletion_order(self, episode_ids: set[str]) -> list[str]:
        """Order a batch without treating planned deletion as completed deletion.

        Safety is deliberately checked again for each episode just before its
        mutation.  A supporter that fails remotely remains ``delete_pending``
        and therefore blocks its dependent origin in that fresh preflight.
        """
        assert self._client is not None
        try:
            result = await self._client.get_nodes_and_edges_by_episode(sorted(episode_ids))
        except GraphitiUnsafeDeletionError:
            raise
        except Exception as exc:
            raise GraphitiDeletionError("Graphiti deletion preflight failed") from exc
        edges = (
            result[1]
            if isinstance(result, tuple) and len(result) > 1
            else getattr(result, "edges", [])
        )
        origins = {
            str(getattr(edge, "episodes", [])[0])
            for edge in edges or []
            if getattr(edge, "episodes", None) and str(edge.episodes[0]) in episode_ids
        }
        return sorted(episode_ids, key=lambda episode_id: (episode_id in origins, episode_id))

    @staticmethod
    def _is_not_found(error: Exception) -> bool:
        return error.__class__.__name__ == "NodeNotFoundError"

    async def _delete_memory_locked(self, memory_id: str) -> bool:
        assert self._client is not None
        record = self._ledger.get(memory_id)
        if record is None or record.state == "deleted":
            return False
        # Do not rely on the clear batch's original membership: an earlier
        # remote failure changes the ledger state and must block this mutation.
        await self._preflight_deletion({memory_id})
        try:
            self._ledger.mark_delete_pending(memory_id)
            await self._client.remove_episode(memory_id)
            self._ledger.mark_deleted(memory_id)
            return True
        except Exception as exc:
            # A retry after a successful remote deletion but failed local
            # finalization is truthful: Graphiti confirms it no longer exists.
            if self._is_not_found(exc):
                try:
                    self._ledger.mark_deleted(memory_id)
                    return True
                except Exception as finalization_error:
                    exc = finalization_error
            try:
                self._ledger.mark_delete_failed(memory_id, str(exc))
            except Exception:
                pass
            raise GraphitiDeletionError(str(exc)) from exc

    async def delete_memory(self, memory_id: str) -> bool:
        """Erase an owned episode only after Graphiti confirms removal."""
        await self._ensure_initialized()
        record = self._ledger.get(memory_id)
        if record is None or record.state == "deleted":
            return False
        async with self._partition_locks({record.partition_id}):
            return await self._delete_memory_locked(memory_id)

    async def clear_user(self, user_id: str) -> int:
        """Erase every independently-safe owned episode, reporting partial failure."""
        await self._ensure_initialized()
        records = [
            record
            for record in self._ledger.records_for_user(user_id)
            if record.state in {"active", "superseded", "delete_pending"}
        ]
        if not records:
            return 0
        by_partition: dict[str, set[str]] = {}
        for record in records:
            by_partition.setdefault(record.partition_id, set()).add(record.episode_id)
        confirmed = 0
        failures: dict[str, Exception] = {}
        async with self._partition_locks(set(by_partition)):
            for partition_id in sorted(by_partition):
                episode_ids = by_partition[partition_id]
                try:
                    order = await self._deletion_order(episode_ids)
                except Exception as exc:
                    failures.update(dict.fromkeys(episode_ids, exc))
                    continue
                for episode_id in order:
                    try:
                        if await self._delete_memory_locked(episode_id):
                            confirmed += 1
                    except GraphitiDeletionError as exc:
                        failures[episode_id] = exc
        if failures:
            raise GraphitiClearError(confirmed, len(failures), failures)
        return confirmed


@dataclass
class SimpleEpisodeType:
    """Stand-in EpisodeType when the Graphiti package is not loaded (tests)."""

    value: str = "text"

    @property
    def text(self) -> SimpleEpisodeType:
        return SimpleEpisodeType("text")

    @property
    def message(self) -> SimpleEpisodeType:
        return SimpleEpisodeType("message")

    @property
    def json(self) -> SimpleEpisodeType:
        return SimpleEpisodeType("json")
