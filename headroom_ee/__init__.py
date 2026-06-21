# SPDX-License-Identifier: LicenseRef-Headroom-Commercial
# Copyright (c) 2025-2026 Cutctx Labs. All rights reserved.
# Proprietary and confidential. NOT licensed under Apache-2.0.
# See headroom_ee/LICENSE (Cutctx Commercial License) and ../LICENSING.md.
"""headroom_ee — Cutctx commercial ("enterprise edition") components.

This package holds the proprietary, All-Rights-Reserved implementations that back
the entitlement-gated features exposed through the open-source ``headroom`` client.
It is a SEPARATE distribution from the Apache-2.0 ``headroom`` package and is
governed by the Cutctx Commercial License (``headroom_ee/LICENSE``).

The open-source ``headroom.<module>`` import paths are thin Apache-2.0 shims that
re-export the implementations here when this commercial distribution is installed.
See ``../LICENSING.md`` for the authoritative open-core boundary.

Do not redistribute.
"""

from __future__ import annotations

__all__: list[str] = []
__license__ = "LicenseRef-Headroom-Commercial"
