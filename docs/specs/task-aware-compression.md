# Task-Aware Compression

## Problem Statement

Current compression in Cutctx routes content by **type** (JSON → SmartCrusher, code → AST, prose → Kompress). This type-based approach is agnostic to what the agent is actually trying to accomplish. 

For example, when debugging an HTTP error, file system tool outputs are irrelevant and should be crushed aggressively, while HTTP responses should be preserved with minimal compression. Today, both get treated the same because they're both JSON.

Task-aware compression uses the current working task (extracted from recent user messages) to modulate compression rate per content segment. Segments matching the task get minimal compression; irrelevant segments get aggressive compression.

## Motivation

- **Higher context efficiency:** Preserve signal, crush noise
- **Better agent performance:** Keep relevant details even when token budgets are tight
- **Graceful fallback:** If no task is detectable, behave identically to UniversalCompressor
- **Minimal overhead:** Task extraction and relevance scoring are fast (no GPU required)

## User Stories

### Story 1: Debugging HTTP Errors
As an agent debugging a 500 error in production, I want HTTP response bodies preserved while filesystem tool outputs are crushed, so my context stays focused on the actual problem.

**Scenario:** Tool returns both error logs (relevant) and system info dumps (irrelevant). Task-aware compression crushes the system info from 5000 tokens to 500 while keeping error logs intact.

### Story 2: Code Navigation
As a code analysis agent, I want function signatures and imports preserved while verbose docstrings and comments are compressed, so I can understand code structure quickly.

**Scenario:** Large Python file with detailed docstrings. Task is "find the database connection function". Compressed output preserves function signatures and imports, crushes docstrings by 70%.

### Story 3: Document Review
As a document summarization agent, I want the document body preserved but metadata (file sizes, timestamps) crushed, so the summary stays accurate.

**Scenario:** 50-page PDF converted to text with metadata. Task is "summarize the findings". Findings section gets minimal compression; metadata and formatting cruft get 90% compression.

### Story 4: No Task Extraction Fallback
As an agent in an ambiguous context, if no task can be extracted, compression should work exactly as before, with no quality loss or new failure modes.

**Scenario:** User sends a confused message like "hi". Task extractor returns None. Behavior is identical to UniversalCompressor—content type routing only, no task-based modulation.

## Technical Design

### Task Extraction

**Input:** Last 3 user messages (message objects with `role` and `content` fields)

**Heuristics** (in order of priority):
1. Look for imperative verbs: "debug", "fix", "implement", "find", "analyze", "review", "summarize", "compare"
2. Look for question words: "what", "how", "where", "why", "which"
3. Look for "fix" or "debug" anywhere in the message
4. Extract the first sentence (typically the task description)
5. If nothing matches, return None

**Output:** Brief string (40-100 chars) describing the task, or None if no task is detectable

**Example:**
```
User: "I'm getting a 500 error when I call /api/users. Can you help debug this?"
Task: "debug API 500 error"

User: "Find all instances of SQL injection in the code"
Task: "find SQL injection instances"

User: "hi"
Task: None (no detectable task)
```

### Relevance Scoring

**Input:** 
- Content chunk (string, any length)
- Task (string, brief)

**Output:** Float [0.0, 1.0] indicating relevance

**Algorithm:**
1. Use BM25 (fast, zero GPU, already available in cutctx.relevance) as primary scorer
2. Fall back to simple keyword overlap if BM25 unavailable
3. Score = number of overlapping terms / max(task_terms, content_terms)

**Characteristics:**
- Fast: <1ms per chunk
- No neural network required
- Handles acronyms well ("API" in task matches "API" in content)
- Degrades gracefully for very short tasks

### Compression Rate Modulation

**Relevance score mapping to compression aggressiveness:**

| Relevance | Compression Strategy | Behavior |
|-----------|----------------------|----------|
| >= 0.7 | Minimal (CacheAligner only) | Preserve all structure and content |
| 0.3-0.7 | Normal (type-based routing) | Use UniversalCompressor as-is |
| < 0.3 | Aggressive (max ratio) | Compress tokens by 90%+ |

**Integration point:** TaskAwareCompressor wraps UniversalCompressor and adds a relevance pre-pass.

### Integration with UniversalCompressor

```python
class TaskAwareCompressor:
    def __init__(self, task: str | None = None):
        self.task = task
        self.universal = UniversalCompressor()
        self.relevance_scorer = BM25Scorer()
    
    def compress(self, content: str, content_type: str | None = None) -> TaskAwareResult:
        # 1. Compute relevance (0.0-1.0) if task available
        relevance = 1.0  # Default: fully relevant (no modulation)
        if self.task:
            relevance = self.relevance_scorer.score(content, self.task).score
        
        # 2. Modulate compression_ratio_target based on relevance
        if relevance >= 0.7:
            # Minimal compression: CacheAligner only
            config = UniversalCompressorConfig(
                compression_ratio_target=0.95,  # Keep 95%
                use_kompress=False,  # Disable ML compression
            )
        elif relevance >= 0.3:
            # Normal compression: use defaults
            config = UniversalCompressorConfig()
        else:
            # Aggressive compression
            config = UniversalCompressorConfig(
                compression_ratio_target=0.1,  # Keep only 10%
            )
        
        # 3. Call UniversalCompressor with modulated config
        universal_with_config = UniversalCompressor(config=config)
        result = universal_with_config.compress(content, content_type)
        
        # 4. Wrap result in TaskAwareResult
        return TaskAwareResult(
            compressed=result.compressed,
            original_tokens=result.tokens_before,
            compressed_tokens=result.tokens_after,
            relevance_score=relevance,
            task_used=self.task,
        )
```

## API

### TaskExtractor

```python
class TaskExtractor:
    @staticmethod
    def extract_task(messages: list[dict]) -> str | None:
        """Extract working task from last 3 user messages.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
        
        Returns:
            Brief task string (40-100 chars) or None if not detectable
        """
```

### RelevanceModulator

```python
class RelevanceModulator:
    def score(self, content: str, task: str) -> float:
        """Score content relevance to task.
        
        Args:
            content: Content chunk to score
            task: Task string
        
        Returns:
            Relevance [0.0, 1.0]
        """
```

### TaskAwareCompressor

```python
class TaskAwareCompressor:
    def __init__(
        self, 
        task: str | None = None,
        relevance_threshold: float = 0.3,
    ):
        """Initialize task-aware compressor.
        
        Args:
            task: Current working task, or None
            relevance_threshold: Minimum relevance before minimal compression (default 0.3)
        """
    
    def compress(
        self, 
        content: str, 
        content_type: str | None = None,
    ) -> TaskAwareResult:
        """Compress content with task-aware modulation.
        
        Args:
            content: Content to compress
            content_type: MIME type (optional)
        
        Returns:
            TaskAwareResult with compressed content and metrics
        """
    
    def set_task(self, task: str | None) -> None:
        """Update task mid-session."""
```

### TaskAwareResult

```python
@dataclass
class TaskAwareResult:
    compressed: str
    original_tokens: int
    compressed_tokens: int
    relevance_score: float  # [0.0, 1.0]
    task_used: str | None
```

## Success Metrics

1. **Quality Retention:** <1% accuracy drop vs. uncompressed on agent success metrics
   - Measure: Run existing agent evals with task-aware compression vs. baseline
   - Threshold: Agent success rate within 1 percentage point

2. **Compression on Irrelevant Content:** >85% compression ratio on content scoring < 0.3 relevance
   - Measure: Sample tool outputs, measure compression on low-relevance chunks
   - Threshold: >85% of tokens removed

3. **No Regression on Relevant Content:** >90% tokens preserved on content scoring > 0.7 relevance
   - Measure: Sample relevant tool outputs
   - Threshold: >90% tokens retained

## Fallback Behavior

If no task is extractable (returns None), TaskAwareCompressor behaves identically to UniversalCompressor:
- Content type detection: enabled
- Structure preservation: enabled
- ML compression (Kompress): enabled
- No task-based modulation applied

This ensures zero new failure modes if task extraction fails or returns None.

## Implementation Notes

- **No GPU required:** BM25 scorer is pure Python, no neural networks
- **Fast path:** Task extraction uses regex patterns, not ML
- **Graceful degradation:** Falls back to BM25 keyword overlap if BM25 scorer unavailable
- **Backward compatible:** When task is None, behaves exactly like UniversalCompressor
