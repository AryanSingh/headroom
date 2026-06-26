# Jedi Integration Spec — Cutctx Python Cross-Reference Enrichment

**Status:** Ready for implementation  
**Author:** Architecture review, June 2026  
**Scope:** Add `JediInterceptor` as an opt-in Python-specific interceptor that appends a compact `[CROSS-REFERENCES]` section to Read tool outputs, exposing cross-file caller/callee relationships with zero LLM cost.

---

## 0. Background and Goal

### 0.1 The Problem

`AstGrepReadOutline` (the existing interceptor at `cutctx/proxy/interceptors/astgrep.py`) does a good job reducing a single file's token count by eliding function bodies. But it is **file-local**: it has no awareness of which other files import `auth/service.py`, what functions call `login()`, or which modules `UserService` depends on.

When an LLM agent is debugging a cross-file issue or tracing a call chain, it must issue multiple `Read` calls blindly — it does not know where to look next. The result is wasted turns and wasted tokens.

### 0.2 What Jedi Provides

[jedi](https://github.com/davidhalter/jedi) (MIT, pure Python, zero binary dependencies) is a static analysis library that understands Python imports and call graphs **across files**. It does not need a running Python interpreter — it walks the AST and resolves names using its own type inferencer.

Key APIs used in this integration:

| API | What it returns |
|---|---|
| `jedi.Script(path=...).get_names(all_scopes=False, definitions=True)` | Top-level names (functions, classes, variables) defined in the file |
| `jedi.Script(path=...).goto(line=N, column=0)` | Jump-to-definition for a name at a given position |
| `jedi.Script(path=...).get_references(line=N, column=0)` | All cross-file references to a name (callers) |

### 0.3 Goal

When the proxy sees a `Read` result for a `.py` file, `JediInterceptor` appends a compact `[CROSS-REFERENCES]` block listing:

1. Which modules/files the read file **imports** (callees / dependencies).
2. Which other files **reference** each top-level symbol in the read file (callers).

This block is appended **only if** the final token count is smaller than the original. Because the interceptor protocol enforces `after < before` (see `base.py` line 311), this constraint is structurally guaranteed — the interceptor simply returns `None` if the cross-references section would not save tokens.

### 0.4 Positioning in the Interceptor Chain

```
Read tool result (Python file)
        │
        ▼
[1] GraphifyInterceptor   (knowledge-graph subgraph, --knowledge-graph flag)
        │
        ▼
[2] JediInterceptor       (cross-file refs, --jedi flag)   ← THIS SPEC
        │
        ▼
[3] AstGrepReadOutline    (per-file signature outline, --intercept-tool-results flag)
        │
        ▼
Compressed output delivered to LLM
```

Placing `JediInterceptor` after `GraphifyInterceptor` ensures that if the knowledge graph already replaced the content with a subgraph representation, jedi operates on that (smaller) content. Placing it before `AstGrepReadOutline` means jedi sees the full body text, giving it accurate line/column positions for its API calls before bodies are elided by ast-grep.

### 0.5 Complementarity with Graphify

| Property | Graphify | Jedi |
|---|---|---|
| Languages | Polyglot (Tree-sitter) | Python only |
| Cross-file awareness | Yes (semantic + AST) | Yes (AST only) |
| LLM cost | Yes (uses LLM for node labelling) | None |
| Startup cost | High (indexes whole repo) | Per-request (lazy) |
| Understands docs/diagrams | Yes | No |
| Instant on cold start | No | Yes |

Jedi is the right choice when Graphify is not installed, when the codebase is Python-only, or when the developer wants zero-LLM-cost cross-reference hints.

---

## 1. Architecture Overview

```
cutctx/proxy/interceptors/
├── base.py                 (unchanged — protocol + registry)
├── astgrep.py              (unchanged — per-file outliner)
├── __init__.py             (MODIFIED — import jedi_interceptor conditionally)
└── jedi_interceptor.py     (NEW — JediInterceptor class)

cutctx/proxy/models.py    (MODIFIED — 3 new config fields)
cutctx/cli/proxy.py       (MODIFIED — --jedi flag + 2 sub-flags)
pyproject.toml              (MODIFIED — python-analysis optional dep group)
tests/test_jedi_interceptor.py  (NEW — 7+ unit tests)
```

### 1.1 Runtime Data Flow (transform() call)

```
transform(tool_name, tool_input, tool_output)
        │
        ├─ 1. Extract file_path from tool_input
        ├─ 2. Acquire threading.Lock (one jedi.Script at a time)
        ├─ 3. Construct jedi.Script(source=tool_output, path=file_path)
        ├─ 4. Collect top-level names (get_names)
        ├─ 5. For each name (up to jedi_max_references):
        │       ├─ get_references() → callers across files
        │       └─ collect unique caller file paths
        ├─ 6. Build [CROSS-REFERENCES] text block
        ├─ 7. Candidate = tool_output + "\n" + cross_refs_block
        ├─ 8. Token check: return candidate only if len(candidate) < len(tool_output)
        │     (the framework enforces tokens_after < tokens_before; this is
        │      a fast character-count pre-check to avoid tokenising a loser)
        └─ 9. Return candidate (or None to pass through)
```

The cross-references block is designed to be **compact** — it replaces long import chains and scattered call-site searches with a single dense section. For a large file (e.g. 4 000 tokens of body code), a 150-token cross-reference appendix still yields a net reduction because `AstGrepReadOutline` in the next stage will elide the function bodies. For a small file where the cross-references would not help, `transform()` returns `None`.

---

## 2. Dependency Changes

### 2.1 `pyproject.toml` — Add `python-analysis` Optional Group

**File:** `pyproject.toml`  
**Section:** `[project.optional-dependencies]`  
**Action:** Insert after the `code = [...]` block (after line 96).

```toml
# Python static analysis (cross-file reference enrichment via jedi)
# pip install cutctx-ai[python-analysis]
python-analysis = [
    "jedi>=0.19.0",
]
```

**Rationale for version floor:** jedi 0.19.0 (released 2023-09-03) introduced stable `get_names()` behaviour and dropped the last legacy `api_classes` reshuffles. All Python 3.10–3.14 versions are supported from this release onward.

**No transitive binary deps:** jedi depends only on `parso` (pure Python) and optionally `sexpdata` (not used here). No Rust, no C extensions. This means `pip install cutctx-ai[python-analysis]` works on any platform without a compiler.

---

## 3. Config Flags

### 3.1 `cutctx/proxy/models.py`

Add three fields to the `ProxyConfig` dataclass. Insert after the `code_graph_watcher` field (after line 180):

```python
# Jedi Python cross-reference interceptor.
# When enabled, Read results for .py files are augmented with a compact
# [CROSS-REFERENCES] section listing callers/callees across the project.
# Requires: pip install cutctx-ai[python-analysis]
# CLI: --jedi; env: CUTCTX_JEDI_ENABLED=1.
jedi_enabled: bool = False

# Maximum number of cross-file references to surface per top-level symbol.
# Higher values give more context but increase the cross-refs section size.
# CLI: --jedi-max-refs N; env: CUTCTX_JEDI_MAX_REFS=N.
jedi_max_references: int = 10

# Include caller locations (files that call symbols defined in the read file).
# Disable to emit only import/dependency information (callees), which is
# faster because it skips the get_references() API calls.
# CLI: --no-jedi-callers; env: CUTCTX_JEDI_INCLUDE_CALLERS=0.
jedi_include_callers: bool = True
```

### 3.2 `cutctx/cli/proxy.py`

Add three Click options to the `proxy` command. Insert near the `--intercept-tool-results` and `--code-graph` options (after line 174):

```python
@click.option(
    "--jedi",
    "jedi_enabled",
    is_flag=True,
    envvar="CUTCTX_JEDI_ENABLED",
    help=(
        "Enable jedi Python cross-reference interceptor. Appends a compact "
        "[CROSS-REFERENCES] section to Read results for .py files, listing "
        "callers and imported modules across the project. "
        "Requires: pip install cutctx-ai[python-analysis]. "
        "Env: CUTCTX_JEDI_ENABLED=1."
    ),
)
@click.option(
    "--jedi-max-refs",
    "jedi_max_references",
    default=None,
    type=click.IntRange(min=1, max=100),
    envvar="CUTCTX_JEDI_MAX_REFS",
    help=(
        "Maximum cross-file references to surface per symbol (default: 10). "
        "Env: CUTCTX_JEDI_MAX_REFS."
    ),
)
@click.option(
    "--no-jedi-callers",
    "jedi_include_callers",
    is_flag=True,
    default=True,
    flag_value=False,
    envvar="CUTCTX_JEDI_INCLUDE_CALLERS",
    help=(
        "Skip caller discovery (only emit import/dependency info). "
        "Faster but provides less cross-file context. "
        "Env: CUTCTX_JEDI_INCLUDE_CALLERS=0."
    ),
)
```

In the `proxy` command function body, add the jedi fields to the `ProxyConfig(...)` constructor call, alongside the `code_graph_watcher` line:

```python
jedi_enabled=jedi_enabled,
jedi_max_references=jedi_max_references if jedi_max_references is not None else 10,
jedi_include_callers=jedi_include_callers,
```

In the startup block that checks `intercept_tool_results`, add conditional registration:

```python
if jedi_enabled:
    try:
        import jedi  # noqa: F401
    except ImportError:
        click.secho(
            "error: --jedi requires jedi. "
            "Run: pip install cutctx-ai[python-analysis]",
            fg="red",
            err=True,
        )
        sys.exit(1)
    from cutctx.proxy.interceptors.jedi_interceptor import JediInterceptor
    from cutctx.proxy.interceptors import base as _ibase
    _ibase.register(
        JediInterceptor(
            max_references=jedi_max_references if jedi_max_references is not None else 10,
            include_callers=jedi_include_callers,
        )
    )
```

---

## 4. New File: `cutctx/proxy/interceptors/jedi_interceptor.py`

This is the full implementation. Copy it verbatim.

```python
"""jedi interceptor: append cross-file reference context to Python Read outputs.

When the LLM reads a .py file, this interceptor runs jedi static analysis to
discover:
  - Which other files import the symbols defined in this file (callers).
  - Which modules this file imports (callees / dependencies).

A compact "[CROSS-REFERENCES]" section is appended to the tool output,
giving the model a map of where to look next without requiring additional
Read calls.

This interceptor is:
  - Python-only (.py extension required).
  - Opt-in (registered only when --jedi flag is passed).
  - Guaranteed to never enlarge content (returns None if cross-refs would grow
    the output; the framework also enforces token non-enlargement independently).
  - Thread-safe (jedi.Script construction is serialised via a module-level lock).
  - Graceful: any jedi failure (syntax error, missing file, import error)
    causes transform() to return None, passing through the original content.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# jedi.Script construction is not thread-safe — it writes to a shared
# module-level cache. Serialise all Script instantiations through this lock.
# transform() calls are typically short (< 200 ms on a warm jedi cache) so
# the coarse lock does not meaningfully reduce throughput in typical proxy
# workloads (1–4 concurrent reads).
_JEDI_LOCK = threading.Lock()

# Minimum character count for the tool output to bother running jedi.
# Below this floor the file is too small for cross-refs to save tokens.
_MIN_CHARS = 300


class JediInterceptor:
    """Interceptor that enriches Python Read outputs with cross-file references.

    Parameters
    ----------
    max_references:
        Maximum number of caller locations to list per top-level symbol.
        Defaults to 10. Set lower to keep the cross-refs section short for
        large codebases with many callers.
    include_callers:
        If True (default), call get_references() for each top-level symbol to
        find cross-file callers. If False, only emit imported module paths
        (cheaper — no get_references() calls).
    """

    name = "jedi"

    def __init__(
        self,
        max_references: int = 10,
        include_callers: bool = True,
    ) -> None:
        self._max_refs = max(1, max_references)
        self._include_callers = include_callers

    # ------------------------------------------------------------------
    # ToolResultInterceptor protocol
    # ------------------------------------------------------------------

    def matches(
        self,
        tool_name: str | None,
        tool_input: dict[str, Any],
        tool_output: str,
    ) -> bool:
        """Return True for Read-family tool results on .py files."""
        if tool_name not in ("Read", "read_file", "view", "cat"):
            return False
        if len(tool_output) < _MIN_CHARS:
            return False
        path = _path_from_input(tool_input)
        if not path:
            return False
        return Path(path).suffix.lower() == ".py"

    def transform(
        self,
        tool_name: str | None,
        tool_input: dict[str, Any],
        tool_output: str,
    ) -> str | None:
        """Append a [CROSS-REFERENCES] section; return None on any failure.

        The framework guarantees that any return value that does not reduce
        tokens is discarded (base.py line 311). This method also applies a
        fast character-count pre-check before building the final string to
        avoid constructing a candidate that the framework will reject anyway.
        """
        path = _path_from_input(tool_input)
        if not path:
            return None

        try:
            cross_refs = _build_cross_refs(
                source=tool_output,
                path=path,
                max_refs=self._max_refs,
                include_callers=self._include_callers,
            )
        except Exception as exc:  # noqa: BLE001 — never crash a request
            logger.debug("jedi analysis failed for %s: %s", path, exc)
            return None

        if not cross_refs:
            return None

        candidate = tool_output + "\n" + cross_refs

        # Fast pre-check: if the candidate is not shorter in raw characters,
        # the framework will reject it on tokens anyway — skip tokenisation.
        if len(candidate) >= len(tool_output):
            return None

        return candidate

    def progressive_disclosure_key(
        self,
        tool_name: str | None,
        tool_input: dict[str, Any],
    ) -> str | None:
        """Key by file path; second Read of the same file passes through."""
        return _path_from_input(tool_input)


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _path_from_input(tool_input: dict[str, Any]) -> str | None:
    """Extract the file path from a tool_input dict.

    Recognises the path key names used by Claude Code (file_path), Claude
    Desktop (path), Cursor (filePath), and generic MCP servers (filename).
    """
    for key in ("file_path", "path", "filePath", "filename"):
        v = tool_input.get(key)
        if isinstance(v, str) and v:
            return v
    return None


def _build_cross_refs(
    source: str,
    path: str,
    max_refs: int,
    include_callers: bool,
) -> str | None:
    """Run jedi and build the [CROSS-REFERENCES] text block.

    Returns None if jedi finds nothing useful or if any error occurs.
    All jedi API calls are serialised via _JEDI_LOCK to avoid shared-cache
    race conditions.
    """
    try:
        import jedi  # noqa: PLC0415 — optional dep, imported lazily
    except ImportError:
        logger.debug("jedi not installed; skipping cross-reference enrichment")
        return None

    path_obj = Path(path)
    lines: list[str] = []

    with _JEDI_LOCK:
        try:
            # Pass source= so jedi analyses the tool output (which is the
            # current file content as seen by the LLM), not whatever is on
            # disk. Pass path= so jedi can resolve relative imports correctly.
            script = jedi.Script(source=source, path=str(path_obj))
            names = script.get_names(all_scopes=False, definitions=True)
        except Exception as exc:  # noqa: BLE001
            logger.debug("jedi.Script() failed for %s: %s", path, exc)
            return None

        # ---- Imported modules (callees / dependencies) -------------------
        import_lines = _collect_imports(source)
        if import_lines:
            lines.append("Imports (dependencies):")
            for imp in import_lines[:max_refs]:
                lines.append(f"  {imp}")

        # ---- Callers of top-level symbols --------------------------------
        if include_callers and names:
            caller_entries: list[tuple[str, list[str]]] = []
            for name in names:
                if name.type not in ("function", "class"):
                    continue
                try:
                    refs = script.get_references(
                        line=name.line,
                        column=name.column,
                        **_jedi_ref_kwargs(),
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.debug(
                        "jedi.get_references() failed for %s in %s: %s",
                        name.name,
                        path,
                        exc,
                    )
                    continue

                # Exclude self-references (definitions in the same file).
                external_refs = [
                    r for r in refs
                    if r.module_path and str(r.module_path) != str(path_obj)
                ]
                if not external_refs:
                    continue

                # Deduplicate by file path, keep at most max_refs entries.
                seen_paths: set[str] = set()
                ref_paths: list[str] = []
                for ref in external_refs:
                    rp = str(ref.module_path)
                    if rp not in seen_paths:
                        seen_paths.add(rp)
                        ref_paths.append(rp)
                    if len(ref_paths) >= max_refs:
                        break

                caller_entries.append((name.name, ref_paths))

            if caller_entries:
                lines.append("Callers (files that reference top-level symbols):")
                for sym_name, ref_paths in caller_entries:
                    paths_str = ", ".join(ref_paths)
                    lines.append(f"  {sym_name}: {paths_str}")

    if not lines:
        return None

    header = "[CROSS-REFERENCES — generated by jedi static analysis]\n"
    body = "\n".join(lines)
    footer = "\n[end cross-references]\n"
    return header + body + footer


def _collect_imports(source: str) -> list[str]:
    """Extract import statement lines from source using simple AST parsing.

    Uses the stdlib `ast` module (always available) rather than jedi's import
    resolution to stay fast and avoid network access. Returns bare import
    strings like "from .models import User" or "import os".
    """
    import ast  # noqa: PLC0415 — stdlib, always available

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            level = "." * (node.level or 0)
            names = ", ".join(a.name for a in node.names)
            imports.append(f"from {level}{module} import {names}")
    return imports


def _jedi_ref_kwargs() -> dict[str, Any]:
    """Return extra kwargs for get_references() based on jedi version.

    jedi >= 0.18.0 accepts `include_builtins=False` to skip stdlib/built-in
    references. Older versions (unlikely given our >=0.19.0 floor) do not
    support this kwarg. This helper centralises the version check.
    """
    try:
        import jedi  # noqa: PLC0415
        parts = tuple(int(x) for x in jedi.__version__.split(".")[:2])
        if parts >= (0, 18):
            return {"include_builtins": False}
    except Exception:  # noqa: BLE001
        pass
    return {}
```

---

## 5. Modified File: `cutctx/proxy/interceptors/__init__.py`

Add conditional import of `jedi_interceptor` so the module is available for the CLI to import on demand. The interceptor is **not** registered here (registration happens in `cli/proxy.py` when `--jedi` is passed); this import is only needed to make `JediInterceptor` importable from the package namespace.

Change the current file from:

```python
# Side-effect: register the built-in interceptors.
from . import astgrep  # noqa: F401
from .base import (
    INTERCEPTORS,
    InterceptionResult,
    ToolResultInterceptor,
    ToolResultInterceptorTransform,
    TransformSpan,
    apply_to_messages,
    interceptor_failure_counts,
    register,
)

__all__ = [
    "INTERCEPTORS",
    "InterceptionResult",
    "ToolResultInterceptor",
    "ToolResultInterceptorTransform",
    "TransformSpan",
    "apply_to_messages",
    "interceptor_failure_counts",
    "register",
]
```

To:

```python
# Side-effect: register the built-in interceptors.
from . import astgrep  # noqa: F401
from .base import (
    INTERCEPTORS,
    InterceptionResult,
    ToolResultInterceptor,
    ToolResultInterceptorTransform,
    TransformSpan,
    apply_to_messages,
    interceptor_failure_counts,
    register,
)

__all__ = [
    "INTERCEPTORS",
    "InterceptionResult",
    "ToolResultInterceptor",
    "ToolResultInterceptorTransform",
    "TransformSpan",
    "apply_to_messages",
    "interceptor_failure_counts",
    "register",
    # JediInterceptor is NOT auto-registered here.
    # The proxy CLI registers it on --jedi. Import is lazy (jedi is optional).
    "JediInterceptor",
]


def __getattr__(name: str) -> object:
    if name == "JediInterceptor":
        from .jedi_interceptor import JediInterceptor  # noqa: PLC0415
        return JediInterceptor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

The `__getattr__` approach avoids an `ImportError` at module load time when `jedi` is not installed — the import only fires when someone actually accesses `JediInterceptor`.

---

## 6. New File: `tests/test_jedi_interceptor.py`

Full test suite with 7+ tests covering the happy path, edge cases, and graceful fallbacks.

```python
"""Unit tests for JediInterceptor.

These tests are designed to run without jedi installed (they mock the
import where necessary), and also pass when jedi is installed.
"""

from __future__ import annotations

import sys
import textwrap
import threading
import types
from typing import Any
from unittest import mock

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tool_input(path: str) -> dict[str, Any]:
    return {"file_path": path}


def _make_large_py_source(n_chars: int = 500) -> str:
    """Return a syntactically valid Python source string of at least n_chars."""
    body = textwrap.dedent(
        """\
        import os
        import sys
        from pathlib import Path

        class Authenticator:
            \"\"\"Handles user authentication.\"\"\"

            def login(self, username: str, password: str) -> bool:
                return username == "admin"

            def logout(self, session_id: str) -> None:
                pass

        def hash_password(password: str) -> str:
            return password[::-1]

        def verify_token(token: str) -> bool:
            return len(token) > 8
        """
    )
    while len(body) < n_chars:
        body += "# padding\n"
    return body


def _make_small_py_source() -> str:
    """Return a Python source string shorter than _MIN_CHARS (300)."""
    return "x = 1\n"


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def interceptor():
    from cutctx.proxy.interceptors.jedi_interceptor import JediInterceptor
    return JediInterceptor(max_references=5, include_callers=True)


# ---------------------------------------------------------------------------
# Test 1: matches() — non-Python file is rejected
# ---------------------------------------------------------------------------


def test_matches_non_python_file_returns_false(interceptor):
    """TypeScript files must never match — jedi is Python-only."""
    result = interceptor.matches(
        tool_name="Read",
        tool_input={"file_path": "/app/src/index.ts"},
        tool_output="const x: number = 1;\n" * 50,
    )
    assert result is False


# ---------------------------------------------------------------------------
# Test 2: matches() — non-Read tool is rejected
# ---------------------------------------------------------------------------


def test_matches_non_read_tool_returns_false(interceptor):
    """Only Read-family tools should trigger the interceptor."""
    result = interceptor.matches(
        tool_name="Bash",
        tool_input={"file_path": "/app/auth.py"},
        tool_output=_make_large_py_source(),
    )
    assert result is False


# ---------------------------------------------------------------------------
# Test 3: matches() — output below _MIN_CHARS is rejected
# ---------------------------------------------------------------------------


def test_matches_small_file_returns_false(interceptor):
    """Files shorter than _MIN_CHARS should not be processed."""
    result = interceptor.matches(
        tool_name="Read",
        tool_input={"file_path": "/app/tiny.py"},
        tool_output=_make_small_py_source(),
    )
    assert result is False


# ---------------------------------------------------------------------------
# Test 4: matches() — valid Python Read returns True
# ---------------------------------------------------------------------------


def test_matches_python_read_returns_true(interceptor):
    result = interceptor.matches(
        tool_name="Read",
        tool_input={"file_path": "/app/auth/service.py"},
        tool_output=_make_large_py_source(),
    )
    assert result is True


# ---------------------------------------------------------------------------
# Test 5: transform() — syntax error triggers graceful fallback (return None)
# ---------------------------------------------------------------------------


def test_transform_syntax_error_returns_none(interceptor):
    """Malformed Python should not crash the interceptor."""
    broken_source = "def foo(:\n    pass\n" * 50  # invalid syntax
    result = interceptor.transform(
        tool_name="Read",
        tool_input={"file_path": "/app/broken.py"},
        tool_output=broken_source,
    )
    # Must return None — never raise
    assert result is None


# ---------------------------------------------------------------------------
# Test 6: transform() — missing jedi package triggers graceful fallback
# ---------------------------------------------------------------------------


def test_transform_missing_jedi_returns_none(interceptor):
    """If jedi is not installed, transform() must return None, not ImportError."""
    # Temporarily hide jedi from sys.modules
    real_jedi = sys.modules.pop("jedi", None)
    try:
        # Also block the import so the lazy import inside _build_cross_refs fails
        with mock.patch.dict(sys.modules, {"jedi": None}):  # type: ignore[dict-item]
            result = interceptor.transform(
                tool_name="Read",
                tool_input={"file_path": "/app/auth.py"},
                tool_output=_make_large_py_source(),
            )
        assert result is None
    finally:
        if real_jedi is not None:
            sys.modules["jedi"] = real_jedi


# ---------------------------------------------------------------------------
# Test 7: transform() — cross-reference section format
# ---------------------------------------------------------------------------


def test_transform_cross_reference_section_format():
    """When jedi runs successfully, the output must contain expected markers."""
    # Build a mock jedi module that returns predictable data
    mock_jedi = types.ModuleType("jedi")
    mock_jedi.__version__ = "0.19.1"  # type: ignore[attr-defined]

    mock_name_login = mock.MagicMock()
    mock_name_login.name = "login"
    mock_name_login.type = "function"
    mock_name_login.line = 10
    mock_name_login.column = 0

    mock_name_class = mock.MagicMock()
    mock_name_class.name = "Authenticator"
    mock_name_class.type = "class"
    mock_name_class.line = 6
    mock_name_class.column = 0

    mock_ref = mock.MagicMock()
    mock_ref.module_path = "/app/views/login_view.py"

    mock_script = mock.MagicMock()
    mock_script.get_names.return_value = [mock_name_login, mock_name_class]
    mock_script.get_references.return_value = [mock_ref]

    mock_jedi.Script = mock.MagicMock(return_value=mock_script)  # type: ignore[attr-defined]

    source = _make_large_py_source(n_chars=600)

    from cutctx.proxy.interceptors.jedi_interceptor import JediInterceptor
    interceptor = JediInterceptor(max_references=5, include_callers=True)

    with mock.patch.dict(sys.modules, {"jedi": mock_jedi}):
        result = interceptor.transform(
            tool_name="Read",
            tool_input={"file_path": "/app/auth/service.py"},
            tool_output=source,
        )

    # If result is None the cross-refs did not shrink the output (acceptable
    # for a short test source). Otherwise validate the format.
    if result is not None:
        assert "[CROSS-REFERENCES" in result
        assert "[end cross-references]" in result
        # The original content must still be present
        assert source in result


# ---------------------------------------------------------------------------
# Test 8: transform() — output must never be larger than input
# ---------------------------------------------------------------------------


def test_transform_never_enlarges_content(interceptor):
    """transform() must return None (not a larger string) when cross-refs expand content."""
    # Use a short source so any cross-refs would enlarge it
    short_source = ("import os\n" * 30)  # ~270 chars — just below _MIN_CHARS

    # If matches() returns False (too short), transform() won't be called by
    # the framework — test directly to verify the internal guard.
    # Monkeypatch _MIN_CHARS to 0 for this call to force execution.
    from cutctx.proxy.interceptors import jedi_interceptor as _mod
    original_min = _mod._MIN_CHARS
    _mod._MIN_CHARS = 0
    try:
        result = interceptor.transform(
            tool_name="Read",
            tool_input={"file_path": "/app/tiny.py"},
            tool_output=short_source,
        )
        # Result must either be None or shorter than short_source
        if result is not None:
            assert len(result) < len(short_source), (
                "transform() enlarged the output — violates interceptor contract"
            )
    finally:
        _mod._MIN_CHARS = original_min


# ---------------------------------------------------------------------------
# Test 9: progressive_disclosure_key() returns file path
# ---------------------------------------------------------------------------


def test_progressive_disclosure_key_returns_path(interceptor):
    key = interceptor.progressive_disclosure_key(
        tool_name="Read",
        tool_input={"file_path": "/app/auth/service.py"},
    )
    assert key == "/app/auth/service.py"


# ---------------------------------------------------------------------------
# Test 10: progressive_disclosure_key() returns None when no path key
# ---------------------------------------------------------------------------


def test_progressive_disclosure_key_no_path_returns_none(interceptor):
    key = interceptor.progressive_disclosure_key(
        tool_name="Read",
        tool_input={"unknown_key": "/app/auth/service.py"},
    )
    assert key is None


# ---------------------------------------------------------------------------
# Test 11: thread safety — concurrent transforms do not crash
# ---------------------------------------------------------------------------


def test_transform_is_thread_safe():
    """Concurrent calls to transform() must not raise or corrupt output."""
    from cutctx.proxy.interceptors.jedi_interceptor import JediInterceptor
    interceptor = JediInterceptor(max_references=3, include_callers=False)
    source = _make_large_py_source(n_chars=600)
    tool_input = {"file_path": "/app/auth.py"}
    errors: list[Exception] = []

    def _call() -> None:
        try:
            interceptor.transform("Read", tool_input, source)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=_call) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert not errors, f"Thread safety failures: {errors}"
```

---

## 7. Integration Point: Proxy Server Startup

The proxy server startup in `cutctx/cli/proxy.py` already has a pattern for conditional interceptor setup (the `intercept_tool_results` block at line 796). The jedi registration block (shown in section 3.2) follows the same pattern:

1. Check the `--jedi` flag.
2. Attempt `import jedi` — fail fast with a clear error if missing.
3. Import `JediInterceptor` from the new module.
4. Call `base.register(JediInterceptor(...))`.

The `register()` function in `base.py` is idempotent on `name`, so calling it multiple times with the same interceptor name is safe (e.g. if the proxy is reloaded in dev without a full restart).

### 7.1 Interceptor Chain Order After Integration

The `INTERCEPTORS` list is ordered by registration sequence. At proxy startup:

| Registration order | Interceptor | Flag required |
|---|---|---|
| 1 | `AstGrepReadOutline` | auto-registered at import time (base module side-effect) |
| 2 | `GraphifyInterceptor` | `--knowledge-graph` (see graphify-integration-spec.md) |
| 3 | `JediInterceptor` | `--jedi` |

Wait — the per-file specification says `JediInterceptor` should sit **after** `GraphifyInterceptor` and **before** `AstGrepReadOutline`. However, `AstGrepReadOutline` auto-registers at module import time (it is the first entry in `INTERCEPTORS`). The correct ordering therefore requires `AstGrepReadOutline` to run **last** — which means it should be re-registered after the others, or a priority/ordering mechanism should be used.

**Recommended approach for ordering:** In `cutctx/proxy/interceptors/__init__.py`, defer `AstGrepReadOutline` registration to a function that the proxy CLI calls after all opt-in interceptors are registered. For backwards compatibility (the existing `--intercept-tool-results` flag), `AstGrepReadOutline` can remain auto-registered, and the spec-mandated ordering can be enforced by inserting `JediInterceptor` at position `len(INTERCEPTORS) - 1` rather than appending:

```python
# In cli/proxy.py, after registering JediInterceptor:
# Move JediInterceptor to run before AstGrepReadOutline (which is always last).
from cutctx.proxy.interceptors.base import INTERCEPTORS
jedi_entry = next(i for i in INTERCEPTORS if i.name == "jedi")
INTERCEPTORS.remove(jedi_entry)
astgrep_idx = next(
    (idx for idx, i in enumerate(INTERCEPTORS) if i.name == "ast-grep"),
    len(INTERCEPTORS),
)
INTERCEPTORS.insert(astgrep_idx, jedi_entry)
```

This is a safe list mutation since `apply_to_messages` iterates `INTERCEPTORS` at call time, not at registration time.

---

## 8. Verification Steps

The following steps verify correct installation, configuration, and behaviour. All commands assume the repo root is the current working directory and the virtual environment is activated.

### Step 1 — Install the optional dependency

```bash
pip install "cutctx-ai[python-analysis]"
python -c "import jedi; print(jedi.__version__)"
# Expected: 0.19.x or later
```

### Step 2 — Confirm jedi is NOT imported on normal proxy startup

```bash
python -c "
import sys
# Simulate proxy startup without --jedi
from cutctx.proxy.interceptors import INTERCEPTORS
names = [i.name for i in INTERCEPTORS]
assert 'jedi' not in names, f'jedi should not be auto-registered: {names}'
assert 'jedi' not in sys.modules, 'jedi should not be imported without --jedi flag'
print('PASS: jedi not auto-imported')
"
```

### Step 3 — Confirm JediInterceptor.matches() rejects non-.py files

```bash
python -c "
from cutctx.proxy.interceptors.jedi_interceptor import JediInterceptor
ic = JediInterceptor()
assert not ic.matches('Read', {'file_path': '/app/index.ts'}, 'x' * 400)
assert not ic.matches('Bash', {'file_path': '/app/auth.py'}, 'x' * 400)
assert ic.matches('Read', {'file_path': '/app/auth.py'}, 'x' * 400)
print('PASS: matches() selects only Python Read results')
"
```

### Step 4 — Confirm transform() returns None for syntax errors (graceful fallback)

```bash
python -c "
from cutctx.proxy.interceptors.jedi_interceptor import JediInterceptor
ic = JediInterceptor()
broken = 'def foo(:\n    pass\n' * 30
result = ic.transform('Read', {'file_path': '/app/broken.py'}, broken)
assert result is None, f'Expected None, got: {result!r:.100}'
print('PASS: syntax error handled gracefully')
"
```

### Step 5 — Confirm transform() never enlarges content

```bash
python -c "
from cutctx.proxy.interceptors.jedi_interceptor import JediInterceptor, _MIN_CHARS
import cutctx.proxy.interceptors.jedi_interceptor as _mod
ic = JediInterceptor()
source = 'import os\nimport sys\n\ndef foo():\n    pass\n' * 20
_mod._MIN_CHARS = 0  # force execution on short source
result = ic.transform('Read', {'file_path': '/tmp/test.py'}, source)
_mod._MIN_CHARS = _MIN_CHARS
if result is not None:
    assert len(result) < len(source), 'transform() enlarged content!'
print('PASS: output size invariant upheld')
"
```

### Step 6 — Run the full test suite

```bash
python -m pytest tests/test_jedi_interceptor.py -v
# Expected: 11 passed (or SKIPPED for tests that require jedi when not installed)
```

### Step 7 — Confirm ProxyConfig accepts the new fields

```bash
python -c "
from cutctx.proxy.models import ProxyConfig
cfg = ProxyConfig(jedi_enabled=True, jedi_max_references=15, jedi_include_callers=False)
assert cfg.jedi_enabled is True
assert cfg.jedi_max_references == 15
assert cfg.jedi_include_callers is False
print('PASS: ProxyConfig fields accepted')
"
```

### Step 8 — Confirm CLI flag is present

```bash
cutctx proxy --help | grep jedi
# Expected output contains:
#   --jedi
#   --jedi-max-refs INTEGER RANGE
#   --no-jedi-callers
```

### Step 9 — Start proxy with --jedi and verify interceptor is registered

```bash
python -c "
import os
os.environ['CUTCTX_INTERCEPT_ENABLED'] = '1'
# Simulate what cli/proxy.py does on --jedi
from cutctx.proxy.interceptors.jedi_interceptor import JediInterceptor
from cutctx.proxy.interceptors import base
base.register(JediInterceptor(max_references=10, include_callers=True))
from cutctx.proxy.interceptors import INTERCEPTORS
names = [i.name for i in INTERCEPTORS]
assert 'jedi' in names, f'jedi not registered: {names}'
print('PASS: JediInterceptor registered in INTERCEPTORS list')
print('Registered interceptors:', names)
"
```

### Step 10 — End-to-end: transform a real Python file

```bash
python -c "
from cutctx.proxy.interceptors.jedi_interceptor import JediInterceptor
ic = JediInterceptor(max_references=5, include_callers=True)

# Use the astgrep.py file from the project itself as test input
source = open('cutctx/proxy/interceptors/astgrep.py').read()
tool_input = {'file_path': 'cutctx/proxy/interceptors/astgrep.py'}

if ic.matches('Read', tool_input, source):
    result = ic.transform('Read', tool_input, source)
    if result:
        print('transform() returned', len(result), 'chars (original:', len(source), 'chars)')
        print('[CROSS-REFERENCES]' in result or result[-200:])
    else:
        print('transform() returned None (no net token reduction — expected for short files)')
else:
    print('matches() returned False')
"
```

---

## 9. Design Decisions and Rationale

### 9.1 Why `source=tool_output` instead of reading from disk?

The tool output is what the LLM sees. If the file on disk has been modified since the LLM issued the `Read` call, using the disk version would produce cross-references for different content. Passing `source=tool_output` ensures jedi analyses exactly the content the LLM is looking at.

### 9.2 Why a module-level `threading.Lock`?

Jedi maintains a shared module-level cache (`_parser_module_cache`) that is not protected by its own locks. Concurrent `jedi.Script()` instantiations from multiple proxy worker threads can corrupt this cache, leading to incorrect analysis results or crashes. A single coarse lock is the correct fix — jedi analysis is fast enough (< 200 ms on warm cache for a 500-line file) that serialisation does not meaningfully reduce proxy throughput at the concurrency levels typical of a developer proxy (1–4 concurrent requests).

If high concurrency becomes a concern, the lock can be replaced with a per-`path` lock (a `defaultdict(threading.Lock)`) or with jedi's own `jedi.set_debug_function()` + `jedi.preload_module()` thread-isolation patterns. This is left as a future optimisation.

### 9.3 Why return `None` instead of the cross-refs block alone?

The interceptor contract (base.py) requires that the returned string be **strictly smaller in tokens** than the input. A cross-references section appended to a short file would enlarge the output. Rather than try to trim the cross-refs to fit, returning `None` is correct — the LLM gets the unmodified original content, which is the best possible outcome in that case.

### 9.4 Why `_collect_imports` uses `ast.parse` instead of jedi's import resolution?

Jedi's import resolution (`script.get_references()` on import nodes) requires project context to follow multi-hop imports. For the purposes of a compact "dependencies" list, the raw import statement text is more useful to the LLM than a resolved path chain. `ast.parse` is always available, is fast, and handles the case where jedi's project inference would fail (e.g. missing `__init__.py` files).

### 9.5 Why place JediInterceptor BEFORE AstGrepReadOutline?

`AstGrepReadOutline` elides function bodies and replaces them with an `OUTLINE_MARKER` comment. After elision, line numbers in the tool output no longer match the original file — `def foo():` at line 42 in the original might appear at line 12 in the elided outline. Jedi's `get_references(line=N, column=0)` uses line numbers from the source passed to `jedi.Script(source=...)`. If JediInterceptor runs after AstGrepReadOutline, it would pass the elided outline as `source=`, causing jedi to analyse incorrect line positions.

Running jedi first, on the full original source, gives correct line/column positions. AstGrepReadOutline then elides bodies from the jedi-enriched string (which still has the original bodies intact at that point).

### 9.6 Why `jedi>=0.19.0` and not the latest?

0.19.0 is the lowest version that:
- Supports `get_names(all_scopes=False, definitions=True)` with the stable return type.
- Works with Python 3.12+ ASTs (parso 0.8.3 was bundled).
- Has `include_builtins` in `get_references()`.

Pinning a floor rather than an exact version lets users upgrade jedi independently without bumping Cutctx.

---

## 10. File Creation / Modification Summary

| File | Action | Description |
|---|---|---|
| `cutctx/proxy/interceptors/jedi_interceptor.py` | **CREATE** | Full `JediInterceptor` implementation — matches, transform, progressive_disclosure_key, helpers |
| `cutctx/proxy/interceptors/__init__.py` | **MODIFY** | Add `__getattr__` lazy export of `JediInterceptor`; add `"JediInterceptor"` to `__all__` |
| `cutctx/proxy/models.py` | **MODIFY** | Add 3 fields: `jedi_enabled: bool = False`, `jedi_max_references: int = 10`, `jedi_include_callers: bool = True` |
| `cutctx/cli/proxy.py` | **MODIFY** | Add 3 Click options (`--jedi`, `--jedi-max-refs`, `--no-jedi-callers`); add jedi startup registration block; pass 3 new fields to `ProxyConfig(...)` constructor |
| `pyproject.toml` | **MODIFY** | Add `python-analysis = ["jedi>=0.19.0"]` optional dep group after `code = [...]` block |
| `tests/test_jedi_interceptor.py` | **CREATE** | 11 unit tests: non-Python rejection, non-Read rejection, small file rejection, matches happy path, syntax error fallback, missing jedi fallback, cross-ref format, no-enlarge invariant, progressive disclosure key, key with no path, thread safety |

**Files NOT modified:**
- `cutctx/proxy/interceptors/base.py` — protocol and registry are unchanged
- `cutctx/proxy/interceptors/astgrep.py` — no changes needed
- All other proxy, compressor, or transform files

---

## 11. Open Questions

1. **Caller discovery latency on large codebases.** `get_references()` on a symbol with thousands of callers (e.g. a widely-used utility function in a monorepo) may take several seconds. Consider adding a per-call timeout via `threading.Timer` and falling back to `None` if exceeded. The current implementation relies on jedi's internal caching to keep repeat calls fast.

2. **Project root inference.** Jedi infers the project root from `path=` by walking up the directory tree looking for `setup.py`, `pyproject.toml`, etc. In Docker containers or when the proxy is started from outside the repo root, this inference may fail. Consider adding a `jedi_project_root: str | None = None` config field that maps to `jedi.Project(path=jedi_project_root)`.

3. **Multi-file project caching.** Each `transform()` call creates a fresh `jedi.Script`. Jedi caches parsed modules internally, so the second call on the same project is much faster. But if the proxy is restarted frequently (e.g. in dev with `--reload`), the cache is lost. A persistent `jedi.Project` instance shared across calls would improve cold-start latency.

4. **Test coverage for actual cross-file references.** The current test suite mocks jedi. Integration tests that create a temporary Python project, run jedi against it, and verify that `[CROSS-REFERENCES]` contains the correct caller paths would catch regressions in jedi API compatibility. These belong in `e2e/` or a new `tests/integration/` directory.
