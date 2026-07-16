# cutctx/cli/_utils/

## Responsibility
Holds shared CLI parsing and terminal-formatting helpers.

## Design
Small pure functions centralize value parsing and consistent human-readable output.

## Flow
Commands pass raw option strings to parsers and structured results to formatters before display.

## Integration
Consumed throughout `cutctx.cli`; depends only on lightweight utilities.
