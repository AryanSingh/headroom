"""Launch an isolated production proxy for dashboard Playwright tests."""

from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=48787)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="cutctx-orchestrator-e2e-") as directory:
        root = Path(directory)
        os.environ.update(
            {
                "CUTCTX_ADMIN_API_KEY": "test-admin-key-for-live-e2e",
                "CUTCTX_CCR_BACKEND": "memory",
                "CUTCTX_WEBHOOKS_IN_MEMORY": "1",
                "CUTCTX_ORCHESTRATION_DIR": str(root / "orchestration"),
                "CUTCTX_ORCHESTRATION_CONFIG": str(root / "orchestration.json"),
                "CUTCTX_ORCHESTRATION_MASTER_KEY": "live-e2e-master-key",
                "CUTCTX_PREFIX_TRACKER_DB_PATH": str(root / "prefix-tracker.db"),
                "CUTCTX_SAVINGS_FILE": str(root / "savings.json"),
                "CUTCTX_TELEMETRY": "0",
                "TOKENIZERS_PARALLELISM": "false",
            }
        )

        from cutctx.proxy.models import ProxyConfig
        from cutctx.proxy.server import create_app
        import uvicorn

        app = create_app(
            ProxyConfig(
                host=args.host,
                port=args.port,
                backend="mock",
                cache_enabled=False,
                admin_api_key="test-admin-key-for-live-e2e",
                admin_auth_failures_per_minute=0,
                prefix_freeze_db_path=str(root / "prefix-tracker.db"),
            )
        )
        uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
