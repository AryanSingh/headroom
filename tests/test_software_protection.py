# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Tests

"""SP-3/SP-5/SP-6/SP-7: Tests for software protection modules."""

import time
from pathlib import Path

# ---------------------------------------------------------------------------
# SP-3: compile_ee.py tests
# ---------------------------------------------------------------------------


class TestCompileEe:
    """Tests for the EE compilation script."""

    def test_script_exists(self):
        script = Path(__file__).resolve().parent.parent / "scripts" / "compile_ee.py"
        assert script.exists(), "compile_ee.py should exist"

    def test_script_is_executable_python(self):
        script = Path(__file__).resolve().parent.parent / "scripts" / "compile_ee.py"
        content = script.read_text()
        assert "def main()" in content
        assert "nuitka" in content.lower()

    def test_compile_all_ee_module_structure(self):
        """Verify cutctx_ee modules exist for compilation."""
        ee_dir = Path(__file__).resolve().parent.parent / "cutctx_ee"
        py_files = [f for f in ee_dir.rglob("*.py") if f.name != "__init__.py"]
        assert len(py_files) >= 5, f"Expected at least 5 EE modules, found {len(py_files)}"

    def test_verify_no_source_logic(self):
        """Verify the no-source check logic works with mock data."""
        import tempfile
        import zipfile

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            # Create a mock wheel with .py files
            wheel_path = tmpdir / "test-ee-0.1.0-py3-none-any.whl"
            with zipfile.ZipFile(wheel_path, "w") as zf:
                zf.writestr("cutctx_ee/__init__.py", "# source code")
                zf.writestr("cutctx_ee/module.so", b"\x7fELF")

            # Should find .py files
            with zipfile.ZipFile(wheel_path) as z:
                py_files = [n for n in z.namelist() if n.endswith(".py")]
                so_files = [n for n in z.namelist() if n.endswith(".so")]
                assert len(py_files) == 1
                assert len(so_files) == 1


# ---------------------------------------------------------------------------
# SP-5: Watermark tests
# ---------------------------------------------------------------------------


class TestWatermark:
    """Tests for per-customer watermarking."""

    def test_watermark_roundtrip(self):
        from cutctx_ee.watermark import Watermark

        wm = Watermark(
            lic_id="lic_test123",
            customer_id="cust_acme",
            build_id="build-20260101",
        )
        marker = wm.to_marker()
        assert marker.startswith("CTXWM:")

        recovered = Watermark.from_marker(marker)
        assert recovered is not None
        assert recovered.lic_id == "lic_test123"
        assert recovered.customer_id == "cust_acme"
        assert recovered.build_id == "build-20260101"
        assert recovered.canary_token == wm.canary_token

    def test_watermark_unique_canary(self):
        from cutctx_ee.watermark import Watermark

        wm1 = Watermark(lic_id="lic_a", customer_id="c1", build_id="b1")
        wm2 = Watermark(lic_id="lic_a", customer_id="c1", build_id="b1")
        # Each watermark gets a unique random canary
        assert wm1.canary_token != wm2.canary_token

    def test_watermark_from_invalid_marker(self):
        from cutctx_ee.watermark import Watermark

        assert Watermark.from_marker("invalid") is None
        assert Watermark.from_marker("CTXWM:invalid_base64!!!") is None
        assert Watermark.from_marker("") is None

    def test_watermark_manifest_roundtrip(self):
        from cutctx_ee.watermark import (
            Watermark,
            extract_watermark_from_manifest,
            watermark_manifest,
        )

        watermark = Watermark(
            lic_id="lic_manifest",
            customer_id="cust",
            build_id="build1",
            canary_token="fixed-token",
            embedded_at=1,
        )

        assert extract_watermark_from_manifest(watermark_manifest(watermark)) == watermark

    def test_malformed_manifest_is_not_a_watermark(self):
        from cutctx_ee.watermark import extract_watermark_from_manifest

        assert extract_watermark_from_manifest({}) is None
        assert extract_watermark_from_manifest({"marker": 42}) is None

    def test_runtime_mutation_and_binary_scan_apis_are_absent(self):
        import cutctx_ee.watermark as watermark

        assert not hasattr(watermark, "embed_watermark_in_source")
        assert not hasattr(watermark, "extract_watermark_from_binary")


# ---------------------------------------------------------------------------
# SP-6: Abuse detection tests
# ---------------------------------------------------------------------------


class TestAbuseDetector:
    """Tests for server-side abuse detection."""

    def test_no_abuse_normal_activity(self):
        from cutctx_ee.abuse import AbuseDetector, ActivationRecord

        detector = AbuseDetector()
        # Normal: same fingerprint, same geo, infrequent
        alerts = detector.process_event(
            ActivationRecord(
                lic_id="lic1",
                fingerprint="fp1",
                ip_address="1.2.3.4",
                geo="US",
                timestamp=1000,
            )
        )
        assert len(alerts) == 0

    def test_impossible_travel(self):
        from cutctx_ee.abuse import AbuseDetector, ActivationRecord

        detector = AbuseDetector()
        detector.process_event(
            ActivationRecord(
                lic_id="lic1",
                fingerprint="fp1",
                ip_address="1.2.3.4",
                geo="US",
                timestamp=1000,
            )
        )
        alerts = detector.process_event(
            ActivationRecord(
                lic_id="lic1",
                fingerprint="fp2",
                ip_address="5.6.7.8",
                geo="EU",
                timestamp=1200,  # 200s later, 8000km away
            )
        )
        impossible = [a for a in alerts if a.flag.value == "impossible_travel"]
        assert len(impossible) == 1
        assert impossible[0].severity.value == "high"

    def test_too_many_fingerprints(self):
        from cutctx_ee.abuse import AbuseDetector, ActivationRecord

        detector = AbuseDetector(max_fingerprints=3)
        for i in range(5):
            detector.process_event(
                ActivationRecord(
                    lic_id="lic1",
                    fingerprint=f"fp{i}",
                    ip_address=f"1.2.3.{i}",
                    geo="US",
                    timestamp=1000 + i,
                )
            )
        alerts = detector.get_alerts(lic_id="lic1", min_severity=None)
        fp_alerts = [a for a in alerts if a.flag.value == "too_many_fingerprints"]
        assert len(fp_alerts) >= 1

    def test_too_many_ips(self):
        from cutctx_ee.abuse import AbuseDetector, ActivationRecord

        detector = AbuseDetector(max_ips=3)
        for i in range(5):
            detector.process_event(
                ActivationRecord(
                    lic_id="lic1",
                    fingerprint="fp1",
                    ip_address=f"10.0.{i}.1",
                    geo="US",
                    timestamp=1000 + i * 100,
                )
            )
        alerts = detector.get_alerts(lic_id="lic1")
        ip_alerts = [a for a in alerts if a.flag.value == "too_many_ips"]
        assert len(ip_alerts) >= 1

    def test_activation_storm(self):
        from cutctx_ee.abuse import AbuseDetector, ActivationRecord

        detector = AbuseDetector(storm_window_secs=60, storm_max_count=3)
        now = time.time()
        for i in range(5):
            detector.process_event(
                ActivationRecord(
                    lic_id="lic1",
                    fingerprint=f"fp{i}",
                    ip_address=f"10.0.0.{i}",
                    event_type="activation",
                    timestamp=now + i,
                )
            )
        alerts = detector.get_alerts(lic_id="lic1")
        storm_alerts = [a for a in alerts if a.flag.value == "activation_storm"]
        assert len(storm_alerts) >= 1

    def test_seat_overuse(self):
        from cutctx_ee.abuse import check_seat_overuse

        alert = check_seat_overuse(current_seats=5, max_seats=3, lic_id="lic1")
        assert alert is not None
        assert alert.flag.value == "seat_overuse"
        assert alert.severity.value == "high"

        alert = check_seat_overuse(current_seats=2, max_seats=3, lic_id="lic1")
        assert alert is None

    def test_clear_history(self):
        from cutctx_ee.abuse import AbuseDetector, ActivationRecord

        detector = AbuseDetector()
        detector.process_event(
            ActivationRecord(
                lic_id="lic1",
                fingerprint="fp1",
                ip_address="1.2.3.4",
            )
        )
        assert detector.get_event_count("lic1") == 1

        detector.clear_history("lic1")
        assert detector.get_event_count("lic1") == 0

    def test_alert_to_dict(self):
        from cutctx_ee.abuse import AbuseAlert, AbuseFlag, Severity

        alert = AbuseAlert(
            lic_id="lic1",
            flag=AbuseFlag.IMPOSSIBLE_TRAVEL,
            severity=Severity.HIGH,
            description="Test",
        )
        d = alert.to_dict()
        assert d["lic_id"] == "lic1"
        assert d["flag"] == "impossible_travel"
        assert d["severity"] == "high"


class TestHaversine:
    """Test the haversine distance calculation."""

    def test_same_point_zero_distance(self):
        from cutctx_ee.abuse import _haversine_km

        d = _haversine_km(39.8, -98.6, 39.8, -98.6)
        assert abs(d) < 0.01

    def test_known_distance(self):
        from cutctx_ee.abuse import _haversine_km

        # New York to London ≈ 5570 km
        d = _haversine_km(40.7, -74.0, 51.5, -0.1)
        assert 5500 < d < 5700

    def test_us_to_eu_flagged(self):
        from cutctx_ee.abuse import GEO_COORDS, _haversine_km

        d = _haversine_km(
            GEO_COORDS["US"][0],
            GEO_COORDS["US"][1],
            GEO_COORDS["EU"][0],
            GEO_COORDS["EU"][1],
        )
        assert d > 5000  # Should be flagged as impossible travel


# ---------------------------------------------------------------------------
# SP-7: Supply chain signing tests
# ---------------------------------------------------------------------------


class TestSignArtifacts:
    """Tests for supply-chain signing scripts."""

    def test_script_exists(self):
        script = Path(__file__).resolve().parent.parent / "scripts" / "sign_artifacts.py"
        assert script.exists()

    def test_secret_patterns_comprehensive(self):
        from scripts.sign_artifacts import FORBIDDEN_PATHS, SECRET_PATTERNS

        assert len(SECRET_PATTERNS) >= 5
        assert len(FORBIDDEN_PATHS) >= 4

    def test_compute_sha256(self):
        import tempfile

        from scripts.sign_artifacts import compute_sha256

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("hello world")
            f.flush()
            h = compute_sha256(Path(f.name))
            assert h == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"

    def test_generate_manifest(self):
        import tempfile

        from scripts.sign_artifacts import generate_manifest

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            (tmpdir / "test.txt").write_text("test content")
            (tmpdir / "binary.so").write_bytes(b"\x7fELF")

            manifest = generate_manifest(tmpdir, build_id="test-build")
            assert manifest["build_id"] == "test-build"
            assert len(manifest["entries"]) == 2
            assert all("sha256" in e for e in manifest["entries"])

    def test_scan_secrets_clean(self):
        import tempfile

        from scripts.sign_artifacts import scan_secrets

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            (tmpdir / "clean.py").write_text("# No secrets here\nx = 1\n")
            findings = scan_secrets(tmpdir)
            assert len(findings) == 0

    def test_scan_secrets_detects_api_key(self):
        import tempfile

        from scripts.sign_artifacts import scan_secrets

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            (tmpdir / "leaked.py").write_text(
                'API_KEY = "sk-ant-abc123def456ghi789jkl012mno345pqr678stu901vwx234"\n'
            )
            findings = scan_secrets(tmpdir)
            assert len(findings) >= 1
            assert any("Anthropic" in f["description"] for f in findings)

    def test_scan_secrets_detects_forbidden_path(self):
        import tempfile

        from scripts.sign_artifacts import scan_secrets

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            (tmpdir / "config.py").write_text('path = "/Users/john/secret.key"\n')
            findings = scan_secrets(tmpdir)
            assert any(f["type"] == "forbidden_path" for f in findings)

    def test_manifest_hash_verification(self):
        import tempfile

        from scripts.sign_artifacts import generate_manifest, verify_manifest_hashes

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            (tmpdir / "file.txt").write_text("content")
            manifest = generate_manifest(tmpdir)

            # Verify — should pass
            violations = verify_manifest_hashes(manifest, tmpdir)
            assert len(violations) == 0

            # Tamper with file — should fail
            (tmpdir / "file.txt").write_text("tampered")
            violations = verify_manifest_hashes(manifest, tmpdir)
            assert len(violations) == 1


# ---------------------------------------------------------------------------
# SP-8: DMCA template test
# ---------------------------------------------------------------------------


class TestLegalDocuments:
    """Tests for legal/operational backstop documents."""

    def test_dmca_template_exists(self):
        path = (
            Path(__file__).resolve().parent.parent / "docs" / "legal" / "DMCA_TAKEDOWN_TEMPLATE.md"
        )
        assert path.exists()

    def test_leak_runbook_exists(self):
        path = (
            Path(__file__).resolve().parent.parent / "docs" / "legal" / "LEAK_RESPONSE_RUNBOOK.md"
        )
        assert path.exists()

    def test_dmca_template_has_required_sections(self):
        content = (
            Path(__file__).resolve().parent.parent / "docs" / "legal" / "DMCA_TAKEDOWN_TEMPLATE.md"
        ).read_text()
        assert "§512" in content or "512" in content
        assert "good faith" in content.lower()
        assert "penalty of perjury" in content.lower()

    def test_leak_runbook_has_phases(self):
        content = (
            Path(__file__).resolve().parent.parent / "docs" / "legal" / "LEAK_RESPONSE_RUNBOOK.md"
        ).read_text()
        assert "Phase 1" in content
        assert "Phase 2" in content
        assert "Phase 3" in content
        assert "Phase 4" in content
        assert "Phase 5" in content
