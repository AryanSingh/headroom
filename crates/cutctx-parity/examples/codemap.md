# crates/cutctx-parity/examples/

## Responsibility
Contains the executable fixture-diff example for inspecting normalized parity outputs.

## Design
The example is a thin consumer of the parity library rather than an alternate implementation.

## Flow
Load/construct comparable fixture values -> invoke normalization/comparison helpers -> print differences for developer inspection.

## Integration
- Built with Cargo examples and depends on `cutctx-parity`'s public API.
