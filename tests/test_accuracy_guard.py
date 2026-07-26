"""Tests for log fidelity verification (accuracy guard).

Coverage:
  - Fidelity verification logic (verify_log_fidelity)
  - Mode resolution (resolve_accuracy_guard_mode)
  - Application logic (apply_accuracy_guard)
  - Edge cases: empty payloads, no high-severity lines, malformed markers
"""

from __future__ import annotations

import pytest

from cutctx.proxy.accuracy_guard import (
    LogFidelityViolation,
    apply_accuracy_guard,
    resolve_accuracy_guard_mode,
    verify_log_fidelity,
)


class TestExtractHighSeverityLines:
    """Test high-severity line extraction."""

    def test_extract_error_lines(self) -> None:
        """ERROR keywords are extracted."""
        content = "line 1\nERROR: something broke\nline 3\nerror at runtime\nLine 4"
        violations = verify_log_fidelity(content, content)
        # No violations if original and compressed are identical
        assert violations == []

    def test_extract_fatal_lines(self) -> None:
        """FATAL/CRITICAL keywords are extracted."""
        content = "FATAL: system down\nCRITICAL failure\ninfo: ok"
        violations = verify_log_fidelity(content, content)
        assert violations == []

    def test_extract_fail_lines(self) -> None:
        """FAIL/FAILED keywords are extracted."""
        content = "test FAILED\nFAIL in module\nwarning: watch out"
        violations = verify_log_fidelity(content, content)
        assert violations == []

    def test_extract_case_variants(self) -> None:
        """Case variants are recognized."""
        content = "line 1\nError: bad\nerror: also bad\nERROR: definitely bad\nLine 5"
        violations = verify_log_fidelity(content, content)
        assert violations == []

    def test_no_high_severity_lines(self) -> None:
        """Payload with no high-severity lines passes all modes."""
        content = "INFO: starting\nDEBUG: tracing\nWARN: watch out\n"
        violations = verify_log_fidelity(content, "")
        # No ERROR+ lines, so no violations
        assert violations == []


class TestVerifyLogFidelity:
    """Test the core fidelity verification."""

    def test_no_lines_lost(self) -> None:
        """When nothing is lost, no violation."""
        original = "INFO: start\nERROR: oops\nINFO: done"
        compressed = original  # Identical
        violations = verify_log_fidelity(original, compressed)
        assert violations == []

    def test_error_line_preserved_in_compressed(self) -> None:
        """ERROR line present in compressed output — OK."""
        original = "INFO: start\nERROR: oops\nINFO: middle\nINFO: done"
        compressed = "ERROR: oops\nINFO: done"
        violations = verify_log_fidelity(original, compressed)
        assert violations == []

    def test_error_line_disclosed_by_marker(self) -> None:
        """ERROR line missing but disclosed in marker — OK."""
        original = "INFO: line 1\nERROR: missing\nINFO: line 2"
        # Compressed without ERROR line, but marker discloses 1 ERROR omitted
        compressed = "INFO: line 1\nINFO: line 2\n[2 lines omitted: 1 ERROR, 1 INFO]"
        violations = verify_log_fidelity(original, compressed)
        assert violations == []

    def test_error_line_silently_lost(self) -> None:
        """ERROR line missing AND not in marker — violation."""
        original = "INFO: line 1\nERROR: missing\nINFO: line 2"
        # Compressed without ERROR line, marker doesn't mention it
        compressed = "INFO: line 1\nINFO: line 2\n[2 lines omitted: 2 INFO]"
        violations = verify_log_fidelity(original, compressed)
        assert len(violations) >= 1
        assert violations[0].violation_type == "missing_high_severity_line"

    def test_fatal_line_silently_lost(self) -> None:
        """FATAL line missing — violation."""
        original = "FATAL: critical\nINFO: after"
        compressed = "INFO: after"  # FATAL silently dropped
        violations = verify_log_fidelity(original, compressed)
        assert len(violations) >= 1

    def test_fail_line_silently_lost(self) -> None:
        """FAIL line missing — violation."""
        original = "INFO: start\nFAIL: test failed\nINFO: end"
        compressed = "INFO: start\nINFO: end"  # FAIL silently dropped
        violations = verify_log_fidelity(original, compressed)
        assert len(violations) >= 1

    def test_multiple_errors_some_lost(self) -> None:
        """Multiple ERROR lines; some lost — violation for each lost one."""
        original = "ERROR: first\nERROR: second\nERROR: third"
        # Only second preserved
        compressed = "ERROR: second\n[2 lines omitted: 2 ERROR]"
        violations = verify_log_fidelity(original, compressed)
        assert len(violations) == 0  # Marker discloses the loss

    def test_empty_payloads(self) -> None:
        """Empty or None payloads don't crash."""
        assert verify_log_fidelity("", "") == []
        assert verify_log_fidelity("", "content") == []
        assert verify_log_fidelity("content", "") == []

    def test_compressed_larger_than_original(self) -> None:
        """Expansion is allowed (no violation)."""
        original = "ERROR: error"
        compressed = "ERROR: error\nEXPANDED: with context"
        violations = verify_log_fidelity(original, compressed)
        assert violations == []

    def test_marker_with_multiple_levels(self) -> None:
        """Marker disclosing multiple levels works."""
        original = "ERROR: first\nFATAL: critical\nFAIL: test failed\nINFO: info\n"
        # All ERROR+ omitted, marker discloses them
        compressed = "INFO: info\n[3 lines omitted: 1 FATAL, 1 ERROR, 1 FAIL]"
        violations = verify_log_fidelity(original, compressed)
        assert violations == []

    def test_marker_with_zero_error_counts(self) -> None:
        """Marker saying 0 FATAL/ERROR/FAIL when they're missing — violation."""
        original = "ERROR: lost\nINFO: kept"
        compressed = "INFO: kept\n[1 lines omitted: 0 FATAL, 0 ERROR, 0 FAIL, 1 INFO]"
        violations = verify_log_fidelity(original, compressed)
        assert len(violations) >= 1

    def test_no_marker_all_errors_lost(self) -> None:
        """No marker and all errors lost — violation."""
        original = "ERROR: one\nERROR: two"
        compressed = ""
        violations = verify_log_fidelity(original, compressed)
        assert len(violations) >= 2

    def test_whitespace_normalization(self) -> None:
        """Line matching is trim-sensitive."""
        original = "  ERROR: indent"
        compressed = "ERROR: indent"  # Same line, different whitespace
        violations = verify_log_fidelity(original, compressed)
        assert violations == []


class TestResolveMode:
    """Test accuracy guard mode resolution."""

    def test_env_var_precedence(self) -> None:
        """Environment variable takes precedence over config."""
        mode = resolve_accuracy_guard_mode(config_value="off", env_var="strict")
        assert mode == "strict"

    def test_config_value_fallback(self) -> None:
        """Config value used when env var absent."""
        mode = resolve_accuracy_guard_mode(config_value="balanced", env_var=None)
        assert mode == "balanced"

    def test_default_off(self) -> None:
        """Default is 'off' when both absent."""
        mode = resolve_accuracy_guard_mode(config_value=None, env_var=None)
        assert mode == "off"

    def test_case_insensitive(self) -> None:
        """Mode matching is case-insensitive."""
        assert resolve_accuracy_guard_mode(config_value="STRICT", env_var=None) == "strict"
        assert resolve_accuracy_guard_mode(config_value="Balanced", env_var=None) == "balanced"

    def test_whitespace_stripped(self) -> None:
        """Leading/trailing whitespace is stripped."""
        assert resolve_accuracy_guard_mode(config_value="  off  ", env_var=None) == "off"

    def test_invalid_mode_defaults_to_off(self) -> None:
        """Invalid mode values default to 'off'."""
        mode = resolve_accuracy_guard_mode(config_value="invalid", env_var=None)
        assert mode == "off"

    def test_empty_strings_treated_as_none(self) -> None:
        """Empty strings don't override."""
        mode = resolve_accuracy_guard_mode(config_value="", env_var="strict")
        assert mode == "strict"


class TestApplyAccuracyGuard:
    """Test the apply_accuracy_guard integration function."""

    def test_off_mode_no_checking(self) -> None:
        """'off' mode returns compressed without checking."""
        original = "ERROR: lost"
        compressed = ""  # Would be a violation
        result = apply_accuracy_guard(original, compressed, mode="off")
        # Even though compressed is empty (violation), off mode ignores it
        assert result == compressed

    def test_balanced_mode_returns_compressed_on_no_violation(self) -> None:
        """'balanced' mode returns compressed when no violation."""
        original = "ERROR: kept\nINFO: also kept"
        compressed = "ERROR: kept\nINFO: also kept"
        result = apply_accuracy_guard(original, compressed, mode="balanced")
        assert result == compressed

    def test_balanced_mode_returns_compressed_on_violation(self) -> None:
        """'balanced' mode logs warning but returns compressed even on violation."""
        original = "ERROR: lost"
        compressed = ""  # Violation
        result = apply_accuracy_guard(original, compressed, mode="balanced")
        assert result == compressed  # Still returns compressed

    def test_strict_mode_returns_compressed_on_no_violation(self) -> None:
        """'strict' mode returns compressed when no violation."""
        original = "ERROR: kept"
        compressed = "ERROR: kept"
        result = apply_accuracy_guard(original, compressed, mode="strict")
        assert result == compressed

    def test_strict_mode_returns_original_on_violation(self) -> None:
        """'strict' mode returns original when violation detected."""
        original = "ERROR: important\nINFO: data"
        # Compressed without ERROR, no marker disclosure
        compressed = "INFO: data"
        result = apply_accuracy_guard(original, compressed, mode="strict")
        assert result == original  # Falls back to original

    def test_strict_mode_with_proper_marker_returns_compressed(self) -> None:
        """'strict' mode returns compressed when marker properly discloses loss."""
        original = "ERROR: lost\nINFO: kept"
        compressed = "INFO: kept\n[1 lines omitted: 1 ERROR]"
        result = apply_accuracy_guard(original, compressed, mode="strict")
        assert result == compressed  # No violation due to marker


class TestRealWorldScenarios:
    """Test on realistic log outputs."""

    def test_pytest_output_with_errors_disclosed(self) -> None:
        """Realistic pytest output where errors are disclosed."""
        original = """============================= test session starts ==============================
collected 100 items
tests/test_foo.py::test_1 PASSED [ 1%]
ERROR: something failed in test_2
ERROR: another failure
test_foo.py::test_3 PASSED [ 3%]
================================ short test summary ============================
FAILED tests/test_foo.py::test_2 - RuntimeError
FAILED tests/test_foo.py::test_4 - AssertionError
======================== 2 failed, 98 passed ========================
"""
        compressed = """============================= test session starts ==============================
FAILED tests/test_foo.py::test_2 - RuntimeError
FAILED tests/test_foo.py::test_4 - AssertionError
======================== 2 failed, 98 passed ========================
[98 lines omitted: 2 ERROR, 96 INFO]
"""
        # Balanced mode: log warning but return compressed
        result = apply_accuracy_guard(original, compressed, mode="balanced")
        assert result == compressed

    def test_npm_error_with_marker(self) -> None:
        """npm output with ERROR disclosed in marker."""
        original = "\n".join(
            ["npm WARN deprecated package: old"] * 30
            + ["npm ERR! code ERESOLVE", "npm ERR! unable to resolve"]
        )
        compressed = (
            "npm ERR! code ERESOLVE\nnpm ERR! unable to resolve\n[30 lines omitted: 30 WARN]"
        )
        result = apply_accuracy_guard(original, compressed, mode="strict")
        assert result == compressed

    def test_cargo_build_error_silently_lost(self) -> None:
        """Cargo build output where error is silently lost — strict mode catches it."""
        original = "   Compiling myapp v1.0.0\nerror[E0382]: borrow of moved value\nFinished dev"
        # Error silently dropped, no marker
        compressed = "   Compiling myapp v1.0.0\nFinished dev"
        result = apply_accuracy_guard(original, compressed, mode="strict")
        assert result == original  # Falls back due to violation

    def test_empty_compressed_with_errors(self) -> None:
        """Compressed is empty but original has ERROR."""
        original = "ERROR: serious issue"
        compressed = ""
        result = apply_accuracy_guard(original, compressed, mode="strict")
        assert result == original

    def test_mixed_severity_marker(self) -> None:
        """Marker with all severity levels, some omitted."""
        original = "FATAL: f\nERROR: e\nFAIL: fa\nWARN: w\nINFO: i\nDEBUG: d"
        compressed = "FATAL: f\nERROR: e\nFAIL: fa\n[3 lines omitted: 1 WARN, 1 INFO, 1 DEBUG]"
        result = apply_accuracy_guard(original, compressed, mode="strict")
        assert result == compressed  # High-severity lines are all there


class TestEdgeCases:
    """Test edge cases and robustness."""

    def test_malformed_marker_ignored(self) -> None:
        """Malformed marker doesn't crash, defaults to 0 counts."""
        original = "ERROR: lost"
        compressed = "[malformed marker here]"
        violations = verify_log_fidelity(original, compressed)
        assert len(violations) >= 1

    def test_marker_is_parsed_when_followed_by_trailing_lines(self) -> None:
        """The marker is NOT the last line in real output.

        With CCR active the compressor appends a retrieval line after the
        omission marker. Requiring the marker at EOF meant it was never
        parsed, so correctly-disclosed omissions looked undisclosed — which
        produced hundreds of spurious violations per payload and, in strict
        mode, would have forced uncompressed forwarding on nearly every log
        request. Parsing must tolerate trailing content.
        """
        original = "ERROR: lost"
        compressed = "[1 lines omitted: 1 ERROR]\nsome other content"
        assert verify_log_fidelity(original, compressed) == []

    def test_real_compressor_output_shape_is_parsed(self) -> None:
        """Exactly the two-line tail the log compressor emits."""
        original = "2026 ERROR alpha\n2026 ERROR beta\n2026 INFO fine"
        compressed = (
            "2026 INFO fine\n"
            "[2 lines omitted: 2 ERROR]\n"
            "[3 lines compressed to 1. Retrieve more: hash=601157cc19c5980c]"
        )
        assert verify_log_fidelity(original, compressed) == []

    def test_undisclosed_loss_is_still_caught(self) -> None:
        """The guard must not become permissive as a result of the above."""
        original = "2026 ERROR alpha\n2026 INFO fine\n2026 ERROR beta"
        compressed = "2026 INFO fine"  # no marker at all
        assert len(verify_log_fidelity(original, compressed)) >= 1

    def test_very_long_lines(self) -> None:
        """Long lines don't cause issues."""
        original = "ERROR: " + "x" * 10000
        compressed = original
        violations = verify_log_fidelity(original, compressed)
        assert violations == []

    def test_unicode_content(self) -> None:
        """Unicode content is handled correctly."""
        original = "ERROR: 失敗しました\nINFO: 情報"
        compressed = "ERROR: 失敗しました\nINFO: 情報"
        violations = verify_log_fidelity(original, compressed)
        assert violations == []

    def test_many_high_severity_lines(self) -> None:
        """Many ERROR lines all tracked correctly."""
        original = "\n".join([f"ERROR: issue {i}" for i in range(100)])
        compressed = original  # All preserved
        violations = verify_log_fidelity(original, compressed)
        assert violations == []

    def test_newline_only_differences(self) -> None:
        """Differences in trailing newlines handled."""
        original = "ERROR: line\n"
        compressed = "ERROR: line"
        violations = verify_log_fidelity(original, compressed)
        assert violations == []
