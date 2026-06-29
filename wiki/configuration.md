# Configuration

Cutctx can be configured via the SDK, proxy command line, or per-request overrides.

## SDK Configuration

```python
from cutctx import CutctxClient, OpenAIProvider
from openai import OpenAI

client = CutctxClient(
    original_client=OpenAI(),
    provider=OpenAIProvider(),

    # Mode: "audit" (observe only) or "optimize" (apply transforms)
    default_mode="optimize",

    # Enable provider-specific cache optimization
    enable_cache_optimizer=True,

    # Enable query-level semantic caching
    enable_semantic_cache=False,

    # Override default context limits per model
    model_context_limits={
        "gpt-4o": 128000,
        "gpt-4o-mini": 128000,
    },

    # Database location (defaults to temp directory)
    # store_url="sqlite:////absolute/path/to/cutctx.db",
)
```

## Proxy Configuration

### Command Line Options

```bash
cutctx proxy \
  --port 8787 \              # Port to listen on
  --host 0.0.0.0 \           # Host to bind to
  --budget 10.00 \           # Daily budget limit in USD
  --log-file cutctx.jsonl  # Log file path
```

### Feature Flags

```bash
# Disable optimization (passthrough mode)
cutctx proxy --no-optimize

# Disable semantic caching
cutctx proxy --no-cache

# Disable CCR response handling
cutctx proxy --no-ccr-responses

# Disable proactive expansion
cutctx proxy --no-ccr-expansion

# (The earlier --llmlingua flag was retired in 0.9.x and replaced by
# Kompress (ModernBERT). See `wiki/transforms.md` for the current
# opt-in path via the `[ml]` extra.)
```

### All Options

```bash
cutctx proxy --help
```

### Kompress backend selection

Kompress (the model-based compressor) can run on two engines:

- **ONNX Runtime** — lightweight, CPU-first. Installed with
  `pip install cutctx-ai[proxy]`. Optionally uses the CoreML execution
  provider on macOS.
- **PyTorch** — heavier, supports CUDA and Apple-Silicon MPS
  acceleration. Installed with `pip install cutctx-ai[ml]`. With
  `device=auto` it selects `cuda`, then `mps`, then `cpu`.

Select the backend via the `CUTCTX_KOMPRESS_BACKEND` environment
variable:

| Value               | Behavior                                                               |
|---------------------|------------------------------------------------------------------------|
| `auto`              | Default. ONNX CPU first (stable, lightweight), PyTorch as fallback.    |
| `onnx` / `onnx_cpu` | Force ONNX Runtime on CPU.                                             |
| `onnx_coreml`       | Force ONNX Runtime with the CoreML provider (CPU fallback).            |
| `pytorch`           | Force PyTorch with automatic device selection (CUDA → MPS → CPU).      |
| `pytorch_mps`       | Force PyTorch on Apple-Silicon MPS; falls back to ONNX CPU on failure. |

Values are case-insensitive and hyphens are accepted (`onnx-cpu` ==
`onnx_cpu`). Shorthand aliases: `cpu` → `onnx_cpu`, `coreml` →
`onnx_coreml`, `mps` / `torch_mps` → `pytorch_mps`, `torch` →
`pytorch`. Unrecognized values log a warning and fall back to `auto`.

Example — opt in to MPS on an Apple-Silicon machine:

```bash
export CUTCTX_KOMPRESS_BACKEND=mps
cutctx proxy ...
```

The default deliberately stays on ONNX CPU so existing installs keep
their compression quality and performance characteristics; accelerator
backends are opt-in.

## Per-Request Overrides

Override configuration for specific requests:

```python
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[...],

    # Override mode for this request
    cutctx_mode="audit",

    # Reserve more tokens for output
    cutctx_output_buffer_tokens=8000,

    # Keep last N turns (don't compress)
    cutctx_keep_turns=5,

    # Skip compression for specific tools
    cutctx_tool_profiles={
        "important_tool": {"skip_compression": True}
    }
)
```

## Modes

| Mode | Behavior | Use Case |
|------|----------|----------|
| `audit` | Observes and logs, no modifications | Production monitoring, baseline measurement |
| `optimize` | Applies safe, deterministic transforms | Production optimization |
| `simulate` | Returns plan without API call | Testing, cost estimation |

### Simulate Mode

Preview what would happen without making an API call:

```python
plan = client.chat.completions.simulate(
    model="gpt-4o",
    messages=large_conversation,
)

print(f"Would save {plan.tokens_saved} tokens")
print(f"Transforms: {plan.transforms}")
print(f"Estimated savings: {plan.estimated_savings}")
```

## SmartCrusher Configuration

Fine-tune JSON compression behavior:

```python
from cutctx.transforms import SmartCrusherConfig

config = SmartCrusherConfig(
    # Maximum items to keep after compression
    max_items_after_crush=15,

    # Minimum tokens before applying compression
    min_tokens_to_crush=200,

    # Relevance scoring tier: "bm25" (fast) or "embedding" (accurate)
    relevance_tier="bm25",

    # Always keep items with these field values
    preserve_fields=["error", "warning", "failure"],
)
```

## Cache Aligner Configuration

Control prefix stabilization:

```python
from cutctx.transforms import CacheAlignerConfig

config = CacheAlignerConfig(
    # Enable/disable cache alignment
    enabled=True,

    # Patterns to extract from system prompt
    dynamic_patterns=[
        r"Today is \w+ \d+, \d{4}",
        r"Current time: .*",
    ],
)
```

## Rolling Window Configuration

Control context window management:

```python
from cutctx.transforms import RollingWindowConfig

config = RollingWindowConfig(
    # Minimum turns to always keep
    min_keep_turns=3,

    # Reserve tokens for output
    output_buffer_tokens=4000,

    # Drop oldest tool outputs first
    prefer_drop_tool_outputs=True,
)
```



## Environment Variables

Some settings can be configured via environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `CUTCTX_MODEL_LIMITS` | Custom model config (JSON string or file path) | - |
| `CUTCTX_CONFIG_DIR` | Canonical config (read-mostly) root. Derives `models.json` and per-plugin config paths when set. | `~/.cutctx/config` |
| `CUTCTX_WORKSPACE_DIR` | Canonical workspace (read-write state) root. Derives savings ledger, memory DB, logs, TOIN, subscription state, and more when set. | `~/.cutctx` |
| `CUTCTX_SAVINGS_PATH` | Full path to the proxy savings JSON ledger. Always wins when set. | derived from `${CUTCTX_WORKSPACE_DIR}` |
| `CUTCTX_TOIN_PATH` | Full path to the TOIN telemetry JSON file. Always wins when set. | derived from `${CUTCTX_WORKSPACE_DIR}` |
| `CUTCTX_SUBSCRIPTION_STATE_PATH` | Full path to the subscription tracker state. Always wins when set. | derived from `${CUTCTX_WORKSPACE_DIR}` |
| `CUTCTX_EMBEDDER_RUNTIME` | Set to `pytorch_mps` to run the memory embedder via the torch sentence-transformers backend on the Apple GPU (MPS). Only engages when Apple MPS is actually available; otherwise it logs a warning and uses the existing default embedder selection path. `pytorch_mps` is the only accepted value. Requires the `[pytorch-mps]` extra. See [Memory](memory.md#embedding-runtime--gpu-offload-apple-silicon). | default embedder selection |

## Filesystem Contract

Cutctx resolves every on-disk resource through a two-root model:

- `CUTCTX_CONFIG_DIR` (default `~/.cutctx/config`) — read-mostly
  configuration
- `CUTCTX_WORKSPACE_DIR` (default `~/.cutctx`) — read-write state

Precedence for each resource is: explicit argument > per-resource env
var > derived from canonical root > default. Every legacy env var
continues to work unchanged.

See **[Filesystem Contract](filesystem-contract.md)** for the full
bucket table, plugin-author guidance, and the Docker naming overlap
note (`CUTCTX_WORKSPACE` is *not* the same as `CUTCTX_WORKSPACE_DIR`).

---

## Custom Model Configuration

Configure context limits and pricing for new or custom models. Useful when:
- A new model is released before Cutctx is updated
- You're using fine-tuned or custom models
- You want to override built-in limits

### Configuration Methods

Settings are resolved in this order (later overrides earlier):
1. Built-in defaults
2. `${CUTCTX_CONFIG_DIR}/models.json` (defaults to
   `~/.cutctx/config/models.json`); falls back to the legacy location
   `~/.cutctx/models.json` when the canonical file is absent
3. `CUTCTX_MODEL_LIMITS` environment variable
4. SDK constructor arguments

### Config File Format

Create `~/.cutctx/models.json`:

```json
{
  "anthropic": {
    "context_limits": {
      "claude-4-opus-20250301": 200000,
      "claude-custom-finetune": 128000
    },
    "pricing": {
      "claude-4-opus-20250301": {
        "input": 15.00,
        "output": 75.00,
        "cached_input": 1.50
      }
    }
  },
  "openai": {
    "context_limits": {
      "gpt-5": 256000,
      "ft:gpt-4o:my-org": 128000
    },
    "pricing": {
      "gpt-5": [5.00, 15.00]
    }
  }
}
```

### Environment Variable

Set `CUTCTX_MODEL_LIMITS` as a JSON string or file path:

```bash
# JSON string
export CUTCTX_MODEL_LIMITS='{"anthropic":{"context_limits":{"claude-new":200000}}}'

# File path
export CUTCTX_MODEL_LIMITS=/path/to/models.json
```

### Pattern-Based Inference

Unknown models are automatically inferred from naming patterns:

| Pattern | Inferred Settings |
|---------|-------------------|
| `*opus*` | 200K context, Opus-tier pricing |
| `*sonnet*` | 200K context, Sonnet-tier pricing |
| `*haiku*` | 200K context, Haiku-tier pricing |
| `gpt-4o*` | 128K context, GPT-4o pricing |
| `o1*`, `o3*` | 200K context, reasoning model pricing |

This means new models like `claude-4-sonnet-20251201` will work automatically with Sonnet-tier defaults.

### SDK Override

Override in code for specific models:

```python
from cutctx import CutctxClient, AnthropicProvider

client = CutctxClient(
    original_client=Anthropic(),
    provider=AnthropicProvider(
        context_limits={
            "claude-new-model": 300000,
        }
    ),
)
```

## Provider-Specific Settings

### OpenAI

```python
from cutctx import OpenAIProvider

provider = OpenAIProvider(
    # Enable automatic prefix caching
    enable_prefix_caching=True,
)
```

### Anthropic

```python
from cutctx import AnthropicProvider

provider = AnthropicProvider(
    # Enable cache_control blocks
    enable_cache_control=True,
)
```

### Google

```python
from cutctx import GoogleProvider

provider = GoogleProvider(
    # Enable context caching
    enable_context_caching=True,
)
```

## Configuration Precedence

Settings are applied in this order (later overrides earlier):

1. Default values
2. Environment variables
3. SDK constructor arguments
4. Per-request overrides

## Validation

Validate your configuration:

```python
result = client.validate_setup()

if not result["valid"]:
    print("Configuration issues:")
    for issue in result["issues"]:
        print(f"  - {issue}")
```

---

## TypeScript SDK Configuration

The TypeScript SDK is configured via environment variables or constructor options.

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CUTCTX_BASE_URL` | Base URL of the Cutctx proxy or cloud API | `http://localhost:8787` |
| `CUTCTX_API_KEY` | API key for Cutctx Cloud authentication | - |

### Usage

```bash
export CUTCTX_BASE_URL=http://localhost:8787
export CUTCTX_API_KEY=your-api-key
```

```typescript
import { CutctxClient } from 'cutctx-ai';

// Reads from CUTCTX_BASE_URL and CUTCTX_API_KEY automatically
const client = new CutctxClient();

// Or configure explicitly
const client = new CutctxClient({
  baseUrl: 'http://localhost:8787',
  apiKey: 'your-api-key',
});
```

See the [TypeScript SDK Guide](typescript-sdk.md) for full configuration options.
