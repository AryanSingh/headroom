# Smart Coding Model Orchestrator: Product & Architecture Spec

## 1. Goal Description

Build a **Smart Coding Model Orchestrator** feature within the `cutctx` ecosystem. It will act as an intelligent, OpenAI-compatible proxy specialized for AI coding agents (like Cline, Aider, Roo Code, and OpenHands). By dynamically routing tasks to the optimal model (local vs. cloud) based on task complexity, the system will reduce API token costs substantially while maintaining or improving output quality.

This system will extend the existing `cutctx` proxy infrastructure (specifically `cutctx.proxy`) from a context-reducer to a full-fledged intelligent model gateway.

---

## 2. Strategic Value & Use Cases

- **Cost Optimization**: Stop burning expensive Claude 3.5 Sonnet tokens on trivial syntax fixes, linting errors, or simple type-hint additions.
- **Privacy/Local First**: Ensure simple, sensitive code stays on local machines using models like Llama 3 8B or DeepSeek Coder via Ollama.
- **Seamless Integration**: Because it operates at the proxy layer, developers don't need to change how they use their coding agents. They simply point the agent to the `cutctx` proxy endpoint.

---

## 3. Core Architecture

The system intercepts the `POST /v1/chat/completions` request.

### 3.1 The Pipeline
1. **Interceptor**: Catches the OpenAI-compatible request from the coding agent inside `cutctx.proxy.server`.
2. **Analyzer & Estimator**: Evaluates the `messages` array, estimates token count, and assigns a `Complexity Score (1-10)`.
3. **LiteLLM Router & Executor**: Rather than reinventing the wheel, we will leverage our existing `litellm` dependency to handle the actual routing and execution. We will configure LiteLLM's `Router` class dynamically based on the complexity score, allowing it to seamlessly handle load balancing, fallbacks, and connection pooling to the chosen backend provider.
4. **Ledger**: Records transaction cost, latency, and the specific model used into `spend_ledger.db`.

### 3.2 Complexity Classifier (The "Brain")
The hardest part of the system is the classifier. If a complex task is mistakenly routed to a weak local model, the agent will write bad code.

**Phase 1: Heuristic Engine (Recommended)**
- **Prompt Size**: Small diffs and short prompts (`< 500` characters) correlate strongly with low complexity.
- **Regex Patterns**: Detect simple instructions (e.g., `r"fix typo"`, `r"add docstring"`, `r"format code"`).
- **System Prompt Analysis**: Different agents (Cline vs Aider) have distinct signatures. We can parse their standard formats.

**Phase 2: ML Classifier (Future)**
- Use a local, quantized DistilBERT or similar fast-embedding model to classify the intent of the coding task.

---

## 4. Implementation Plan & File Modifications

All changes will be isolated within the `cutctx/cutctx/` codebase.

### Phase 1: Foundation & Classification
1. **Create `cutctx/orchestrator/` directory**
   - **`classifier.py`**: Implement `def classify_task_complexity(messages: list[dict]) -> TaskComplexity`. Start with the Heuristic Engine.
   - **`cache.py`**: Semantic and exact-match caching for agent prompts (extending `cutctx/proxy/semantic_cache.py`).
2. **Integrate LiteLLM for Routing (`cutctx/proxy/model_router.py`)**
   - Map our `TaskComplexity` enum directly into LiteLLM's configuration.
   - Use LiteLLM's built-in fallback and health-check mechanisms for local inference servers (e.g., Ollama) instead of building custom health probes.

### Phase 2: Gateway Integration
1. **Modify `cutctx/proxy/server.py`**
   - Inject the `classifier` logic into the `chat_completions` request handler.
   - Buffer the first few tokens for local models when `stream=True` to ensure the local model hasn't immediately hallucinated (a common issue with weak models).
2. **Update Ledger & Tracking**
   - Modify `cutctx/proxy/cost.py` and `cutctx/proxy/savings_tracker.py` to record "Routed Savings" (the delta between what Claude would have cost vs. what the local model cost).

### Phase 3: Dashboard & Analytics
1. **Update UI**
   - Add a new "Orchestrator Insights" tab in the dashboard.
   - Visualize:
     - Total Cost Saved via Routing.
     - Model Distribution (e.g., 60% Cloud, 40% Local).
     - Complexity Distribution (High, Medium, Low task breakdown).

---

## 5. Open Questions & Design Decisions

Before execution begins, the following decisions must be finalized:

1. **Local Provider Support**: Which local provider (Ollama, LM Studio, vLLM) should we prioritize as a first-class citizen for offloading low-complexity tasks?
2. **Streaming Fallbacks**: Coding agents heavily rely on streaming (`stream=True`). If a local model fails mid-stream, we cannot easily fallback to Claude without breaking the agent's parser. Do we buffer responses, or just fail fast and let the agent retry?
3. **Agent Adapters**: Should we build specific interceptors for **Cline** and **Aider** to better understand their unique prompt structures, or treat all incoming traffic generically?
