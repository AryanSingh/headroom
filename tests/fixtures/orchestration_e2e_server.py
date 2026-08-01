"""Launch an isolated production proxy for dashboard Playwright tests."""

from __future__ import annotations

import argparse
import os
import tempfile
import threading
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=48787)
    parser.add_argument("--provider-port", type=int, default=48788)
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
                "CUTCTX_ORCHESTRATION_MASTER_KEY": "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
                "CUTCTX_PREFIX_TRACKER_DB_PATH": str(root / "prefix-tracker.db"),
                "CUTCTX_SAVINGS_FILE": str(root / "savings.json"),
                "CUTCTX_SAFE_SAVINGS_EXPERIENCE": "1",
                "CUTCTX_TELEMETRY": "0",
                "TOKENIZERS_PARALLELISM": "false",
            }
        )

        import uvicorn
        from fastapi import FastAPI

        from cutctx.proxy.models import ProxyConfig
        from cutctx.proxy.server import create_app

        provider_app = FastAPI()

        @provider_app.get("/v1/models")
        async def models() -> dict[str, object]:
            return {
                "data": [
                    {
                        "id": "gpt-5.4-mini",
                        "display_name": "GPT-5.4 Mini (E2E)",
                        "capabilities": ["reasoning", "tool_calling", "streaming"],
                        "context_length": 128_000,
                        "max_output_tokens": 16_384,
                    }
                ]
            }

        @provider_app.post("/v1/chat/completions")
        async def completions() -> dict[str, object]:
            return {
                "id": "chatcmpl-live-e2e",
                "object": "chat.completion",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }

        provider_server = uvicorn.Server(
            uvicorn.Config(
                provider_app,
                host=args.host,
                port=args.provider_port,
                log_level="warning",
            )
        )
        provider_thread = threading.Thread(target=provider_server.run, daemon=True)
        provider_thread.start()
        for _ in range(200):
            if provider_server.started:
                break
            time.sleep(0.01)
        if not provider_server.started:
            raise RuntimeError("Local E2E provider did not start")

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
        try:
            uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
        finally:
            provider_server.should_exit = True
            provider_thread.join(timeout=5)


if __name__ == "__main__":
    main()
