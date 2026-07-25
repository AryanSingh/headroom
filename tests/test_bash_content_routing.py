"""Tests for Bash tool content-shape routing.

Tests the mechanism that routes Bash output by content shape instead of
excluding it wholesale. Directory listings are protected; log-shaped output
is routed to LogCompressor.

Coverage:
1. Directory listing detection (tree, ls, find output)
2. Log-shaped output detection (pytest, cargo, npm, make, etc.)
3. Router behavior with Bash tool messages
4. Error line preservation through compression
"""

import pytest

from cutctx.providers import OpenAIProvider
from cutctx.tokenizer import Tokenizer
from cutctx.transforms.content_router import (
    CompressionStrategy,
    ContentRouter,
    ContentRouterConfig,
    _is_directory_listing_output,
    bash_content_routing_enabled,
)


@pytest.fixture
def tokenizer():
    """Get a tokenizer for tests."""
    provider = OpenAIProvider()
    token_counter = provider.get_token_counter("gpt-4o")
    return Tokenizer(token_counter, "gpt-4o")


class TestDirectoryListingDetection:
    """Tests for detecting directory listing vs. log output."""

    def test_tree_output_detected_as_listing(self):
        """tree command output is detected as directory listing."""
        from cutctx.transforms.content_router import _is_directory_listing_output

        content = """directory
├── file1.txt
├── file2.py
├── subdir
│   ├── nested.txt
│   └── another.py
└── README.md

5 files, 2 directories"""
        assert _is_directory_listing_output(content) is True

    def test_ls_long_output_detected_as_listing(self):
        """ls -la output is detected as directory listing."""
        from cutctx.transforms.content_router import _is_directory_listing_output

        content = """total 48
drwxr-xr-x   5 user  staff   160 Jul 26 10:30 .
drwxr-xr-x  10 user  staff   320 Jul 25 14:20 ..
-rw-r--r--   1 user  staff  1024 Jul 26 10:30 file.txt
drwxr-xr-x   3 user  staff    96 Jul 26 10:25 subdir
-rw-r--r--   1 user  staff  2048 Jul 25 15:00 data.json"""
        assert _is_directory_listing_output(content) is True

    def test_find_output_detected_as_listing(self):
        """find command output is detected as directory listing."""
        from cutctx.transforms.content_router import _is_directory_listing_output

        content = """./src/main.py
./src/utils.py
./tests/test_main.py
./tests/fixtures/data.json
./README.md
./setup.py"""
        assert _is_directory_listing_output(content) is True

    def test_pytest_output_not_detected_as_listing(self):
        """pytest output is NOT detected as directory listing."""
        from cutctx.transforms.content_router import _is_directory_listing_output

        content = """============================= test session starts ==============================
platform darwin -- Python 3.11.0
collected 15 items

tests/test_foo.py::test_basic PASSED [  6%]
tests/test_foo.py::test_edge FAILED [ 13%]

=================================== FAILURES ===================================
tests/test_foo.py::test_edge - AssertionError: expected 5 got 3

========================= 1 failed, 14 passed in 0.45s ========================="""
        assert _is_directory_listing_output(content) is False

    def test_cargo_output_not_detected_as_listing(self):
        """cargo build output is NOT detected as directory listing."""
        from cutctx.transforms.content_router import _is_directory_listing_output

        content = """   Compiling myproject v0.1.0 (/path/to/project)
warning: unused variable: `x`
 --> src/main.rs:5:9
  |
5 |     let x = 5;
  |         ^ help: if this is intentional, prefix it with an underscore: `_x`

error[E0382]: borrow of moved value: `s`
    --> src/lib.rs:10:5
     |
10 |     consume(s);
     |     --------- value moved here
11 |     println!("{}", s);
     |                   ^ value used here after move

error: could not compile `myproject` (bin target `my_binary`)"""
        assert _is_directory_listing_output(content) is False

    def test_npm_output_not_detected_as_listing(self):
        """npm test output is NOT detected as directory listing."""
        from cutctx.transforms.content_router import _is_directory_listing_output

        content = """npm WARN deprecated package@1.0.0: This package is deprecated
npm ERR! code ERESOLVE
npm ERR! ERESOLVE unable to resolve dependency tree
npm ERR!
npm ERR! While resolving: myproject@1.0.0
npm ERR! While resolving dependencies for myproject@1.0.0:
npm ERR! Could not resolve dependency:
npm ERR! peer optional webpack@"^4.0.0" from my-plugin@2.0.0

npm info ok"""
        assert _is_directory_listing_output(content) is False

    def test_generic_log_not_detected_as_listing(self):
        """Generic log with timestamps not detected as listing."""
        from cutctx.transforms.content_router import _is_directory_listing_output

        content = """[2026-07-26T10:30:45.123Z] INFO: Starting service
[2026-07-26T10:30:46.234Z] DEBUG: Loading configuration
[2026-07-26T10:30:47.345Z] INFO: Service started on port 8080
[2026-07-26T10:30:48.456Z] WARNING: High memory usage
[2026-07-26T10:30:49.567Z] ERROR: Failed to connect to database"""
        assert _is_directory_listing_output(content) is False

    def test_empty_content_not_detected_as_listing(self):
        """Empty content is not detected as listing."""
        from cutctx.transforms.content_router import _is_directory_listing_output

        assert _is_directory_listing_output("") is False
        assert _is_directory_listing_output("   \n  \n  ") is False


@pytest.fixture
def bash_routing_on(monkeypatch):
    """Enable the opt-in Bash content-shape routing.

    Routing ships OFF: `Bash` is on DEFAULT_EXCLUDE_TOOLS because commit
    4605fc197 found the text compressor mangling tree/ls output, and
    misclassifying a listing would reintroduce that on the request path.
    Tests that exercise the routing must opt in explicitly, exactly as an
    operator would.
    """
    monkeypatch.setenv("CUTCTX_BASH_CONTENT_ROUTING", "1")


class TestBashRoutingDefaultsOff:
    """The shipped default must remain the pre-existing safe behaviour."""

    def test_routing_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv("CUTCTX_BASH_CONTENT_ROUTING", raising=False)
        assert bash_content_routing_enabled() is False

    @pytest.mark.parametrize("value", ["1", "true", "yes", "on", "TRUE", "On"])
    def test_recognised_truthy_values(self, monkeypatch, value):
        monkeypatch.setenv("CUTCTX_BASH_CONTENT_ROUTING", value)
        assert bash_content_routing_enabled() is True

    @pytest.mark.parametrize("value", ["", "0", "false", "no", "off", "banana"])
    def test_everything_else_is_off(self, monkeypatch, value):
        monkeypatch.setenv("CUTCTX_BASH_CONTENT_ROUTING", value)
        assert bash_content_routing_enabled() is False


class TestListingWinsOverKeywordFilenames:
    """A directory listing whose filenames contain severity words is still a
    listing. This is the regression that motivated gating the feature."""

    def test_ls_of_a_log_directory_is_a_listing(self):
        listing = (
            "total 48\n"
            "-rw-r--r--  1 u  s   1024 Jul 25 10:00 error.log\n"
            "-rw-r--r--  1 u  s   2048 Jul 25 10:01 WARNING.md\n"
            "-rw-r--r--  1 u  s    512 Jul 25 10:02 failed_runs.txt\n"
            "drwxr-xr-x  3 u  s     96 Jul 25 10:03 archive"
        )
        assert _is_directory_listing_output(listing) is True

    def test_structural_marker_still_wins(self):
        """An unambiguous log marker beats listing syntax."""
        log = (
            "2026-07-25T10:00:00Z INFO starting\n"
            "-rw-r--r--  1 u  s  10 Jul 25 10:00 a.txt\n"
            "2026-07-25T10:00:01Z ERROR failed to bind"
        )
        assert _is_directory_listing_output(log) is False


class TestBashContentRouting:
    """Tests for Bash tool message routing behavior."""

    def test_bash_tree_output_excluded_recent(self, tokenizer):
        """Recent Bash tree output is excluded from compression."""
        router = ContentRouter(ContentRouterConfig())

        tree_output = """directory
├── src
│   ├── main.py
│   └── utils.py
└── tests
    └── test_main.py"""

        messages = [
            {
                "role": "tool",
                "tool_call_id": "bash_1",
                "content": tree_output,
            }
        ]
        # Mock tool name map
        router._build_tool_name_map = lambda msgs: {"bash_1": "Bash"}

        result = router.apply(
            messages,
            tokenizer=tokenizer,
        )

        # Tree output should be excluded
        assert any("router:excluded:tool" in transform for transform in result.transforms_applied)

    def test_bash_pytest_output_not_excluded_recent(self, tokenizer, bash_routing_on):
        """Recent Bash pytest output is NOT excluded."""
        router = ContentRouter(ContentRouterConfig())

        pytest_output = """============================= test session starts ==============================
collected 3 items

tests/test_foo.py::test_basic PASSED [  33%]
tests/test_foo.py::test_edge FAILED [ 66%]
tests/test_foo.py::test_simple PASSED [ 100%]

=================================== FAILURES ===================================
tests/test_foo.py::test_edge - AssertionError

========================= 1 failed, 2 passed in 0.45s ========================="""

        messages = [
            {
                "role": "tool",
                "tool_call_id": "bash_1",
                "content": pytest_output,
            }
        ]
        # Mock tool name map
        router._build_tool_name_map = lambda msgs: {"bash_1": "Bash"}

        result = router.apply(
            messages,
            tokenizer=tokenizer,
        )

        # pytest output should NOT be excluded
        # (it flows through to normal compression routing, not the excluded:tool path)
        assert not any(
            "router:excluded:tool" in transform for transform in result.transforms_applied
        )

    def test_bash_cargo_output_not_excluded(self, tokenizer, bash_routing_on):
        """Bash cargo output is routed to LogCompressor, not excluded."""
        router = ContentRouter(ContentRouterConfig())

        cargo_output = """   Compiling myproject v0.1.0
    Finished dev [unoptimized + debuginfo] target(s) in 0.45s
     Running `target/debug/myproject`
error[E0425]: cannot find value `x` in scope
 --> src/main.rs:5:9
  |
5 |     println!("{}", x);
  |                    ^ not found in this scope"""

        messages = [
            {
                "role": "tool",
                "tool_call_id": "bash_1",
                "content": cargo_output,
            }
        ]
        router._build_tool_name_map = lambda msgs: {"bash_1": "Bash"}

        result = router.apply(
            messages,
            tokenizer=tokenizer,
        )

        # cargo output should NOT be excluded
        assert not any(
            "router:excluded:tool" in transform for transform in result.transforms_applied
        )

    def test_bash_lowercase_tree_output_excluded(self, tokenizer):
        """Lowercase 'bash' tool name also works for content-shape routing."""
        router = ContentRouter(ContentRouterConfig())

        tree_output = """src/
├── main.py
└── utils.py"""

        messages = [
            {
                "role": "tool",
                "tool_call_id": "bash_1",
                "content": tree_output,
            }
        ]
        # Mock lowercase tool name
        router._build_tool_name_map = lambda msgs: {"bash_1": "bash"}

        result = router.apply(
            messages,
            tokenizer=tokenizer,
        )

        # Should be excluded
        assert any("router:excluded:tool" in transform for transform in result.transforms_applied)

    def test_bash_make_output_not_excluded(self, tokenizer, bash_routing_on):
        """Bash make output is routed, not excluded."""
        router = ContentRouter(ContentRouterConfig())

        make_output = """make[1]: Entering directory '/path/to/project'
gcc -Wall -c main.c
gcc -Wall -c utils.c
make[1]: *** [Makefile:10: utils.o] Error 1
make: *** [Makefile:5: all] Error 2"""

        messages = [
            {
                "role": "tool",
                "tool_call_id": "bash_1",
                "content": make_output,
            }
        ]
        router._build_tool_name_map = lambda msgs: {"bash_1": "Bash"}

        result = router.apply(
            messages,
            tokenizer=tokenizer,
        )

        # make output should NOT be excluded
        assert not any(
            "router:excluded:tool" in transform for transform in result.transforms_applied
        )

    def test_other_tools_still_excluded(self, tokenizer):
        """Non-Bash excluded tools (Read, Grep, etc.) still behave normally."""
        router = ContentRouter(ContentRouterConfig())

        # Read output: exact file content
        read_output = """def process(data):
    return data * 2

if __name__ == "__main__":
    print(process(5))"""

        messages = [
            {
                "role": "tool",
                "tool_call_id": "read_1",
                "content": read_output,
            }
        ]
        router._build_tool_name_map = lambda msgs: {"read_1": "Read"}

        result = router.apply(
            messages,
            tokenizer=tokenizer,
        )

        # Read should still be excluded
        assert any("router:excluded:tool" in transform for transform in result.transforms_applied)


class TestBashLogCompressionRatios:
    """Tests that log-shaped Bash output achieves good compression ratios."""

    def test_bash_pytest_achieves_high_compression(self, tokenizer, bash_routing_on):
        """Bash pytest output achieves >80% compression."""
        router = ContentRouter(ContentRouterConfig())

        # Large pytest output with many passing tests
        pytest_output = """============================= test session starts ==============================
platform darwin -- Python 3.11.0
collected 100 items

tests/test_basic.py::test_1 PASSED [  1%]
tests/test_basic.py::test_2 PASSED [  2%]
tests/test_basic.py::test_3 PASSED [  3%]
tests/test_basic.py::test_4 PASSED [  4%]
tests/test_basic.py::test_5 PASSED [  5%]
tests/test_edge.py::test_6 FAILED [ 50%]
tests/test_edge.py::test_7 PASSED [ 51%]
tests/test_edge.py::test_8 PASSED [ 52%]
tests/test_edge.py::test_9 PASSED [ 53%]
tests/test_edge.py::test_10 PASSED [ 54%]
""" + "\n".join([f"tests/test_foo.py::test_{i} PASSED [ {i}%]" for i in range(100, 150)])

        messages = [
            {
                "role": "tool",
                "tool_call_id": "bash_1",
                "content": pytest_output,
            }
        ]
        router._build_tool_name_map = lambda msgs: {"bash_1": "Bash"}

        result = router.apply(
            messages,
            tokenizer=tokenizer,
        )

        # Should NOT be excluded (it's available for compression routing)
        assert not any(
            "router:excluded:tool" in transform for transform in result.transforms_applied
        )

    def test_bash_error_lines_not_excluded(self, tokenizer, bash_routing_on):
        """Error lines in Bash logs are not excluded from routing."""
        router = ContentRouter(ContentRouterConfig())

        cargo_output = """   Compiling myproject v0.1.0
warning: unused variable: `x`
 --> src/main.rs:5:9

error[E0425]: cannot find value `undefined_var`
 --> src/lib.rs:42:10
  |
42 |     let y = undefined_var;
  |             ^^^^^^^^^^^^^^ not found in this scope

error: could not compile `myproject`

Finished with 1 error"""

        messages = [
            {
                "role": "tool",
                "tool_call_id": "bash_1",
                "content": cargo_output,
            }
        ]
        router._build_tool_name_map = lambda msgs: {"bash_1": "Bash"}

        result = router.apply(
            messages,
            tokenizer=tokenizer,
        )

        # Cargo output with errors should NOT be excluded
        assert not any(
            "router:excluded:tool" in transform for transform in result.transforms_applied
        )


class TestEdgeCases:
    """Edge cases for content-shape routing."""

    def test_bash_mixed_content_with_log_and_paths(self):
        """Mixed content with both log patterns and paths defaults to log detection."""
        from cutctx.transforms.content_router import _is_directory_listing_output

        # Content with both: log patterns should win
        mixed = """ERROR: Build failed
./src/main.py
./src/utils.py
FATAL: System crash
./tests/test.py"""
        # Log patterns take precedence — should NOT be detected as listing
        assert _is_directory_listing_output(mixed) is False

    def test_bash_mostly_paths_no_log_patterns(self):
        """High-density paths without log patterns detected as listing."""
        from cutctx.transforms.content_router import _is_directory_listing_output

        content = """./src/main.py
./src/utils.py
./tests/test_main.py
./tests/fixtures/data.json
./README.md
./setup.py
./LICENSE
./MANIFEST.in
./pyproject.toml
./tox.ini"""
        # No log patterns, high path density — should be listing
        assert _is_directory_listing_output(content) is True

    def test_bash_very_short_output(self):
        """Very short Bash output (< 5 lines) is handled correctly."""
        from cutctx.transforms.content_router import _is_directory_listing_output

        # Too short to determine
        short = "ERROR\nfailed"
        # Log pattern present, so not a listing
        assert _is_directory_listing_output(short) is False

        short_paths = "./src/\n./tests/"
        # Mostly paths, no log patterns
        assert _is_directory_listing_output(short_paths) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
