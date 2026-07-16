# cutctx/proxy/routing/

## Responsibility
Provides runtime failover and request-format translation between provider routes.

## Design
Failover policy ranks alternate providers and guards retries; translators convert supported request/response schemas while retaining model, tool, and streaming semantics.

## Flow
After a primary route fails or a cross-provider target is selected, request data is translated, attempted against candidates under policy, and the successful response is translated back.

## Integration
Used by central router and provider handlers; consumes provider registry, circuit breakers, model routing, and observability.
