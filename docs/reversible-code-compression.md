# Reversible code compression

Source code is the largest incompressible surface the proxy sees, and it is
what the highest-volume client sends: Codex is 4.16B input tokens at 0.33%
saved, and its one eligible category — tool outputs — is code and patches.

Two cheaper routes were measured and rejected before building this:

- **Lossless normalisation** (trailing whitespace, blank-line collapsing):
  **0.03%** across 142 files, and not reliably AST-preserving.
- **`code_aware`**: drops ~a quarter of function-body statements while keeping
  signatures, and emitted **invalid Python on 16 of 100** real source files.
  For an agent reading a file in order to edit it, that is the worst possible
  failure. (That corruption is now caught by a router-level guard — see below.)

So this removes code only where it can remove it **visibly and reversibly**.

## Contracts

Enforced in code, pinned by 15 tests. Anything that cannot be guaranteed
returns the input unchanged.

1. **Output parses.** Re-parsed before return; discarded if not.
2. **Every elided body is retrievable** from CCR under the hash in its marker.
3. **The skeleton survives** — imports, decorators, signatures, annotations,
   docstrings, module-level code, and *nested* definitions. A body containing
   a nested `def` or `class` is never elided: the inner signature is skeleton
   too, and retrievability does not rescue it because the agent has to see
   that the inner function exists before it knows to retrieve anything.
   Measured on CodeSearchNet, the flat-fixture version of this cost 3
   signatures and 1 docstring across 47 compressions.
4. **Never inflates.**

The gap is self-describing, which is the whole point:

```python
def handler(request: dict, context: str) -> dict:
    """Handle the request."""
    # <cutctx:code_elided sha256=a1b2c3d4e5f6 lines=23> retrieve to view
    pass
```

## Measured

120 real source files:

| | |
| --- | ---: |
| Tokens | 451,181 → 221,571 |
| Saving on code | **50.9%** |
| CodeSearchNet mean ratio | 0.664 (signatures 46/46, docstrings 46/46) |
| Invalid syntax | 0 |
| Unretrievable markers | 0 |

Through the router on the same corpus: **3.7% → 13.8%** overall (source files
are not all code by volume).

## Economics of the retrieval round-trip

Eliding saves tokens now and costs them back if the agent retrieves. Measured
over 640 elided bodies:

| | Per body |
| --- | ---: |
| Mean body | 281 tokens |
| Marker + `pass` | 30 tokens |
| **Never retrieved** | **+251 saved (89.3%)** |
| **Every body retrieved** | −30 (**10.7% overhead**) |

The downside is bounded at ~11% and the upside is ~89%: an agent would have to
retrieve nearly nine of every ten elided bodies before this is a wash.

**Not counted:** each retrieval is a round-trip. The token arithmetic above
says nothing about the latency or the extra model turn, and nothing about
whether task success changes. That is the missing measurement.

## Prompt cache

Prefix-stable by construction — same code, same hash, same marker, and the
compressor holds no per-session state. Verified across repeated calls, fresh
instances, and a growing conversation.

This is the property semantic dedup lacked: its session hash index made an
earlier turn render differently on the next request, which invalidates the
cached prefix and costs roughly 8x what it saves when cache reads dominate the
bill. Code elision does not have that failure mode.

## Why it is off by default

Reversible code compression is enabled by default for new proxy processes.
Use `--no-reversible-code` or `CUTCTX_REVERSIBLE_CODE=0` to preserve the
previous pass-through behavior.

To change an already-running proxy without restarting it (and without closing
active Codex WebSockets), use the local admin configuration API:

```bash
curl -fsS -X POST http://127.0.0.1:8787/admin/config/flags \
  -H "X-Cutctx-Admin-Key: $CUTCTX_ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  --data '{"reversible_code":true}'
```

Set `false` in the same request for the immediate kill switch. The setting
affects only future compression decisions; it does not recreate pipelines,
restart the proxy, or interrupt a request already in flight.

Not because the economics are unclear — they are bounded and favourable — but
because code reaches the proxy through `Read`, `Grep` and `Bash`, which are on
`DEFAULT_EXCLUDE_TOOLS` precisely so "Cutctx cannot corrupt the payloads an
agent is most sensitive to". Turning this on by default would override that
stance for every user at once, on the strength of token arithmetic that does
not model round-trip latency or task success.

The honest gate for flipping the default is completion data, not token data.

## Measuring it on your own traffic

You do not need a task-set harness. Both signals are already recorded, so a
week with the flag on answers it:

```bash
cutctx proxy --enable-reversible-code        # or CUTCTX_REVERSIBLE_CODE=1
```

**Did it save anything?** Compression savings are attributed under
`cutctx_compression` in `cutctx perf` / the Savings page. Compare a week with
the flag against a week without. `reversible_code` also appears in
`strategy_chain` and in `transforms_applied` per request, so you can confirm
it is firing rather than inferring it from the total.

**Did it cost anything?** That is the number that decides the default. Every
retrieval is recorded in `retrieval_labels` (`~/.cutctx/episodes.db`):

```sql
SELECT COUNT(*) FROM retrieval_labels
WHERE timestamp_ts > strftime('%s','now','-7 days');
```

Compare against the count of elided bodies over the same window. The
break-even is ~89%: if the agent is retrieving fewer than roughly nine in ten
elided bodies, the flag is winning on tokens. Watch task behaviour alongside
it — a retrieval is a round-trip, and the token arithmetic does not price
latency or a lost train of thought.

If that comes back clean on your traffic, flipping the default is an
evidence-backed decision rather than a hopeful one. It is deliberately not
flipped here, because code arrives through tools this product explicitly
protects and one week of your data settles it better than any argument.
## Product-managed startup

CutCtx Control now installs a user-scoped, persistent product runtime the
first time it starts an idle proxy. The runtime carries
`--enable-reversible-code` and `CUTCTX_REVERSIBLE_CODE=1` explicitly, so a
package upgrade cannot silently fall back to an older default. The control
application first probes the configured local port: if it is healthy, it
attaches without restarting or interrupting active Codex WebSockets. The
managed service starts automatically at future login and restarts after an
unexpected exit.
