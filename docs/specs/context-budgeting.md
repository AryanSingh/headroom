# Context Budget Controller: Progressive Compression for Long Agent Sessions

## Problem Statement

Long-running agent sessions hit context limits unexpectedly, causing crashes or truncation. Current approach in `proxy/budget.py` terminates streams when token budget is exhausted — a hard wall that leaves no graceful recovery path.

Instead, we need **progressive compression**: as the session fills up, older context gets compressed more aggressively to make room for new context. The agent never hits the wall; it degrades gracefully.

Additionally, agents need **cost forecasting** to understand their spending trajectory: "based on current token velocity, this task will cost ~$0.85 with Headroom."

## User Stories

### 1. Agent Avoids Context Limit Hard Fail
As a long-running agent, I want my session to stay alive when approaching context limits, even if older messages get heavily compressed, so I can continue making progress instead of crashing.

**Acceptance Criteria:**
- Agent detects entering YELLOW zone (60% of budget) and applies light compression to messages older than the last 10
- Agent detects entering RED zone (80% of budget) and applies aggressive compression to messages older than the last 5
- Agent detects entering CRITICAL zone (95% of budget) and summarizes oldest 20% of context
- Agent never hard-fails on context limit; graceful degradation is guaranteed

### 2. Cost Forecasting for Budget Planning
As an agent operator, I want to forecast the total cost of a task before it runs, so I can allocate budgets and avoid surprises.

**Acceptance Criteria:**
- `forecast()` method projects total cost based on current token velocity
- Forecast confidence increases as session accumulates data (early forecasts are ~50% accurate, settled forecasts <15% variance)
- Cost is broken down per-model and per-provider when multiple models are used

### 3. Policy-Driven Compression Levels
As an operator, I want to choose compression aggressiveness (conservative, balanced, aggressive) via environment variables, so different workloads get tailored strategies.

**Acceptance Criteria:**
- HEADROOM_BUDGET_POLICY env var controls zone thresholds and compression window sizes
- conservative = wider zones, later compression (keep more context)
- balanced = default, proven good for most agents (default)
- aggressive = tight zones, early compression (maximize budget longevity)

### 4. Session-Level Status and Observability
As an agent, I want to know my current budget zone, compression applied, and forecast so I can surface warnings or adapt behavior.

**Acceptance Criteria:**
- `status` property exposes current zone, tokens used/available, compression applied, and forecast_usd
- All metrics update as messages are processed
- Dashboard/logs show zone transitions for debugging

## Technical Design

### Budget Zones

Four zones define when and how aggressively to compress:

| Zone | Range | Compression Strategy |
|------|-------|----------------------|
| GREEN | 0-60% | No compression; passthrough |
| YELLOW | 60-80% | Light: compress messages older than last 10; aggressiveness 0.5 |
| RED | 80-95% | Aggressive: compress messages older than last 5; aggressiveness 0.8 |
| CRITICAL | 95%+ | Emergency: summarize oldest 20% of context; aggressiveness 1.0 |

### Progressive Compression Algorithm

```python
def apply(messages: list[dict]) -> list[dict]:
    """Apply progressive compression based on budget zone."""
    token_count = _count_tokens(messages)
    zone = _get_zone(token_count)
    
    if zone == BudgetZone.GREEN:
        return messages  # No compression
    
    elif zone == BudgetZone.YELLOW:
        # Compress old messages (keep recent)
        cutoff_index = len(messages) - self.policy.compression_window_yellow
        old_messages = messages[:cutoff_index]
        recent = messages[cutoff_index:]
        compressed = self._compress_old_messages(old_messages, aggressiveness=0.5)
        return compressed + recent
    
    elif zone == BudgetZone.RED:
        # Compress older messages more aggressively
        cutoff_index = len(messages) - self.policy.compression_window_red
        old_messages = messages[:cutoff_index]
        recent = messages[cutoff_index:]
        compressed = self._compress_old_messages(old_messages, aggressiveness=0.8)
        return compressed + recent
    
    elif zone == BudgetZone.CRITICAL:
        # Summarize oldest 20% of context
        cutoff_index = len(messages) // 5  # Oldest 20%
        to_summarize = messages[:cutoff_index]
        keep = messages[cutoff_index:]
        
        # Call headroom.compress with aggressive settings
        summary = self._summarize(to_summarize)
        return [summary] + keep
```

### Configuration via Environment Variables

Zone thresholds and compression windows are configurable:

```bash
# Conservative (keep more context, compress later)
HEADROOM_BUDGET_POLICY=conservative
HEADROOM_BUDGET_GREEN=0.70      # 0-70%
HEADROOM_BUDGET_YELLOW=0.85     # 70-85%
HEADROOM_BUDGET_RED=0.95        # 85-95%
HEADROOM_BUDGET_WINDOW_YELLOW=15  # Protect last 15 messages
HEADROOM_BUDGET_WINDOW_RED=8       # Protect last 8 messages

# Balanced (default)
HEADROOM_BUDGET_POLICY=balanced
HEADROOM_BUDGET_GREEN=0.60
HEADROOM_BUDGET_YELLOW=0.80
HEADROOM_BUDGET_RED=0.95
HEADROOM_BUDGET_WINDOW_YELLOW=10
HEADROOM_BUDGET_WINDOW_RED=5

# Aggressive (maximize budget life, compress early)
HEADROOM_BUDGET_POLICY=aggressive
HEADROOM_BUDGET_GREEN=0.50
HEADROOM_BUDGET_YELLOW=0.75
HEADROOM_BUDGET_RED=0.90
HEADROOM_BUDGET_WINDOW_YELLOW=5
HEADROOM_BUDGET_WINDOW_RED=3
```

### Cost Forecasting

Cost forecast is based on token velocity (average tokens/message):

```python
def forecast(messages: list[dict]) -> dict:
    """Project total cost without applying compression."""
    token_count = _count_tokens(messages)
    velocity = token_count / len(messages) if messages else 0
    
    # Project to budget exhaustion
    tokens_available = self.max_tokens - token_count
    estimated_messages_remaining = tokens_available / velocity
    
    # Cost per 1M tokens from pricing data
    cost_per_token = _get_model_cost_per_token(self.model)
    
    # Forecast: current cost + projected cost
    current_cost = token_count * cost_per_token
    projected_cost = tokens_available * cost_per_token
    total_forecast = current_cost + projected_cost
    
    return {
        "token_velocity": velocity,
        "tokens_available": tokens_available,
        "estimated_messages_remaining": estimated_messages_remaining,
        "forecast_usd": total_forecast,
        "confidence_pct": min(100, len(messages) * 10),  # 10% per message up to 100%
        "breakdown_by_model": {...}
    }
```

### API Design

#### ContextBudgetController

```python
class ContextBudgetController:
    def __init__(
        self,
        max_tokens: int = 100_000,
        model: str = "claude-sonnet-4-6",
        policy: str = "balanced"
    ):
        """Initialize budget controller with max tokens and policy.
        
        Args:
            max_tokens: Token budget per session
            model: Model name for cost estimation
            policy: 'conservative', 'balanced', or 'aggressive'
        """
        self.max_tokens = max_tokens
        self.model = model
        self.policy = BudgetPolicy.from_env(policy)
        self._tokens_used = 0
        self._compression_applied = False
    
    def apply(self, messages: list[dict]) -> list[dict]:
        """Apply progressive compression if needed, return adjusted messages.
        
        Returns messages with compression applied progressively based on zone.
        Messages stay in place but some are compressed to save tokens.
        """
    
    @property
    def status(self) -> BudgetStatus:
        """Current budget status: zone, tokens, forecast."""
    
    def forecast(self, messages: list[dict]) -> dict:
        """Forecast total cost based on current velocity."""
    
    def _count_tokens(self, messages: list[dict]) -> int:
        """Use tiktoken or headroom's token counter."""
    
    def _compress_old_messages(
        self,
        messages: list[dict],
        aggressiveness: float = 0.5
    ) -> list[dict]:
        """Apply headroom compress to messages, scaling aggressiveness."""
    
    def _get_zone(self, tokens_used: int) -> BudgetZone:
        """Determine current zone from token usage."""
    
    def _summarize(self, messages: list[dict]) -> dict:
        """Summarize oldest messages (use for CRITICAL zone)."""
```

#### BudgetStatus

```python
@dataclass
class BudgetStatus:
    zone: BudgetZone
    tokens_used: int
    tokens_budget: int
    tokens_available: int
    percent_used: float
    compression_applied: bool
    forecast_usd: float
```

#### BudgetPolicy

```python
@dataclass
class BudgetPolicy:
    green_threshold: float = 0.60      # 0-60% is GREEN
    yellow_threshold: float = 0.80     # 60-80% is YELLOW
    red_threshold: float = 0.95        # 80-95% is RED
    compression_window_yellow: int = 10  # Protect last 10 messages
    compression_window_red: int = 5       # Protect last 5 messages
    
    @classmethod
    def from_env(cls, policy: str = "balanced") -> BudgetPolicy:
        """Load policy from environment, falling back to named preset."""
        import os
        return cls(
            green_threshold=float(os.getenv("HEADROOM_BUDGET_GREEN", "0.60")),
            yellow_threshold=float(os.getenv("HEADROOM_BUDGET_YELLOW", "0.80")),
            red_threshold=float(os.getenv("HEADROOM_BUDGET_RED", "0.95")),
            compression_window_yellow=int(os.getenv("HEADROOM_BUDGET_WINDOW_YELLOW", "10")),
            compression_window_red=int(os.getenv("HEADROOM_BUDGET_WINDOW_RED", "5")),
        )
```

## Success Metrics

1. **No Hard Failures**: Agent sessions never hit context-limit wall; compression keeps them alive
2. **Cost Accuracy**: Forecast vs. actual cost variance < 15% for typical sessions
3. **Performance**: Compression overhead < 5% latency impact per compression
4. **Observability**: Zone transitions logged; dashboard shows budget status over time

## Integration Points

- `compress.py`: Use existing `compress()` function with CompressConfig
- `cost.py`: Leverage CostTracker for pricing data
- `savings_tracker.py`: Record compression applied due to budget pressure
- Proxy request handler: Call `apply()` on inbound message stream before model
