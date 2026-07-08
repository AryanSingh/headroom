from __future__ import annotations

from cutctx.proxy.savings_tracker import PERSISTED_SAVINGS_SOURCES
from cutctx.savings import SavingsSource


def test_rtk_cli_filtering_is_canonical_savings_source() -> None:
    source = SavingsSource.RTK_CLI_FILTERING

    assert source.value == "rtk_cli_filtering"
    assert source.label == "RTK CLI Filtering"
    assert "RTK" in source.description
    assert source.value in PERSISTED_SAVINGS_SOURCES
