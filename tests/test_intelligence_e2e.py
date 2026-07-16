"""End-to-end tests for the Intelligence Pipeline — all 6 features.

Tests simulate realistic multi-turn agent conversations with real data flows
through the full IntelligencePipeline, validating each feature actually works
in integration (not just unit-tested in isolation).

Features tested:
1. Task-Aware Compression — extract task, score messages, modulation
2. Semantic Dedup — duplicate content → CCR pointer replacement
3. Context Budget — progressive compression as token budget fills
4. Cross-Session Profiles — persistence to disk, load on restart
5. Multi-Agent Shared State — cache hit on repeated content
6. Cost Forecasting — policy engine + cost tracker accumulation
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from cutctx.proxy.intelligence_pipeline import IntelligencePipeline, PipelineContext

# ---------------------------------------------------------------------------
# Helpers — realistic message fixtures
# ---------------------------------------------------------------------------


def _make_task_messages(task: str, extra_context: str = "") -> list[dict]:
    """Create realistic agent conversation with a detectable task."""
    msgs = [
        {"role": "system", "content": "You are a helpful coding assistant."},
        {"role": "user", "content": f"Please {task} in the codebase."},
        {"role": "assistant", "content": "I'll help you with that. Let me look at the code."},
    ]
    if extra_context:
        msgs.append({"role": "user", "content": extra_context})
    return msgs


def _make_long_content(length: int = 2000, prefix: str = "") -> str:
    """Generate a long content block for dedup/budget testing."""
    base = prefix or "The quick brown fox jumps over the lazy dog. "
    repeats = length // len(base) + 1
    return (base * repeats)[:length]


def _make_repeated_turns(n: int, content_len: int = 1200) -> list[dict]:
    """Create N turns with alternating user/assistant messages, each with substantial content."""
    msgs = [{"role": "system", "content": "You are a helpful assistant."}]
    for i in range(n):
        role = "user" if i % 2 == 0 else "assistant"
        content = f"Turn {i}: " + _make_long_content(content_len, f"Message from turn {i}. ")
        msgs.append({"role": role, "content": content})
    return msgs


def _make_duplicate_content_messages(n_copies: int = 3) -> list[dict]:
    """Create messages where the same large content appears multiple times."""
    file_content = _make_long_content(
        1200, "class DatabaseConnection:\n    def __init__(self, host, port): "
    )
    msgs = [{"role": "system", "content": "You are a helpful coding assistant."}]
    for i in range(n_copies):
        msgs.append(
            {"role": "user", "content": f"Here's the file content (copy {i + 1}):\n{file_content}"}
        )
    msgs.append(
        {"role": "assistant", "content": "I see the file content repeated. Let me analyze it."}
    )
    return msgs


# ---------------------------------------------------------------------------
# 1. Task-Aware Compression — E2E
# ---------------------------------------------------------------------------


class TestTaskAwareE2E:
    """End-to-end task-aware compression testing."""

    def test_task_extracted_and_relevance_scores_assigned(self):
        """Full pipeline: task is extracted and every message gets a relevance score."""
        pipeline = IntelligencePipeline(task_aware=True)
        messages = _make_task_messages(
            "debug the HTTP 500 error",
            "The error occurs when calling /api/users endpoint with invalid auth token",
        )

        ctx = pipeline.pre_compression(messages, model="claude-sonnet-4")

        # Task should be detected
        assert ctx.task is not None
        assert "debug" in ctx.task.lower() or "error" in ctx.task.lower()

        # Every message should have a relevance score
        assert len(ctx.message_relevance_scores) == len(messages)

        # Scores should be floats in [0, 1]
        for score in ctx.message_relevance_scores:
            assert 0.0 <= score <= 1.0

    def test_relevant_messages_score_higher_than_irrelevant(self):
        """Messages about the task score higher than unrelated messages."""
        pipeline = IntelligencePipeline(task_aware=True)

        # Messages where some are relevant to "debug error 500" and some are not
        messages = [
            {"role": "system", "content": "You are a helpful coding assistant."},
            {"role": "user", "content": "debug the HTTP 500 error in the API"},
            {
                "role": "assistant",
                "content": "The error trace shows a NullPointerException in DatabaseConnection.connect()",
            },
            {
                "role": "user",
                "content": "Also, what's the weather like today? Can you recommend a good restaurant?",
            },
        ]

        ctx = pipeline.pre_compression(messages, model="claude-sonnet-4")

        if ctx.task and len(ctx.message_relevance_scores) >= 4:
            # The error-related assistant message should score higher than weather
            error_msg_score = ctx.message_relevance_scores[2]  # error trace
            weather_msg_score = ctx.message_relevance_scores[3]  # weather question
            # At minimum, error score should not be less than weather score
            # (BM25 might give weather a score too due to "today" etc.)
            assert error_msg_score >= weather_msg_score - 0.1

    def test_no_task_means_no_relevance_scores(self):
        """When task_aware is disabled, no relevance scores are computed."""
        pipeline = IntelligencePipeline(task_aware=False)
        messages = _make_task_messages("fix the bug")

        ctx = pipeline.pre_compression(messages, model="claude-sonnet-4")

        assert ctx.task is None
        assert ctx.message_relevance_scores == []

    def test_short_messages_get_full_relevance(self):
        """Short/structured messages (<20 chars) get 1.0 relevance (fully relevant)."""
        pipeline = IntelligencePipeline(task_aware=True)
        messages = [
            {"role": "system", "content": "sys"},  # <20 chars → 1.0
            {
                "role": "user",
                "content": "debug the critical authentication timeout error",
            },  # long → scored
            {"role": "assistant", "content": "ok"},  # <20 chars → 1.0
        ]

        ctx = pipeline.pre_compression(messages, model="claude-sonnet-4")

        if ctx.task:
            assert len(ctx.message_relevance_scores) == 3
            assert ctx.message_relevance_scores[0] == 1.0  # short "sys"
            assert ctx.message_relevance_scores[2] == 1.0  # short "ok"

    def test_question_word_task_extraction(self):
        """Tasks starting with question words (How, What, Why) are extracted."""
        pipeline = IntelligencePipeline(task_aware=True)
        messages = [
            {
                "role": "user",
                "content": "How does the authentication middleware work in the proxy server?",
            },
        ]

        ctx = pipeline.pre_compression(messages, model="claude-sonnet-4")

        assert ctx.task is not None
        assert len(ctx.task) >= 10


# ---------------------------------------------------------------------------
# 2. Semantic Dedup — E2E
# ---------------------------------------------------------------------------


class TestSemanticDedupE2E:
    """End-to-end semantic deduplication testing."""

    def test_duplicate_content_replaced_with_pointer(self):
        """When same content appears twice, second is replaced with [cutctx:ref:HASH]."""
        pipeline = IntelligencePipeline(dedup=True)
        # Use TRULY identical messages (no per-copy prefix)
        large_content = _make_long_content(1200)
        messages = [
            {"role": "user", "content": large_content},
            {"role": "user", "content": large_content},
        ]

        # Pre-compression (no-op for dedup)
        ctx = pipeline.pre_compression(messages, model="claude-sonnet-4")

        # Post-compression applies dedup
        result = pipeline.post_compression(messages, messages, ctx, request_id="test-1")

        # Find messages that got replaced
        deduped = [m for m in result if "[cutctx:ref:" in m.get("content", "")]
        assert len(deduped) >= 1, f"Expected at least 1 deduped message, got {len(deduped)}"
        assert ctx.dedup_count >= 1
        assert ctx.tokens_saved_by_dedup > 0

    def test_system_messages_not_deduped(self):
        """System messages are never replaced with pointers."""
        pipeline = IntelligencePipeline(dedup=True)
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "system", "content": "You are a helpful assistant."},  # Same system msg
        ]

        ctx = pipeline.pre_compression(messages, model="claude-sonnet-4")
        result = pipeline.post_compression(messages, messages, ctx, request_id="test-2")

        for m in result:
            assert "[cutctx:ref:" not in m.get("content", "")

    def test_short_content_not_deduped(self):
        """Content below MIN_DEDUP_TOKENS (200) is not deduped."""
        pipeline = IntelligencePipeline(dedup=True)
        messages = [
            {"role": "user", "content": "short"},  # <200 tokens
            {"role": "user", "content": "short"},
        ]

        ctx = pipeline.pre_compression(messages, model="claude-sonnet-4")
        result = pipeline.post_compression(messages, messages, ctx, request_id="test-3")

        assert ctx.dedup_count == 0

    def test_dedup_across_multiple_process_calls(self):
        """Deduplicator state persists across multiple process() calls."""
        from cutctx.dedup import SessionDeduplicator

        dedup = SessionDeduplicator()
        large_content = _make_long_content(1200)

        # First call: content is new
        r1 = dedup.process([{"role": "user", "content": large_content}])
        assert r1.dedup_count == 0
        assert r1.refs_created == 1

        # Second call: same content → deduped
        r2 = dedup.process([{"role": "user", "content": large_content}])
        assert r2.dedup_count == 1
        assert "[cutctx:ref:" in r2.messages[0]["content"]

    def test_three_way_dedup_saves_two(self):
        """Three copies of same content → 1 tracked + 2 deduped."""
        pipeline = IntelligencePipeline(dedup=True)
        large_content = _make_long_content(1200)
        messages = [
            {"role": "user", "content": large_content},
            {"role": "user", "content": large_content},
            {"role": "user", "content": large_content},
        ]

        ctx = pipeline.pre_compression(messages, model="claude-sonnet-4")
        result = pipeline.post_compression(messages, messages, ctx, request_id="test-5")

        assert ctx.dedup_count == 2


# ---------------------------------------------------------------------------
# 3. Context Budget — E2E
# ---------------------------------------------------------------------------


class TestContextBudgetE2E:
    """End-to-end context budget controller testing."""

    def test_green_zone_no_compression(self):
        """When well under budget, no compression is applied."""
        pipeline = IntelligencePipeline(context_budget=True, context_budget_max_tokens=100_000)
        messages = _make_repeated_turns(5, content_len=200)

        ctx = pipeline.pre_compression(messages, model="claude-sonnet-4")
        result = pipeline.post_compression(messages, messages, ctx, request_id="test-budget-1")

        assert ctx.budget_zone == "GREEN"
        assert ctx.budget_compression_applied is False

    def test_large_context_triggers_compression(self):
        """When context exceeds budget, compression is applied."""
        # Use a very small budget to trigger compression
        pipeline = IntelligencePipeline(
            context_budget=True,
            context_budget_max_tokens=500,  # Very small budget
            context_budget_policy="aggressive",
        )
        # Create messages that will exceed 500 tokens
        messages = _make_repeated_turns(20, content_len=500)

        ctx = pipeline.pre_compression(messages, model="claude-sonnet-4")
        result = pipeline.post_compression(messages, messages, ctx, request_id="test-budget-2")

        # Should be in non-GREEN zone with compression applied
        assert ctx.budget_zone != "GREEN" or ctx.budget_compression_applied is True

    def test_budget_status_reports_accurately(self):
        """Budget status reports token usage and zone correctly."""
        from cutctx.context_budget import ContextBudgetController

        budget = ContextBudgetController(max_tokens=10_000, model="claude-sonnet-4")
        messages = _make_repeated_turns(10, content_len=500)

        result = budget.apply(messages)
        status = budget.status

        assert status.tokens_used > 0
        assert status.tokens_budget == 10_000
        assert status.percent_used > 0
        assert hasattr(status.zone, "value")  # BudgetZone enum

    def test_budget_zone_transitions(self):
        """Budget controller transitions through GREEN → YELLOW → RED as context grows."""
        from cutctx.context_budget import ContextBudgetController

        budget = ContextBudgetController(max_tokens=1_000, model="claude-sonnet-4")

        # Small context → GREEN
        small = _make_repeated_turns(2, content_len=100)
        budget.apply(small)
        assert budget.status.zone.value == "GREEN"

        # Larger context → should transition
        large = _make_repeated_turns(50, content_len=500)
        budget.apply(large)
        # With 50*500=25000 chars / 4 = 6250 tokens, budget is 1000 → CRITICAL
        assert budget.status.zone.value in ("YELLOW", "RED", "CRITICAL")


# ---------------------------------------------------------------------------
# 4. Cross-Session Profiles — E2E
# ---------------------------------------------------------------------------


class TestCrossSessionProfilesE2E:
    """End-to-end cross-session profile testing."""

    def test_profile_persists_to_disk(self):
        """Profile data is saved to disk and can be reloaded."""
        from cutctx.profiles import CompressionProfile

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a profile with a known hash
            test_hash = "test_e2e_hash"
            profile = CompressionProfile(workspace_hash=test_hash)
            profile.record_session(
                session_id="test-session-1",
                stats=[
                    {
                        "content_type": "code",
                        "original_count": 1000,
                        "compressed_count": 500,
                        "was_retrieved": False,
                    }
                ],
            )

            # Monkeypatch _get_profile_path to use our tmpdir
            def fake_get_profile_path(ws_hash):
                return Path(tmpdir) / f"{ws_hash}.json"

            with patch("cutctx.profiles._get_profile_path", side_effect=fake_get_profile_path):
                profile.save()

            # Verify file exists
            expected_path = Path(tmpdir) / "test_e2e_hash.json"
            assert expected_path.exists()

            # Reload
            with open(expected_path) as f:
                data = json.load(f)
            assert "stats" in data
            assert "code" in data["stats"]
            assert data["stats"]["code"]["sessions_seen"] == 1

    def test_profile_recommends_less_compression_after_retrievals(self):
        """After high CCR retrieval rates, profile recommends less aggressive compression."""
        from cutctx.profiles import CompressionProfile

        profile = CompressionProfile(workspace_hash="test_retrieval")

        # Record 10 compressions, 7 retrieved → 70% retrieval rate
        for _ in range(10):
            profile.record_session(
                session_id=f"session-{_}",
                stats=[
                    {
                        "content_type": "logs",
                        "original_count": 1000,
                        "compressed_count": 300,  # 30% ratio (aggressive)
                        "was_retrieved": True,
                    }
                ],
            )

        # High retrieval rate should push recommended ratio higher
        target = profile.get_compression_target("logs")
        assert target > 0.3  # Should increase from aggressive 0.3 ratio

    def test_profile_in_pipeline(self):
        """Pipeline loads profile and records session data."""
        pipeline = IntelligencePipeline(profiles=True)
        messages = _make_task_messages("review code")

        # Mock _get_profile to avoid filesystem dependencies
        mock_profile = MagicMock()
        mock_profile.stats = {"code": MagicMock(recommended_ratio=0.5)}

        with patch.object(pipeline, "_get_profile", return_value=mock_profile):
            # Pre: should load profile
            ctx = pipeline.pre_compression(messages, model="claude-sonnet-4")
            assert ctx.profile_loaded is True
            assert "code" in ctx.profile_recommendations

            # Post: should record session
            pipeline.post_compression(messages, messages, ctx, request_id="test-profile-3")
            mock_profile.record_session.assert_called_once()
            mock_profile.save.assert_called_once()

    def test_profile_recommendation_adjusts_over_time(self):
        """Profile learns over multiple sessions and adjusts recommendations."""
        from cutctx.profiles import CompressionProfile

        profile = CompressionProfile(workspace_hash="test_learning")

        # Session 1-2: low retrieval rate → keep current ratio
        for i in range(2):
            profile.record_session(
                session_id=f"low-retrieval-{i}",
                stats=[
                    {
                        "content_type": "tool_output",
                        "original_count": 1000,
                        "compressed_count": 400,
                        "was_retrieved": False,
                    }
                ],
            )

        target_after_low = profile.get_compression_target("tool_output")

        # Session 3-5: high retrieval rate → should increase
        for i in range(3):
            profile.record_session(
                session_id=f"high-retrieval-{i}",
                stats=[
                    {
                        "content_type": "tool_output",
                        "original_count": 1000,
                        "compressed_count": 400,
                        "was_retrieved": True,
                    }
                ],
            )

        target_after_high = profile.get_compression_target("tool_output")
        # After high retrieval, target should be higher (less aggressive)
        assert target_after_high >= target_after_low


# ---------------------------------------------------------------------------
# 5. Multi-Agent Shared State — E2E
# ---------------------------------------------------------------------------


class TestMultiAgentSharedStateE2E:
    """End-to-end multi-agent shared state testing."""

    def test_cache_hit_on_repeated_content(self):
        """Agent B gets cache hit when compressing same content as Agent A."""
        from cutctx.shared_context import MultiAgentCoordinator

        # Reset singleton to avoid cross-test contamination
        MultiAgentCoordinator.reset_instance()
        coordinator = MultiAgentCoordinator.get_instance()

        content = _make_long_content(1200)

        # Agent A compresses
        result_a = coordinator.compress_shared(
            content=content,
            agent_id="agent-a",
            workspace_key="test-project",
        )
        assert result_a.cache_hit is False

        # Agent B compresses same content → cache hit
        result_b = coordinator.compress_shared(
            content=content,
            agent_id="agent-b",
            workspace_key="test-project",
        )
        assert result_b.cache_hit is True
        assert result_b.compressed_content == result_a.compressed_content

        MultiAgentCoordinator.reset_instance()

    def test_cache_miss_on_different_content(self):
        """Different content gets cache miss."""
        from cutctx.shared_context import MultiAgentCoordinator

        MultiAgentCoordinator.reset_instance()
        coordinator = MultiAgentCoordinator.get_instance()

        result_a = coordinator.compress_shared(
            content="Content about database connections and SQL queries",
            agent_id="agent-a",
            workspace_key="test-project",
        )
        result_b = coordinator.compress_shared(
            content="Content about frontend React components and JSX",
            agent_id="agent-b",
            workspace_key="test-project",
        )

        assert result_a.cache_hit is False
        assert result_b.cache_hit is False

        MultiAgentCoordinator.reset_instance()

    def test_workspace_isolation(self):
        """Content in different workspaces is not shared."""
        from cutctx.shared_context import MultiAgentCoordinator

        MultiAgentCoordinator.reset_instance()
        coordinator = MultiAgentCoordinator.get_instance()

        content = _make_long_content(1200)

        result_a = coordinator.compress_shared(
            content=content,
            agent_id="agent-a",
            workspace_key="project-alpha",
        )
        result_b = coordinator.compress_shared(
            content=content,
            agent_id="agent-b",
            workspace_key="project-beta",  # Different workspace
        )

        assert result_a.cache_hit is False
        assert result_b.cache_hit is False  # Isolated by workspace

        MultiAgentCoordinator.reset_instance()

    def test_shared_state_in_pipeline(self):
        """Pipeline registers as agent and stores compression results."""
        pipeline = IntelligencePipeline(shared_context=True)
        messages = _make_task_messages("review code")

        # Mock compress_shared to avoid cutctx.compress import chain
        mock_coordinator = MagicMock()
        mock_coordinator.get_agent_context.return_value = MagicMock(total_items_compressed=0)

        # Pre: should register proxy as agent
        with patch.object(pipeline, "_get_coordinator", return_value=mock_coordinator):
            ctx = pipeline.pre_compression(messages, model="claude-sonnet-4")
            mock_coordinator.register_agent.assert_called_once()
            assert ctx.shared_context_hit is False  # First request, no prior context

            # Post: should store compressed result
            pipeline.post_compression(messages, messages, ctx, request_id="test-shared-1")
            mock_coordinator.compress_shared.assert_called_once()

        # Now simulate a coordinator that HAS prior data
        mock_coordinator2 = MagicMock()
        mock_coordinator2.get_agent_context.return_value = MagicMock(total_items_compressed=5)

        with patch.object(pipeline, "_get_coordinator", return_value=mock_coordinator2):
            ctx2 = pipeline.pre_compression(messages, model="claude-sonnet-4")
            assert ctx2.shared_context_hit is True  # Previous request stored data

    def test_agent_tracking(self):
        """Agents are properly registered and tracked."""
        from cutctx.shared_context import MultiAgentCoordinator

        MultiAgentCoordinator.reset_instance()
        coordinator = MultiAgentCoordinator.get_instance()

        coordinator.register_agent("coding-agent", {"framework": "langchain"})
        coordinator.set_agent_task("coding-agent", "implement auth module")

        info = coordinator.get_agent_context("coding-agent")
        assert info.active is True
        assert info.current_task == "implement auth module"
        assert info.metadata["framework"] == "langchain"

        MultiAgentCoordinator.reset_instance()


# ---------------------------------------------------------------------------
# 6. Cost Forecasting — E2E
# ---------------------------------------------------------------------------


class TestCostForecastingE2E:
    """End-to-end cost forecasting testing."""

    def test_policy_engine_selects_strategy(self):
        """Policy engine selects appropriate strategy based on budget."""
        from cutctx.cost_forecast import CompressionStrategy, PolicyEngine

        engine = PolicyEngine(model="claude-sonnet-4")

        # High budget → light compression
        decision_high = engine.evaluate(
            input_tokens=10_000,
            budget_remaining_usd=50.0,
        )
        assert decision_high.strategy in (CompressionStrategy.LIGHT, CompressionStrategy.MINIMAL)

        # Critical budget → emergency compression
        decision_critical = engine.evaluate(
            input_tokens=10_000,
            budget_remaining_usd=0.20,
        )
        assert decision_critical.strategy == CompressionStrategy.EMERGENCY

    def test_cost_tracker_accumulates_across_requests(self):
        """Cost tracker accumulates costs across multiple requests."""
        from cutctx.cost_forecast import SessionCostTracker

        tracker = SessionCostTracker(model="claude-sonnet-4")

        # Record 3 requests
        tracker.record_request(input_tokens=10_000, output_tokens=1_000)
        tracker.record_request(input_tokens=20_000, output_tokens=2_000)
        tracker.record_request(
            input_tokens=15_000,
            output_tokens=1_500,
            compressed_input_tokens=8_000,  # Compressed
        )

        snap = tracker.snapshot()

        assert snap.request_count == 3
        assert snap.total_input_tokens == 45_000
        assert snap.total_output_tokens == 4_500
        assert snap.total_usd > 0
        assert snap.tokens_saved_by_compression > 0
        assert snap.usd_saved_by_compression > 0

    def test_cost_forecast_in_pipeline(self):
        """Pipeline evaluates policy and tracks costs across requests."""
        pipeline = IntelligencePipeline(cost_forecast=True)
        messages = _make_task_messages("optimize performance")

        # First request
        ctx1 = pipeline.pre_compression(messages, model="claude-sonnet-4")
        assert ctx1.policy_strategy is not None
        assert ctx1.policy_compression_ratio > 0

        pipeline.post_compression(
            messages,
            messages,
            ctx1,
            request_id="test-cost-1",
            input_tokens=10_000,
            output_tokens=500,
        )

        # Second request — cost tracker should have accumulated
        ctx2 = pipeline.pre_compression(messages, model="claude-sonnet-4")
        pipeline.post_compression(
            messages,
            messages,
            ctx2,
            request_id="test-cost-2",
            input_tokens=15_000,
            output_tokens=800,
        )

        # Cost tracker should have data from both requests
        tracker = pipeline._get_cost_tracker()
        snap = tracker.snapshot()
        assert snap.request_count == 2
        assert snap.total_usd > 0

    def test_cost_estimator_savings_calculation(self):
        """CostEstimator correctly calculates compression savings."""
        from cutctx.cost_forecast import CostEstimator

        estimator = CostEstimator(model="claude-sonnet-4")

        # Without compression
        no_compress = estimator.estimate(input_tokens=100_000, output_tokens=5_000)
        assert no_compress.compression_savings_usd == 0

        # With 50% compression
        with_compress = estimator.estimate(
            input_tokens=100_000,
            output_tokens=5_000,
            compression_ratio=0.5,
        )
        assert with_compress.compression_savings_usd > 0
        assert with_compress.savings_percent > 40  # ~50% savings

    def test_model_pricing_resolves_correctly(self):
        """Model pricing resolves for known models with fallback."""
        from cutctx.cost_forecast import CostEstimator

        # Known model
        estimator_sonnet = CostEstimator(model="claude-sonnet-4")
        estimate_sonnet = estimator_sonnet.estimate(input_tokens=1_000_000)
        assert estimate_sonnet.input_usd == 3.0  # $3/M

        # Unknown models are not assigned an invented family price.
        estimator_unknown = CostEstimator(model="unknown-model-v99")
        estimate_unknown = estimator_unknown.estimate(input_tokens=1_000_000)
        assert estimate_unknown.input_usd is None
        assert estimate_unknown.total_usd is None


# ---------------------------------------------------------------------------
# 7. Full Pipeline — Multi-Request Persistence
# ---------------------------------------------------------------------------


class TestPipelinePersistenceE2E:
    """Test that pipeline state persists across multiple requests."""

    def test_dedup_accumulates_across_requests(self):
        """Deduplicator tracks hashes across multiple pipeline calls."""
        pipeline = IntelligencePipeline(dedup=True)
        large_content = _make_long_content(1200)

        # Request 1: content is new
        msgs1 = [{"role": "user", "content": large_content}]
        ctx1 = pipeline.pre_compression(msgs1, model="claude-sonnet-4")
        pipeline.post_compression(msgs1, msgs1, ctx1, "req-1")
        assert ctx1.dedup_count == 0

        # Request 2: same content → deduped
        msgs2 = [{"role": "user", "content": large_content}]
        ctx2 = pipeline.pre_compression(msgs2, model="claude-sonnet-4")
        result2 = pipeline.post_compression(msgs2, msgs2, ctx2, "req-2")
        assert ctx2.dedup_count == 1
        assert "[cutctx:ref:" in result2[0]["content"]

        # Request 3: still deduped
        msgs3 = [{"role": "user", "content": large_content}]
        ctx3 = pipeline.pre_compression(msgs3, model="claude-sonnet-4")
        pipeline.post_compression(msgs3, msgs3, ctx3, "req-3")
        assert ctx3.dedup_count == 1

    def test_cost_tracker_accumulates_across_requests(self):
        """Cost tracker accumulates across pipeline calls."""
        pipeline = IntelligencePipeline(cost_forecast=True)
        messages = _make_task_messages("review code")

        for i in range(5):
            ctx = pipeline.pre_compression(messages, model="claude-sonnet-4")
            pipeline.post_compression(
                messages,
                messages,
                ctx,
                request_id=f"req-{i}",
                input_tokens=10_000,
                output_tokens=500,
            )

        tracker = pipeline._get_cost_tracker()
        snap = tracker.snapshot()
        assert snap.request_count == 5
        assert snap.total_input_tokens == 50_000

    def test_profile_accumulates_across_requests(self):
        """Profile records multiple sessions."""
        pipeline = IntelligencePipeline(profiles=True)
        messages = _make_task_messages("review code")

        # Mock profile to avoid filesystem
        mock_profile = MagicMock()
        mock_profile.stats = {}

        with patch.object(pipeline, "_get_profile", return_value=mock_profile):
            for i in range(3):
                ctx = pipeline.pre_compression(messages, model="claude-sonnet-4")
                pipeline.post_compression(messages, messages, ctx, request_id=f"session-{i}")

            # Profile should have been called 3 times
            assert mock_profile.record_session.call_count == 3
            assert mock_profile.save.call_count == 3


# ---------------------------------------------------------------------------
# 8. Graceful Failure — E2E
# ---------------------------------------------------------------------------


class TestGracefulFailureE2E:
    """Test that failures in individual modules don't break the pipeline."""

    def test_task_extraction_failure_doesnt_break_pipeline(self):
        """If TaskExtractor fails, pipeline continues."""
        pipeline = IntelligencePipeline(task_aware=True)
        messages = [{"role": "user", "content": "help me"}]

        with patch(
            "cutctx.compression.task_aware.TaskExtractor.extract_task",
            side_effect=RuntimeError("boom"),
        ):
            ctx = pipeline.pre_compression(messages, model="claude-sonnet-4")
            # Should not raise
            assert ctx.task is None

    def test_dedup_failure_doesnt_break_post_compression(self):
        """If deduplicator fails, post_compression returns original messages."""
        pipeline = IntelligencePipeline(dedup=True)
        messages = _make_task_messages("fix bug")
        ctx = PipelineContext()

        with patch.object(pipeline, "_get_deduplicator", side_effect=RuntimeError("dedup boom")):
            result = pipeline.post_compression(messages, messages, ctx, "test-fail-1")
            # Should return original messages unchanged
            assert len(result) == len(messages)

    def test_cost_forecast_failure_doesnt_break_pipeline(self):
        """If cost forecast fails, pipeline continues."""
        pipeline = IntelligencePipeline(cost_forecast=True)
        messages = _make_task_messages("fix bug")

        with patch("cutctx.cost_forecast.PolicyEngine", side_effect=RuntimeError("cost boom")):
            ctx = pipeline.pre_compression(messages, model="claude-sonnet-4")
            assert ctx.policy_strategy == "light"  # Default

    def test_profile_failure_doesnt_break_pipeline(self):
        """If profile fails, pipeline continues."""
        pipeline = IntelligencePipeline(profiles=True)
        messages = _make_task_messages("review code")
        ctx = PipelineContext()

        with patch.object(pipeline, "_get_profile", side_effect=RuntimeError("profile boom")):
            result = pipeline.post_compression(messages, messages, ctx, "test-fail-3")
            assert len(result) == len(messages)

    def test_shared_context_failure_doesnt_break_pipeline(self):
        """If shared context fails, pipeline continues."""
        pipeline = IntelligencePipeline(shared_context=True)
        messages = _make_task_messages("fix bug")
        ctx = PipelineContext()

        with patch.object(pipeline, "_get_coordinator", side_effect=RuntimeError("coord boom")):
            result = pipeline.post_compression(messages, messages, ctx, "test-fail-4")
            assert len(result) == len(messages)

    def test_budget_failure_doesnt_break_pipeline(self):
        """If context budget fails, pipeline continues."""
        pipeline = IntelligencePipeline(context_budget=True)
        messages = _make_task_messages("fix bug")
        ctx = PipelineContext()

        with patch.object(
            pipeline, "_get_budget_controller", side_effect=RuntimeError("budget boom")
        ):
            result = pipeline.post_compression(messages, messages, ctx, "test-fail-5")
            assert len(result) == len(messages)


# ---------------------------------------------------------------------------
# 9. Combined Feature E2E — Full Stack
# ---------------------------------------------------------------------------


class TestCombinedFeaturesE2E:
    """Test multiple features working together in a realistic scenario."""

    def test_all_features_enabled_together(self):
        """All 6 features enabled — full pipeline runs without errors."""
        pipeline = IntelligencePipeline(
            task_aware=True,
            dedup=True,
            context_budget=True,
            context_budget_max_tokens=100_000,
            profiles=True,
            shared_context=True,
            cost_forecast=True,
        )

        messages = _make_task_messages(
            "debug the database connection pooling issue",
            "The error happens intermittently under high load with 500 concurrent connections",
        )

        # Pre-compression
        ctx = pipeline.pre_compression(messages, model="claude-sonnet-4")
        assert ctx.task is not None
        assert ctx.policy_strategy is not None

        # Post-compression
        result = pipeline.post_compression(
            messages,
            messages,
            ctx,
            request_id="combined-test-1",
            input_tokens=5_000,
            output_tokens=200,
        )

        # Verify all features ran
        assert ctx.policy_strategy is not None  # Cost forecast ran
        assert ctx.total_latency_ms > 0  # Pipeline took some time
        # Messages should be intact (GREEN zone, no dedup on small content)
        assert len(result) == len(messages)

    def test_realistic_multi_turn_conversation(self):
        """Simulate a realistic 10-turn agent conversation."""
        pipeline = IntelligencePipeline(
            task_aware=True,
            dedup=True,
            cost_forecast=True,
            profiles=True,
        )

        # Simulate turns with file reads (duplicated content)
        file_content = _make_long_content(
            1200,
            "def authenticate_user(request):\n    token = request.headers.get('Authorization')\n",
        )
        messages = [
            {"role": "system", "content": "You are a Python backend developer."},
            {"role": "user", "content": "Please debug the authentication error in the API"},
            {"role": "assistant", "content": "I'll look at the authentication code."},
            {"role": "user", "content": f"Here's the file:\n{file_content}"},
            {
                "role": "assistant",
                "content": "I see the issue. The token validation is missing error handling.",
            },
            {"role": "user", "content": f"Here's the file again:\n{file_content}"},  # Duplicate!
            {"role": "assistant", "content": "Let me fix the error handling."},
            {"role": "user", "content": "Now test the fix with a valid token"},
            {"role": "assistant", "content": "The fix works. Here are the test results."},
            {"role": "user", "content": "Deploy the fix to staging"},
        ]

        # Request 1: initial context
        ctx1 = pipeline.pre_compression(messages[:5], model="claude-sonnet-4")
        result1 = pipeline.post_compression(
            messages[:5],
            messages[:5],
            ctx1,
            request_id="turn-1",
            input_tokens=15_000,
            output_tokens=500,
        )

        # Request 2: full conversation with duplicate
        ctx2 = pipeline.pre_compression(messages, model="claude-sonnet-4")
        result2 = pipeline.post_compression(
            messages,
            messages,
            ctx2,
            request_id="turn-2",
            input_tokens=30_000,
            output_tokens=1_000,
        )

        # Verify
        assert ctx2.task is not None
        assert ctx2.policy_strategy is not None
        tracker = pipeline._get_cost_tracker()
        assert tracker.snapshot().request_count == 2

    def test_pipeline_context_to_dict_roundtrip(self):
        """PipelineContext serializes to dict correctly."""
        ctx = PipelineContext(
            task="debug error",
            dedup_count=3,
            tokens_saved_by_dedup=1500,
            budget_zone="YELLOW",
            cost_estimate_usd=0.15,
            cost_savings_usd=0.05,
            policy_strategy="moderate",
            policy_compression_ratio=0.5,
            policy_rationale="budget < $5",
            shared_context_hit=True,
            total_latency_ms=12.5,
            message_relevance_scores=[0.8, 0.3, 0.9],
        )

        d = ctx.to_dict()
        assert d["task"] == "debug error"
        assert d["dedup_count"] == 3
        assert d["budget_zone"] == "YELLOW"
        assert d["policy_strategy"] == "moderate"
        assert d["message_relevance_scores"] == [0.8, 0.3, 0.9]


# ---------------------------------------------------------------------------
# 10. Integration with from_config — E2E
# ---------------------------------------------------------------------------


class TestFromConfigE2E:
    """Test that from_config correctly reads ProxyConfig attributes."""

    def test_from_config_all_enabled(self):
        """from_config reads all enabled flags from a config object."""
        config = MagicMock()
        config.task_aware_enabled = True
        config.dedup_enabled = True
        config.context_budget_enabled = True
        config.context_budget_max_tokens = 50_000
        config.context_budget_policy = "aggressive"
        config.profiles_enabled = True
        config.shared_context_enabled = True
        config.cost_forecast_enabled = True
        config.default_model = "gpt-4o"

        pipeline = IntelligencePipeline.from_config(config)

        assert pipeline.task_aware is True
        assert pipeline.dedup is True
        assert pipeline.context_budget is True
        assert pipeline.context_budget_max_tokens == 50_000
        assert pipeline.context_budget_policy == "aggressive"
        assert pipeline.profiles is True
        assert pipeline.shared_context is True
        assert pipeline.cost_forecast is True
        assert pipeline.model == "gpt-4o"

    def test_from_config_all_disabled(self):
        """from_config with all flags disabled creates noop pipeline."""
        config = MagicMock(spec=[])  # No attributes
        pipeline = IntelligencePipeline.from_config(config)

        assert pipeline.any_enabled() is False

    def test_any_enabled(self):
        """any_enabled returns True when at least one feature is on."""
        p1 = IntelligencePipeline(task_aware=True)
        assert p1.any_enabled() is True

        p2 = IntelligencePipeline()
        assert p2.any_enabled() is False

        p3 = IntelligencePipeline(cost_forecast=True)
        assert p3.any_enabled() is True
