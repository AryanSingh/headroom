# Savings Telemetry

Partner caches, routers, and inference gateways can attribute savings without
calling a separate Headroom API. Send one `x-headroom-savings-metadata` header
on the request into the local proxy. The proxy strips this internal header
before forwarding upstream and persists the normalized savings into dashboard
history, buyer reports, and `cutctx integrations status`.

## Example

```bash
curl http://127.0.0.1:8787/v1/chat/completions \
  -H 'authorization: Bearer <provider-key>' \
  -H 'content-type: application/json' \
  -H 'x-headroom-savings-metadata: {"semantic_cache":{"tokens":420},"vllm_apc":{"prefix_cache_hits":900},"model_routing":{"tokens_routed":1200,"usd_saved":0.18}}' \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"hello"}]}'
```

## Accepted Sources

Canonical source keys:

- `provider_prompt_cache`
- `semantic_cache`
- `prefix_cache_self_hosted`
- `model_routing`

Accepted integration aliases:

| Integration | Payload shape | Savings source |
|-------------|---------------|----------------|
| LiteLLM | `{"litellm":{"cache_hit_tokens":500}}` | `provider_prompt_cache` |
| GPTCache | `{"gptcache":{"saved_prompt_tokens":500}}` | `semantic_cache` |
| vLLM APC | `{"vllm_apc":{"prefix_cache_hits":500}}` | `prefix_cache_self_hosted` |
| Model router | `{"model_routing":{"tokens_routed":500,"usd_saved":0.07}}` | `model_routing` |

Simple gateways may use dedicated headers instead of JSON:

- `x-headroom-provider-cache-tokens`
- `x-headroom-semantic-cache-avoided-tokens`
- `x-headroom-prefix-cache-hits`
- `x-headroom-model-routing-tokens`
- `x-headroom-model-routing-usd`

The same metadata path is wired for normal, streaming, batch, OpenAI
Responses, Gemini, Anthropic, Bedrock streaming, and passthrough outcomes.

## Optional Demo Integrations

The local `cutctx integrations status --format json` command reports whether
optional partner libraries are present in the current environment.

- `gptcache`: useful for semantic-cache demos on local dev machines
- `vllm`: typically deployed on Linux with self-hosted inference, not on macOS

If you want to demo these integrations locally, install them only in an
integration-specific environment rather than the default proxy runtime.
