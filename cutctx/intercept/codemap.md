# cutctx/intercept/

## Responsibility
Implements host-level traffic interception for routing supported applications through the local proxy.

## Design
The macOS adapter encapsulates platform-specific certificate, proxy, and process configuration.

## Flow
Installation enables interception and teardown restores host state.

## Integration
Invoked by CLI setup/intercept; integrates with macOS networking and the proxy runtime.
