# Remote Compaction Passthrough Design

## Goal

Allow Codex remote-compaction requests to reach the ChatGPT subscription backend without proxy mutation.

## Evidence

Live failures show a 2.55 MB subscription request with the continuation fields `client_metadata`, `include`, `reasoning`, `store`, `stream`, and `text`. The proxy strips those fields and then truncates the body to 900 KB. ChatGPT returns HTTP 400.

## Design

Classify this request shape before model routing or payload processing: a ChatGPT subscription Responses request with the full remote-compaction field set and a large structured input. For that class, preserve the model, body, and delivery fields exactly; skip routing, compression, sanitization, and the context guard. Continue using the existing subscription route and authentication headers.

The classifier is deliberately narrow: ordinary subscription turns and ordinary oversized requests retain the existing safety policy.

## Verification

An HTTP-handler regression test will assert that a representative remote-compaction body reaches the upstream unchanged. The focused Responses routing suite will run before and after promotion, and the managed proxy readiness endpoint will be checked after restart.
