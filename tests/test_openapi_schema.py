"""Regression tests for the generated public API contract."""

from cutctx.proxy.models import ProxyConfig
from cutctx.proxy.server import create_app


def test_openapi_schema_generates_with_webhook_subscription_model():
    schema = create_app(ProxyConfig()).openapi()

    assert "/webhooks/subscriptions" in schema["paths"]
    assert "WebhookSubscriptionInput" in schema["components"]["schemas"]


def test_openapi_operation_ids_are_unique_for_generated_clients():
    schema = create_app(ProxyConfig()).openapi()
    operation_ids = [
        operation["operationId"]
        for path_item in schema["paths"].values()
        for operation in path_item.values()
        if isinstance(operation, dict) and "operationId" in operation
    ]

    assert len(operation_ids) == len(set(operation_ids))
