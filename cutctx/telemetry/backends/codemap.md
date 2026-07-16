# cutctx/telemetry/backends/

## Responsibility
Persists or exports privacy-filtered telemetry envelopes.

## Design
A backend protocol has filesystem and HTTPS-beacon strategies for offline versus remote delivery.

## Flow
The reporter submits an envelope; the backend stores/transmits it and returns delivery status for acknowledgement/retry.

## Integration
Consumed by telemetry reporter; uses local paths or configured collection endpoints.
