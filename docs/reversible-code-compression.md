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

`--enable-reversible-code` / `CUTCTX_REVERSIBLE_CODE=1`.

Not because the economics are unclear — they are bounded and favourable — but
because code reaches the proxy through `Read`, `Grep` and `Bash`, which are on
`DEFAULT_EXCLUDE_TOOLS` precisely so "Cutctx cannot corrupt the payloads an
agent is most sensitive to". Turning this on by default would override that
stance for every user at once, on the strength of token arithmetic that does
not model round-trip latency or task success.

The honest gate for flipping the default is one experiment: run a real coding
agent through a task set with the flag on and off, and compare completion
rather than tokens. Until someone runs it, this ships as a measured option
rather than a new default.
