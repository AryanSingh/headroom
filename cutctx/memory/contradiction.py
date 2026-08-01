"""Contradiction detection helpers for hierarchical memory.

Deterministic (CI-safe) classifier plus hooks for an optional injectable
LLM classifier. Used by ``HierarchicalMemory.add`` when
``MemoryConfig.contradiction_detection`` is enabled.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from enum import Enum

from cutctx.memory.models import Memory

ContradictionClassifier = Callable[[str, str, list[str]], "ContradictionVerdict"]


class ContradictionVerdict(Enum):
    INDEPENDENT = "independent"
    REFINE = "refine"
    CONTRADICT = "contradict"


_EXCLUSIVE_PREDICATES = (
    "was born in",
    "is married to",
)
_EXCLUSIVE_PREDICATE_PATTERN = re.compile(
    rf"^(?P<subject>.+?)\s+(?P<predicate>{'|'.join(_EXCLUSIVE_PREDICATES)})\s+(?P<object>.+)$",
    re.IGNORECASE,
)


def _normalize_entities(entities: Iterable[str]) -> set[str]:
    return {e.strip().lower() for e in entities if e and e.strip()}


def find_contradiction_candidates(
    new_memory: Memory,
    existing: Iterable[Memory],
) -> list[Memory]:
    """Return active memories sharing at least one entity with ``new_memory``.

    Requires explicit ``entity_refs`` on the new memory so free-text saves
    without entities do not trigger silent supersession.
    """
    new_entities = _normalize_entities(new_memory.entity_refs)
    if not new_entities:
        return []

    found: list[Memory] = []
    for mem in existing:
        if not mem.is_current:
            continue
        if mem.user_id != new_memory.user_id:
            continue
        shared = _normalize_entities(mem.entity_refs) & new_entities
        if shared:
            found.append(mem)
    return found


def classify_pair(
    old_content: str,
    new_content: str,
    shared_entities: list[str],
) -> ContradictionVerdict:
    """Deterministic classifier for contradiction / refine / independent.

    Rules (conservative to avoid silent data loss):
    - No shared entities → INDEPENDENT
    - Identical text → REFINE (idempotent update)
    - New properly extends old (old substring of new) → REFINE
    - New narrows old (new proper substring of old) → INDEPENDENT
    - A small explicit table of exclusive predicates with a changed object → CONTRADICT
    - Shared entity without an unambiguous exclusive predicate → INDEPENDENT
    """
    if not shared_entities:
        return ContradictionVerdict.INDEPENDENT

    old_l = old_content.strip().lower()
    new_l = new_content.strip().lower()

    if not old_l or not new_l:
        return ContradictionVerdict.INDEPENDENT

    if old_l == new_l:
        return ContradictionVerdict.REFINE

    # Extension only: old is contained in new (richer update).
    if old_l in new_l and new_l != old_l:
        return ContradictionVerdict.REFINE

    # Only predicates explicitly known to be exclusive are eligible for
    # supersession.  Facts such as owning several things, liking several
    # things, or working on several projects commonly coexist.
    old_role = _EXCLUSIVE_PREDICATE_PATTERN.fullmatch(old_l)
    new_role = _EXCLUSIVE_PREDICATE_PATTERN.fullmatch(new_l)
    if old_role and new_role:
        same_subject = old_role.group("subject").strip() == new_role.group("subject").strip()
        same_predicate = old_role.group("predicate").lower() == new_role.group("predicate").lower()
        old_obj = old_role.group("object").strip()
        new_obj = new_role.group("object").strip()
        if same_subject and same_predicate and old_obj != new_obj:
            return ContradictionVerdict.CONTRADICT
        if same_subject and same_predicate and old_obj == new_obj:
            return ContradictionVerdict.REFINE

    # Shared entities without a clear role conflict → leave both current.
    return ContradictionVerdict.INDEPENDENT


def shared_entity_names(a: Memory, b: Memory) -> list[str]:
    shared = _normalize_entities(a.entity_refs) & _normalize_entities(b.entity_refs)
    return sorted(shared)
