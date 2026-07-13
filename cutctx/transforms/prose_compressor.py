"""Conservative query-aware compression for prose and RAG excerpts."""

from __future__ import annotations

import re
from dataclasses import dataclass

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z`])")
_WORD = re.compile(r"[A-Za-z0-9_./:-]+")
_EXACT_ANCHOR = re.compile(
    r"`[^`]+`|\b[A-Z][A-Z0-9_]{3,}\b|"
    r"\b[A-Za-z_][A-Za-z0-9_]*\.(?:jsonl?|ya?ml|toml|py|ts|js)\b"
)
_CONSTRAINT_ANCHOR = re.compile(
    r"(?:\b(?:interval|limit|timeout|ttl|retries|retry count|retain(?:ed|s|tion)?)\b"
    r"[^.!?]*\b\d+(?:\.\d+)?\b|"
    r"\b\d+(?:\.\d+)?\b[^.!?]*"
    r"\b(?:interval|limit|timeout|ttl|retries|retry count|retain(?:ed|s|tion)?)\b)",
    re.IGNORECASE,
)
_STOP = {
    "a",
    "an",
    "and",
    "are",
    "for",
    "from",
    "how",
    "is",
    "of",
    "the",
    "to",
    "what",
    "when",
    "which",
    "who",
    "why",
}
_GIT_COMMIT_START = re.compile(r"(?m)^commit \S+(?:\s|$)")


@dataclass(frozen=True)
class ProseCompressionResult:
    compressed: str
    original: str
    original_sentences: int
    retained_sentences: int
    compression_ratio: float


def _terms(text: str) -> set[str]:
    terms: set[str] = set()
    for token in _WORD.findall(text):
        normalized = token.lower()
        if len(normalized) <= 2 or normalized in _STOP:
            continue
        if normalized.endswith("ies") and len(normalized) > 4:
            normalized = normalized[:-3] + "y"
        elif normalized.endswith("es") and len(normalized) > 4:
            normalized = normalized[:-2]
        elif normalized.endswith("s") and len(normalized) > 3:
            normalized = normalized[:-1]
        terms.add(normalized)
    return terms


class QueryAwareProseCompressor:
    """Select query-relevant sentences while retaining operational anchors.

    It intentionally declines when there is no query, the document is too
    small, or selection cannot save at least ten percent. Exact identifiers,
    paths, environment variables, and time/count constraints are retained even
    when they are not query-relevant so compressed runbooks remain actionable.
    """

    def compress(
        self, content: str, context: str = "", *, aggressive: bool = False
    ) -> ProseCompressionResult:
        """Select useful prose sentences.

        The default is deliberately conservative: without a relevant query it
        leaves text untouched.  The aggressive router mode may opt into a
        deterministic fallback when an ML compressor is unavailable.  That
        fallback retains headings, exact identifiers, numerical constraints,
        and one representative sentence rather than silently reporting an
        aggressive route that made no reduction.
        """
        query_terms = _terms(context)
        git_log_result = self._compress_git_log(content, query_terms)
        if git_log_result is not None:
            return git_log_result
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", content) if part.strip()]
        units: list[tuple[str, bool]] = []
        for paragraph in paragraphs:
            lines = paragraph.splitlines()
            if lines and lines[0].lstrip().startswith("#"):
                units.append((lines[0].strip(), True))
                paragraph = " ".join(line.strip() for line in lines[1:] if line.strip())
            else:
                paragraph = " ".join(line.strip() for line in lines if line.strip())
            units.extend(
                (sentence.strip(), False)
                for sentence in _SENTENCE_BOUNDARY.split(paragraph)
                if sentence.strip()
            )

        sentence_count = sum(not heading for _, heading in units)
        if sentence_count < 4 or (not query_terms and not aggressive):
            return self._unchanged(content, sentence_count)

        scored: list[tuple[int, int]] = []
        keep: set[int] = set()
        for index, (unit, heading) in enumerate(units):
            if heading:
                keep.add(index)
                continue
            overlap = len(_terms(unit) & query_terms)
            scored.append((overlap, index))
            if _EXACT_ANCHOR.search(unit) or _CONSTRAINT_ANCHOR.search(unit):
                keep.add(index)

        # Always retain the strongest query match. Operational identifiers and
        # constraints provide supporting context through the anchor path above.
        for overlap, index in sorted(scored, reverse=True)[:1]:
            if overlap > 0:
                keep.add(index)
        has_query_match = any(overlap > 0 for overlap, _ in scored)
        if not has_query_match and not aggressive:
            return self._unchanged(content, sentence_count)

        if aggressive and not has_query_match:
            # No semantic query signal is available. Preserve a representative
            # lead sentence in addition to format/operational anchors so the
            # result remains intelligible and useful for retrieval.
            first_sentence = next(
                (index for index, (_, heading) in enumerate(units) if not heading), None
            )
            if first_sentence is not None:
                keep.add(first_sentence)

        selected = [unit for index, (unit, _) in enumerate(units) if index in keep]
        compressed = "\n\n".join(selected)
        ratio = len(compressed) / max(len(content), 1)
        if ratio >= 0.90:
            return self._unchanged(content, sentence_count)
        return ProseCompressionResult(
            compressed=compressed,
            original=content,
            original_sentences=sentence_count,
            retained_sentences=sum(not units[index][1] for index in keep),
            compression_ratio=ratio,
        )

    def _compress_git_log(
        self, content: str, query_terms: set[str]
    ) -> ProseCompressionResult | None:
        """Select the relevant commit while preserving its attribution.

        A git log is line-oriented metadata, not ordinary prose. Selecting
        only the subject can discard the ``Author:`` line that answers common
        audit and incident questions, so retain the entire matching commit.
        """
        starts = list(_GIT_COMMIT_START.finditer(content))
        if not query_terms or len(starts) < 2 or "\nAuthor:" not in content:
            return None

        commits = [
            content[
                start.start() : starts[index + 1].start()
                if index + 1 < len(starts)
                else len(content)
            ].strip()
            for index, start in enumerate(starts)
        ]
        scored = [
            (len(_terms(commit) & query_terms), index) for index, commit in enumerate(commits)
        ]
        best_score, best_index = max(scored)
        if best_score <= 0:
            return self._unchanged(content, len(commits))

        compressed = commits[best_index]
        ratio = len(compressed) / max(len(content), 1)
        if ratio >= 0.90:
            return self._unchanged(content, len(commits))
        return ProseCompressionResult(
            compressed=compressed,
            original=content,
            original_sentences=len(commits),
            retained_sentences=1,
            compression_ratio=ratio,
        )

    @staticmethod
    def _unchanged(content: str, sentence_count: int) -> ProseCompressionResult:
        return ProseCompressionResult(
            compressed=content,
            original=content,
            original_sentences=sentence_count,
            retained_sentences=sentence_count,
            compression_ratio=1.0,
        )
