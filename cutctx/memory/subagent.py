"""Sub-Agent Context Bridge.

Implements the Arize/Alyx pattern for sub-agent context management.
Allows an orchestrator agent to provision a sub-agent with a compressed
summary of its current state, while granting the sub-agent access to the
same CCR memory store so it can retrieve full context if needed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from cutctx.memory.ports import MemoryFilter

if TYPE_CHECKING:
    from cutctx.memory.core import HierarchicalMemory

logger = logging.getLogger(__name__)


@dataclass
class SubAgentBridge:
    """Bridge for managing context handoffs to sub-agents."""

    memory: HierarchicalMemory
    parent_session_id: str
    user_id: str

    async def provision_subagent(self, task: str, limit: int = 20) -> dict[str, Any]:
        """Generate a payload that the orchestrator can pass to the sub-agent.

        This fetches the most recent/important context from the parent session
        and packages it along with the CCR access scope.

        Args:
            task: The instruction for the sub-agent.
            limit: Maximum number of memories to include in the summary.

        Returns:
            A dictionary containing the task, context_summary, and ccr_scope.
        """
        # Fetch relevant context from the parent session
        memories = await self.memory.query(
            MemoryFilter(user_id=self.user_id, session_id=self.parent_session_id, limit=100)
        )

        # Sort by importance and time to get the most relevant
        memories.sort(key=lambda m: (m.importance, m.created_at.timestamp()), reverse=True)

        # Take the top N items for the distillation
        top_memories = memories[:limit]

        # Sort chronologically for the summary
        top_memories.sort(key=lambda m: m.created_at.timestamp())

        context_summary = "\n".join([f"- {m.content}" for m in top_memories])

        payload = {
            "task": task,
            "context_summary": context_summary,
            "ccr_scope": {"user_id": self.user_id, "session_id": self.parent_session_id},
        }

        if not memories:
            logger.warning(
                "No context found for session %s when provisioning sub-agent task: %s",
                self.parent_session_id,
                task,
            )
            payload["warning"] = (
                "No context found for this session. Sub-agent will start with zero context."
            )

        return payload

    async def merge_result(
        self, subagent_id: str, distilled_result: str, importance: float = 0.8
    ) -> None:
        """Merge the distilled sub-agent result back into the parent's memory.

        Args:
            subagent_id: Identifier for the sub-agent.
            distilled_result: The summarized result returned by the sub-agent.
            importance: The importance score to assign to this distilled memory.
        """
        if not subagent_id or not subagent_id.strip():
            raise ValueError("subagent_id must be a non-empty string")
        if not distilled_result or not distilled_result.strip():
            raise ValueError("distilled_result must be a non-empty string")
        if not 0.0 <= importance <= 1.0:
            raise ValueError("importance must be between 0.0 and 1.0")

        content = f"[Sub-Agent {subagent_id} Result]: {distilled_result}"

        await self.memory.add(
            content=content,
            user_id=self.user_id,
            session_id=self.parent_session_id,
            importance=importance,
            metadata={
                "source": "subagent_distillation",
                "subagent_id": subagent_id,
            },
        )
        logger.info(
            "Merged subagent %s result into session %s", subagent_id, self.parent_session_id
        )
