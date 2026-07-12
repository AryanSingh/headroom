from __future__ import annotations

from cutctx.proxy.helpers import extract_tags


def test_extract_tags_skips_sensitive_internal_headers() -> None:
    tags = extract_tags(
        {
            "X-Cutctx-Project": "headroom",
            "x-cutctx-admin-key": "secret-admin-key",
            "x-cutctx-api-key": "secret-api-key",
            "x-cutctx-bypass": "true",
        }
    )

    assert tags["project"] == "headroom"
    assert tags["bypass"] == "true"
    assert "admin-key" not in tags
    assert "api-key" not in tags

