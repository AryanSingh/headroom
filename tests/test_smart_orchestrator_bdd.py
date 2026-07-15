from cutctx.proxy.model_router import (
    ModelRoute,
    ModelRouter,
    ModelRouterConfig,
    prepare_model_routing,
)


class MockHandler:
    def __init__(self, _model_router):
        self._model_router = _model_router


from cutctx.proxy.savings_metadata import _merge_payload


class TestSmartOrchestratorBDD:
    """BDD style tests for the Smart Coding Model Orchestrator."""

    def test_given_low_complexity_prompt_when_routed_then_downgraded(self):
        # GIVEN a model router configured for complexity routing
        config = ModelRouterConfig(
            enabled=True,
            downgrade_when="low_complexity",
            routes=[ModelRoute(source="gpt-4", target="llama-3-8b")],
        )
        router = ModelRouter(config=config)
        # mock cost lookup
        router._lookup_costs = lambda src, tgt: (10.0, 1.0)

        # WHEN a low complexity prompt is received
        messages = [{"role": "user", "content": "fix typo"}]
        handler = MockHandler(_model_router=router)
        target_model, meta = prepare_model_routing(
            handler, "gpt-4", messages=messages, request_savings_metadata={}
        )

        # THEN the model should be downgraded (routed away from source model)
        assert "model_routing" in meta
        assert meta["model_routing"]["target_model"] == "llama-3-8b"
        assert target_model == "llama-3-8b"

    def test_given_high_complexity_prompt_when_routed_then_retained(self):
        # GIVEN a model router configured for complexity routing
        config = ModelRouterConfig(
            enabled=True,
            downgrade_when="low_complexity",
            routes=[ModelRoute(source="gpt-4", target="llama-3-8b")],
        )
        router = ModelRouter(config=config)
        # mock cost lookup
        router._lookup_costs = lambda src, tgt: (10.0, 1.0)

        # WHEN a high/medium complexity prompt is received
        messages = [
            {"role": "user", "content": "build an entire orchestrator system with AST parsing"}
        ]
        handler = MockHandler(_model_router=router)
        target_model, meta = prepare_model_routing(
            handler, "gpt-4", messages=messages, request_savings_metadata={}
        )

        # THEN the model should NOT be downgraded, but the retained decision
        # remains observable for the request trace inspector.
        assert meta["model_routing"]["source_model"] == "gpt-4"
        assert meta["model_routing"]["target_model"] == "gpt-4"
        assert meta["model_routing"]["tokens_saved"] == 0
        assert target_model == "gpt-4"

    def test_given_routed_request_when_saved_then_ledger_updated(self):
        # GIVEN a routing decision with mocked metadata
        payload = {
            "model_routing": {
                "source_model": "gpt-4",
                "target_model": "llama-3-8b",
                "reason": "Complexity routing (LOW)",
                "tokens": 500,
                "usd": 0.05,
            }
        }

        # WHEN merged into savings payload (simulating proxy lifecycle)
        result = {}
        _merge_payload(result, payload)

        # THEN the ledger tracks the saved tokens and USD under model_routing
        assert "model_routing" in result
        assert result["model_routing"]["tokens"] == 500
        assert result["model_routing"]["usd"] == 0.05

    def test_given_codex_opencode_slim_when_low_complexity_then_routes_to_lighter_gpt(self):
        # GIVEN the named Codex/OpenCode slim preset
        config = ModelRouterConfig.codex_gpt54mini_high_preset()
        router = ModelRouter(config=config)
        router._lookup_costs = lambda src, tgt: (10.0, 1.0)

        # WHEN a simple Codex task arrives on a heavy GPT model
        messages = [{"role": "user", "content": "fix typo in README"}]
        handler = MockHandler(_model_router=router)
        target_model, meta = prepare_model_routing(
            handler,
            "gpt-5.5",
            messages=messages,
            request_savings_metadata={},
        )

        # THEN it routes to the configured lighter GPT model
        assert target_model == "gpt-5.4-mini"
        assert meta["model_routing"]["target_model"] == "gpt-5.4-mini"
        assert meta["model_routing"]["request_overrides"] == {"reasoning": {"effort": "high"}}

    def test_given_codex_opencode_slim_when_high_complexity_then_keeps_gpt_model(self):
        # GIVEN the named Codex/OpenCode slim preset
        config = ModelRouterConfig.codex_gpt54mini_high_preset()
        router = ModelRouter(config=config)
        router._lookup_costs = lambda src, tgt: (10.0, 1.0)

        # WHEN the request is a heavy coding task
        messages = [
            {
                "role": "user",
                "content": "build an orchestrator with AST parsing, retries, and replay tooling",
            }
        ]
        handler = MockHandler(_model_router=router)
        target_model, meta = prepare_model_routing(
            handler,
            "gpt-5.5",
            messages=messages,
            request_savings_metadata={},
        )

        # THEN the heavy GPT model is preserved and the abstention is visible.
        assert target_model == "gpt-5.5"
        assert meta["model_routing"]["source_model"] == "gpt-5.5"
        assert meta["model_routing"]["target_model"] == "gpt-5.5"
        assert meta["model_routing"]["tokens_saved"] == 0
