"""Hierarchical memory data models for Cutctx."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore[assignment]


class ScopeLevel(Enum):
    """Memory scope hierarchy levels."""

    USER = "user"  # Persistent across all sessions
    SESSION = "session"  # Persistent within a task/conversation
    AGENT = "agent"  # Persistent within an agent's lifetime
    TURN = "turn"  # Ephemeral, single LLM call


@dataclass
class Provenance:
    """Provenance tracking for a memory's origin."""

    created_by_session: str | None
    created_by_agent: str | None
    source: str  # "learn" | "manual" | "extracted" | "imported"
    commit_sha: str | None  # if created during a coding session
    created_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "created_by_session": self.created_by_session,
            "created_by_agent": self.created_by_agent,
            "source": self.source,
            "commit_sha": self.commit_sha,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Provenance | None:
        if not data:
            return None
        return cls(
            created_by_session=data.get("created_by_session"),
            created_by_agent=data.get("created_by_agent"),
            source=data.get("source", "unknown"),
            commit_sha=data.get("commit_sha"),
            created_at=data.get("created_at", 0.0),
        )


@dataclass
class Memory:
    """A hierarchically-scoped memory with temporal awareness."""

    # Identity
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""

    # Hierarchical Scoping (required: user_id, optional: narrower scopes)
    user_id: str = ""
    workspace_id: str | None = None
    project_id: str | None = None
    session_id: str | None = None
    agent_id: str | None = None
    turn_id: str | None = None

    # Temporal
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    valid_from: datetime = field(default_factory=lambda: datetime.now(UTC))
    valid_until: datetime | None = None  # None = current/active

    # Classification
    importance: float = 0.5  # 0.0 - 1.0
    value_score: float = 0.5  # 0.0 - 1.0 (Outcome-linked EWMA)
    last_value_update: float = 0.0
    citations: list[str] = field(default_factory=list)
    outcome_links: list[str] = field(default_factory=list)

    # Lineage (for supersession and bubbling)
    supersedes: str | None = None  # ID of memory this replaced
    superseded_by: str | None = None  # ID of memory that replaced this
    promoted_from: str | None = None  # ID of child memory (if bubbled up)
    promotion_chain: list[str] = field(default_factory=list)
    provenance: Provenance | None = None

    # Access tracking
    access_count: int = 0
    last_accessed: datetime | None = None

    # Entity references
    entity_refs: list[str] = field(default_factory=list)

    # Embedding (for vector search)
    embedding: Any = None  # np.ndarray when numpy is available

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def scope_level(self) -> ScopeLevel:
        """Compute the scope level from hierarchy fields."""
        if self.turn_id is not None:
            return ScopeLevel.TURN
        if self.agent_id is not None:
            return ScopeLevel.AGENT
        if self.session_id is not None:
            return ScopeLevel.SESSION
        return ScopeLevel.USER

    @property
    def is_current(self) -> bool:
        """Check if this memory is current (not superseded)."""
        return self.valid_until is None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "content": self.content,
            "user_id": self.user_id,
            "workspace_id": self.workspace_id,
            "project_id": self.project_id,
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "turn_id": self.turn_id,
            "created_at": self.created_at.isoformat(),
            "valid_from": self.valid_from.isoformat(),
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
            "importance": self.importance,
            "value_score": self.value_score,
            "last_value_update": self.last_value_update,
            "citations": self.citations,
            "outcome_links": self.outcome_links,
            "supersedes": self.supersedes,
            "superseded_by": self.superseded_by,
            "promoted_from": self.promoted_from,
            "promotion_chain": self.promotion_chain,
            "provenance": self.provenance.to_dict() if self.provenance else None,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "entity_refs": self.entity_refs,
            "embedding": self.embedding.tolist() if self.embedding is not None else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Memory:
        """Create from dictionary."""
        embedding = None
        if data.get("embedding") and np is not None:
            embedding = np.array(data["embedding"], dtype=np.float32)

        return cls(
            id=data["id"],
            content=data["content"],
            user_id=data.get("user_id", ""),
            workspace_id=data.get("workspace_id"),
            project_id=data.get("project_id"),
            session_id=data.get("session_id"),
            agent_id=data.get("agent_id"),
            turn_id=data.get("turn_id"),
            created_at=datetime.fromisoformat(data["created_at"]),
            valid_from=datetime.fromisoformat(data["valid_from"]),
            valid_until=datetime.fromisoformat(data["valid_until"])
            if data.get("valid_until")
            else None,
            importance=data.get("importance", 0.5),
            value_score=data.get("value_score", 0.5),
            last_value_update=data.get("last_value_update", 0.0),
            citations=data.get("citations", []),
            outcome_links=data.get("outcome_links", []),
            supersedes=data.get("supersedes"),
            superseded_by=data.get("superseded_by"),
            promoted_from=data.get("promoted_from"),
            promotion_chain=data.get("promotion_chain", []),
            provenance=Provenance.from_dict(data.get("provenance")),
            access_count=data.get("access_count", 0),
            last_accessed=datetime.fromisoformat(data["last_accessed"])
            if data.get("last_accessed")
            else None,
            entity_refs=data.get("entity_refs", []),
            embedding=embedding,
            metadata=data.get("metadata", {}),
        )


@dataclass
class DecisionTrace(Memory):
    """A reasoning trace storing Situation, Rationale, Action, and Outcome.
    
    This provides agents with "reasoning memory" to understand why past
    decisions were made, avoiding repeated mistakes.
    """
    
    situation: str = ""
    rationale: str = ""
    action: str = ""
    outcome: str = ""
    
    def __post_init__(self):
        # Ensure the content string also reflects the decision trace
        if not self.content:
            self.content = (
                f"Situation: {self.situation}\n"
                f"Rationale: {self.rationale}\n"
                f"Action: {self.action}\n"
                f"Outcome: {self.outcome}"
            )
        self.metadata["type"] = "decision_trace"
        self.metadata["situation"] = self.situation
        self.metadata["rationale"] = self.rationale
        self.metadata["action"] = self.action
        self.metadata["outcome"] = self.outcome

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
        import dataclasses
        kwargs = {f.name: getattr(base, f.name) for f in dataclasses.fields(Memory)}
        kwargs.update({
            "situation": situation,
            "rationale": rationale,
            "action": action,
            "outcome": outcome,
        })
        return cls(**kwargs)
