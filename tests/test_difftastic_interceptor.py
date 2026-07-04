"""Tests for the DifftasticInterceptor module."""

from __future__ import annotations

import hashlib
from unittest.mock import MagicMock, patch

import pytest

from cutctx.proxy.interceptors.difftastic_interceptor import (
    DifftasticInterceptor,
    _is_git_diff,
    _reconstruct_old_new,
    _run_difft,
    _split_into_file_diffs,
)

# ===========================================================================
# Fixtures
# ===========================================================================

_SINGLE_FILE_DIFF = """\
diff --git a/src/main.py b/src/main.py
index abc123..def456 100644
--- a/src/main.py
+++ b/src/main.py
@@ -1,7 +1,9 @@
 def greet(name):
-    print("Hello, " + name)
+    print(f"Hello, {name}!")
+

 def farewell(name):
     print("Goodbye, " + name)
+
+
"""

_MULTI_FILE_DIFF = """\
diff --git a/src/main.py b/src/main.py
index a1..b1 100644
--- a/src/main.py
+++ b/src/main.py
@@ -1,3 +1,3 @@
 def greet(name):
-    return "Hello, " + name
+    return f"Hello, {name}!"
diff --git a/src/utils.py b/src/utils.py
index a2..b2 100644
--- a/src/utils.py
+++ b/src/utils.py
@@ -1,4 +1,4 @@
 def add(a, b):
-    return a + b
+    return a + b + 0
"""

_COMBINED_DIFF = """\
diff --cc src/main.py
index abc123,def456..789abc
--- a/src/main.py
+++ b/src/main.py
@@@ -1,5 -1,5 +1,9 @@@
  def greet(name):
-     print("Hello, " + name)
 -    print("Goodbye, " + name)
++    print(f"Hello, {name}!")
++    print(f"Goodbye, {name}!")
"""

_NEW_FILE_DIFF = """\
diff --git a/src/new.py b/src/new.py
new file mode 100644
index 0000000..abc123
--- /dev/null
+++ b/src/new.py
@@ -0,0 +1,3 @@
+def new_func():
+    pass
"""

_DELETED_FILE_DIFF = """\
diff --git a/src/old.py b/src/old.py
deleted file mode 100644
index abc123..0000000
--- a/src/old.py
+++ /dev/null
@@ -1,3 +0,0 @@
-def old_func():
-    pass
"""

_MODE_CHANGE_DIFF = """\
diff --git a/src/main.py b/src/main.py
old mode 100644
new mode 100755
"""

_RENAME_DIFF = """\
diff --git a/src/old.py b/src/new.py
similarity index 100%
rename from src/old.py
rename to src/new.py
"""

_GREP_OUTPUT = """\
src/main.py:10:    print("hello")
src/utils.py:5:    return a + b
"""

_PLAIN_TEXT = """\
This is just some plain text without any diff content.
It spans multiple lines.
"""


# ===========================================================================
# TestMatches
# ===========================================================================


class TestMatches:
    def test_matches_bash_with_git_diff(self):
        interceptor = DifftasticInterceptor()
        assert interceptor.matches("Bash", {}, _SINGLE_FILE_DIFF) is True

    def test_matches_run_tool(self):
        interceptor = DifftasticInterceptor()
        assert interceptor.matches("Run", {}, _SINGLE_FILE_DIFF) is True

    def test_no_match_on_non_diff(self):
        interceptor = DifftasticInterceptor()
        assert interceptor.matches("Bash", {}, _PLAIN_TEXT) is False

    def test_no_match_on_grep_output(self):
        interceptor = DifftasticInterceptor()
        assert interceptor.matches("Bash", {}, _GREP_OUTPUT) is False

    def test_no_match_on_read_tool(self):
        interceptor = DifftasticInterceptor()
        assert interceptor.matches("Read", {}, _SINGLE_FILE_DIFF) is False

    def test_no_match_below_min_chars(self):
        interceptor = DifftasticInterceptor()
        small = "diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n"
        assert interceptor.matches("Bash", {}, small) is False

    def test_matches_multi_file_diff(self):
        interceptor = DifftasticInterceptor()
        assert interceptor.matches("Bash", {}, _MULTI_FILE_DIFF) is True

    def test_matches_combined_diff(self):
        """H5: combined diff (diff --cc) should be detected."""
        interceptor = DifftasticInterceptor()
        assert interceptor.matches("Bash", {}, _COMBINED_DIFF) is True

    def test_empty_diff_does_not_match(self):
        """H5: empty diff string should not match."""
        interceptor = DifftasticInterceptor()
        assert interceptor.matches("Bash", {}, "") is False

    def test_mode_change_diff_matches(self):
        """H5: mode-only change diff should be detected as a diff."""
        interceptor = DifftasticInterceptor()
        # Pad to exceed MIN_CHARS_TO_TRANSFORM threshold
        padded = _MODE_CHANGE_DIFF + "\n# " + "x" * 200
        assert interceptor.matches("Bash", {}, padded) is True

    def test_rename_diff_matches(self):
        """H5: rename-only diff should be detected as a diff."""
        interceptor = DifftasticInterceptor()
        # Pad to exceed MIN_CHARS_TO_TRANSFORM threshold
        padded = _RENAME_DIFF + "\n# " + "x" * 200
        assert interceptor.matches("Bash", {}, padded) is True


# ===========================================================================
# TestIsGitDiff
# ===========================================================================


class TestIsGitDiff:
    def test_detects_diff_git(self):
        assert _is_git_diff("diff --git a/x b/x\n") is True

    def test_detects_bare_minus_a(self):
        assert _is_git_diff("--- a/foo.py\n+++ b/foo.py\n") is True

    def test_rejects_plain_text(self):
        assert _is_git_diff("hello world") is False

    def test_rejects_grep_output(self):
        assert _is_git_diff(_GREP_OUTPUT) is False

    def test_detects_diff_cc(self):
        """H5: combined diff (diff --cc) should be detected."""
        assert _is_git_diff("diff --cc src/main.py\n") is True


# ===========================================================================
# TestSplitIntoFileDiffs
# ===========================================================================


class TestSplitIntoFileDiffs:
    def test_single_file(self):
        sections = _split_into_file_diffs(_SINGLE_FILE_DIFF)
        assert len(sections) == 1
        path_a, path_b, section = sections[0]
        assert path_a == "src/main.py"
        assert path_b == "src/main.py"
        assert "diff --git" in section

    def test_multi_file(self):
        sections = _split_into_file_diffs(_MULTI_FILE_DIFF)
        assert len(sections) == 2
        assert sections[0][0] == "src/main.py"
        assert sections[1][0] == "src/utils.py"

    def test_bare_diff(self):
        bare = "--- a/old.txt\n+++ b/new.txt\n@@ -1 +1 @@\n-old\n+new\n"
        sections = _split_into_file_diffs(bare)
        assert len(sections) == 1


# ===========================================================================
# TestReconstructOldNew
# ===========================================================================


class TestReconstructOldNew:
    def test_extracts_old_and_new(self):
        section = """\
diff --git a/main.py b/main.py
--- a/main.py
+++ b/main.py
@@ -1,3 +1,3 @@
 def greet(name):
-    return "Hello, " + name
+    return f"Hello, {name}!"
"""
        old, new, ext = _reconstruct_old_new(section)
        assert '    return "Hello, ' in old
        assert '    return f"Hello, {name}!"' in new
        assert ext == ".py"

    def test_context_in_both(self):
        section = """\
--- a/file.py
+++ b/file.py
@@ -1,4 +1,4 @@
 keep_me
-old_line
+new_line
 keep_me_too
"""
        old, new, ext = _reconstruct_old_new(section)
        assert "keep_me" in old
        assert "keep_me" in new
        assert "old_line" in old
        assert "new_line" in new
        assert ext == ".py"

    def test_combined_diff_hunks(self):
        """H2+H5: combined diff with @@@ headers and 2-space context."""
        section = """\
diff --cc src/main.py
--- a/src/main.py
+++ b/src/main.py
@@@ -1,5 -1,5 +1,9 @@@
  def greet(name):
-     print("Hello, " + name)
 -    print("Goodbye, " + name)
++    print(f"Hello, {name}!")
++    print(f"Goodbye, {name}!")
"""
        old, new, ext = _reconstruct_old_new(section)
        assert "def greet(name):" in old
        assert "def greet(name):" in new
        assert 'print("Hello, ' in old
        assert 'print("Goodbye, ' in old
        assert 'print(f"Hello, {name}!")' in new
        assert 'print(f"Goodbye, {name}!")' in new
        assert ext == ".py"

    def test_new_file_extension(self):
        """H3+H5: new file (--- /dev/null) should use +++ extension."""
        old, new, ext = _reconstruct_old_new(NEW_FILE_DIFF_FIXTURE)
        assert ext == ".py", f"Expected .py, got {ext!r}"
        assert "def new_func():" in new
        assert old.strip() == ""

    def test_deleted_file_extension(self):
        """H5: deleted file (+++ /dev/null) should use --- extension."""
        section = """\
diff --git a/src/old.py b/src/old.py
deleted file mode 100644
--- a/src/old.py
+++ /dev/null
@@ -1,3 +0,0 @@
-def old_func():
-    pass
"""
        old, new, ext = _reconstruct_old_new(section)
        assert ext == ".py", f"Expected .py, got {ext!r}"
        assert "def old_func():" in old
        assert new.strip() == ""

    def test_empty_diff_returns_empty(self):
        """H5: empty diff section should produce empty content."""
        section = ""
        old, new, ext = _reconstruct_old_new(section)
        assert old == ""
        assert new == ""
        assert ext == ".txt"

    def test_mode_change_no_hunks(self):
        """H5: mode-only change (no hunks) should produce empty content."""
        section = """\
diff --git a/src/main.py b/src/main.py
old mode 100644
new mode 100755
"""
        old, new, ext = _reconstruct_old_new(section)
        assert old == ""
        assert new == ""

    def test_rename_no_hunks(self):
        """H5: rename-only diff (no hunks) should produce empty content."""
        section = """\
diff --git a/src/old.py b/src/new.py
similarity index 100%
rename from src/old.py
rename to src/new.py
"""
        old, new, ext = _reconstruct_old_new(section)
        assert old == ""
        assert new == ""


# Need fixture for NEW_FILE_DIFF as a raw string
NEW_FILE_DIFF_FIXTURE = """\
diff --git a/src/new.py b/src/new.py
new file mode 100644
index 0000000..abc123
--- /dev/null
+++ b/src/new.py
@@ -0,0 +1,3 @@
+def new_func():
+    pass
"""


# ===========================================================================
# TestSubprocessTimeout
# ===========================================================================


class TestSubprocessTimeout:
    def test_timeout_returns_none(self):
        with patch(
            "cutctx.proxy.interceptors.difftastic_interceptor.subprocess.run",
        ) as mock_run:
            from subprocess import TimeoutExpired

            mock_run.side_effect = TimeoutExpired("difft", 10)
            result = _run_difft("difft", "old", "new", ".py")
            assert result is None

    def test_oserror_returns_none(self):
        with patch(
            "cutctx.proxy.interceptors.difftastic_interceptor.subprocess.run",
        ) as mock_run:
            mock_run.side_effect = OSError("not found")
            result = _run_difft("difft", "old", "new", ".py")
            assert result is None

    def test_nonzero_exit_returns_none(self):
        with patch(
            "cutctx.proxy.interceptors.difftastic_interceptor.subprocess.run",
        ) as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 2
            mock_result.stdout = ""
            mock_result.stderr = "error"
            mock_run.return_value = mock_result
            result = _run_difft("difft", "old", "new", ".py")
            assert result is None


# ===========================================================================
# TestTransformOutputQuality
# ===========================================================================


class TestTransformOutputQuality:
    def test_shorter_difft_accepted(self):
        interceptor = DifftasticInterceptor()
        # Simulate a resolved exe and a successful do_transform producing shorter output.
        with patch.object(interceptor, "_get_exe", return_value="/fake/difft"):
            with patch.object(interceptor, "do_transform", return_value="short"):
                result = interceptor.transform("Bash", {}, "very long content " * 100)
                assert result == "short"

    def test_longer_difft_returns_none(self):
        interceptor = DifftasticInterceptor()
        with patch.object(interceptor, "_get_exe", return_value="/fake/difft"):
            # do_transform returns output that is longer than the original.
            original = "short content"
            with patch.object(interceptor, "do_transform", return_value=original + " extra"):
                result = interceptor.transform("Bash", {}, original)
                assert result is None

    def test_binary_not_found_graceful(self):
        interceptor = DifftasticInterceptor()
        with patch.object(interceptor, "_get_exe", return_value=None):
            result = interceptor.transform("Bash", {}, _SINGLE_FILE_DIFF)
            assert result is None

    def test_empty_output_returns_none(self):
        interceptor = DifftasticInterceptor()
        with patch.object(interceptor, "_get_exe", return_value="/fake/difft"):
            # If exe is resolved but do_transform returns None (e.g. no file diffs).
            with patch.object(interceptor, "do_transform", return_value=None):
                result = interceptor.transform("Bash", {}, _SINGLE_FILE_DIFF)
                assert result is None

    def test_do_transform_shorter_output(self):
        """Verify do_transform can produce shorter output with mocked difft."""
        interceptor = DifftasticInterceptor()
        # Mock _run_difft to return a short structural diff
        with patch.object(
            interceptor.__class__,
            "_get_exe",
            lambda self: "/fake/difft",
        ):
            with patch(
                "cutctx.proxy.interceptors.difftastic_interceptor._run_difft",
                return_value="def greet(name): ...\n",
            ):
                result = interceptor.do_transform("/fake/difft", _SINGLE_FILE_DIFF)
                assert result is not None
                assert "cutctx: structural diff" in result
                assert len(result) < len(_SINGLE_FILE_DIFF)

    def test_never_enlarge_with_banner_overhead(self):
        """H5: if difft output with banner is larger than original, return None."""
        interceptor = DifftasticInterceptor()
        orig = "very short content"
        # do_transform returns content with banner that is larger than original
        with patch.object(interceptor, "_get_exe", return_value="/fake/difft"):
            with patch.object(
                interceptor,
                "do_transform",
                return_value="[cutctx: structural diff via difft for a -> b]\nshort",
            ):
                result = interceptor.transform("Bash", {}, orig)
                assert result is None, "Should not enlarge content even with banner"

    def test_new_file_difft_produces_output(self):
        """H5: new file diff with mocked difft should produce structural output."""
        interceptor = DifftasticInterceptor()
        with patch.object(interceptor, "_get_exe", return_value="/fake/difft"):
            with patch(
                "cutctx.proxy.interceptors.difftastic_interceptor._run_difft",
                return_value="def new_func(): ...\n",
            ):
                result = interceptor.do_transform("/fake/difft", NEW_FILE_DIFF_FIXTURE)
                assert result is not None
                assert "cutctx: structural diff" in result


# ===========================================================================
# TestProgressiveDisclosureKey
# ===========================================================================


class TestProgressiveDisclosureKey:
    def test_key_from_command(self):
        interceptor = DifftasticInterceptor()
        key = interceptor.progressive_disclosure_key("Bash", {"command": "git diff"})
        expected = hashlib.sha256(b"git diff").hexdigest()
        assert key == expected

    def test_deterministic(self):
        interceptor = DifftasticInterceptor()
        k1 = interceptor.progressive_disclosure_key("Bash", {"command": "git status"})
        k2 = interceptor.progressive_disclosure_key("Bash", {"command": "git status"})
        assert k1 == k2

    def test_differs_for_different_commands(self):
        interceptor = DifftasticInterceptor()
        k1 = interceptor.progressive_disclosure_key("Bash", {"command": "git diff"})
        k2 = interceptor.progressive_disclosure_key("Bash", {"command": "git log"})
        assert k1 != k2

    def test_no_key_when_no_command(self):
        interceptor = DifftasticInterceptor()
        key = interceptor.progressive_disclosure_key("Bash", {})
        assert key is None
        key = interceptor.progressive_disclosure_key("Bash", {"command": ""})
        expected = hashlib.sha256(b"").hexdigest()
        assert key == expected


# ===========================================================================
# TestIntegration (skipped if difft not available)
# ===========================================================================


class TestIntegration:
    @pytest.fixture(autouse=True)
    def _check_difft(self):
        import shutil

        if not shutil.which("difft"):
            pytest.skip("difft not on PATH — integration tests skipped")

    def test_real_diff_produces_shorter_output(self):
        interceptor = DifftasticInterceptor()
        exe = interceptor._get_exe()
        assert exe is not None, "difft should be resolvable"
        result = interceptor.do_transform(exe, _SINGLE_FILE_DIFF)
        assert result is not None
        assert len(result) < len(_SINGLE_FILE_DIFF)

    def test_version_detection(self):
        interceptor = DifftasticInterceptor()
        version = interceptor._get_difft_version()
        assert version is not None and version != "unknown"
        assert "difft" in version.lower()
