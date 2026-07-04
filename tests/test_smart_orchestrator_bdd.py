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

        # THEN the model should NOT be downgraded
        assert "model_routing" not in meta
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
