from cutctx.proxy.model_router import (
    TaskComplexity,
    classify_task_complexity,
    ModelRouter,
    ModelRouterConfig,
)

def test_classify_task_complexity_low():
    messages = [
        {"role": "user", "content": "Please fix the typo in this file"}
    ]
    assert classify_task_complexity(messages) == TaskComplexity.LOW

    messages = [
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "add type hints to the function"}
    ]
    assert classify_task_complexity(messages) == TaskComplexity.LOW

def test_classify_task_complexity_medium():
    messages = [
        {"role": "user", "content": "Please refactor the model_router.py to use an ML classifier."}
    ]
    assert classify_task_complexity(messages) == TaskComplexity.MEDIUM

def test_router_integration():
    config = ModelRouterConfig(
        enabled=True,
        downgrade_when="low_complexity",
    )
    router = ModelRouter(config=config)

    # Low complexity should be downgradeable
    messages_low = [{"role": "user", "content": "fix linting"}]
    assert router.is_text_downgradeable(messages_low) == True

    # Medium complexity should NOT be downgradeable by text classifier
    messages_medium = [{"role": "user", "content": "implement a new websocket handler"}]
    assert router.is_text_downgradeable(messages_medium) == False

if __name__ == "__main__":
    test_classify_task_complexity_low()
    test_classify_task_complexity_medium()
    test_router_integration()
    print("All tests passed!")
