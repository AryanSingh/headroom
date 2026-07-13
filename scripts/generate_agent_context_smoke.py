from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

from cutctx.cli.report import _build_agent_context_report, _render_agent_context_report
from cutctx.paths import request_history_path
from cutctx.proxy.models import ProxyConfig
from cutctx.proxy.server import create_app


def _compressible_messages(batch_id: int, rows: int = 80) -> list[dict[str, object]]:
    payload = json.dumps(
        [
            {
                "id": i,
                "batch": batch_id,
                "status": "error" if i % 9 == 0 else "ok",
                "message": f"repeated agent-context smoke row {i % 5}",
                "component": "smoke-runner",
            }
            for i in range(rows)
        ],
        indent=2,
    )
    return [
        {"role": "user", "content": "Summarize this tool output and keep errors visible."},
        {
            "role": "tool",
            "tool_call_id": f"smoke_{batch_id}",
            "content": payload,
        },
    ]


def generate_agent_context_smoke(
    *,
    workspace_dir: Path,
    request_count: int = 24,
    markdown_output: Path,
    json_output: Path,
) -> dict[str, object]:
    workspace_dir.mkdir(parents=True, exist_ok=True)
    (workspace_dir / "logs").mkdir(parents=True, exist_ok=True)

    previous_workspace = os.environ.get("CUTCTX_WORKSPACE_DIR")
    previous_admin_key = os.environ.get("CUTCTX_ADMIN_API_KEY")
    os.environ["CUTCTX_WORKSPACE_DIR"] = str(workspace_dir)
    os.environ["CUTCTX_ADMIN_API_KEY"] = "agent-context-smoke-admin"

    try:
        app = create_app(
            ProxyConfig(
                cache_enabled=False,
                rate_limit_enabled=False,
                log_requests=True,
                log_file=str(request_history_path()),
                admin_api_key="agent-context-smoke-admin",
            )
        )

        with TestClient(app) as client:
            headers = {"x-cutctx-admin-key": "agent-context-smoke-admin"}
            for batch_id in range(request_count):
                response = client.post(
                    "/v1/compress",
                    json={
                        "messages": _compressible_messages(batch_id),
                        "model": "gpt-4o",
                    },
                    headers=headers,
                )
                if response.status_code != 200:
                    raise RuntimeError(
                        f"compress request {batch_id} failed: {response.status_code} {response.text}"
                    )

        payload = _build_agent_context_report(days=0)
        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.parent.mkdir(parents=True, exist_ok=True)
        markdown_output.write_text(
            _render_agent_context_report(payload, "markdown"),
            encoding="utf-8",
        )
        json_output.write_text(
            _render_agent_context_report(payload, "json"),
            encoding="utf-8",
        )
        return payload
    finally:
        if previous_workspace is None:
            os.environ.pop("CUTCTX_WORKSPACE_DIR", None)
        else:
            os.environ["CUTCTX_WORKSPACE_DIR"] = previous_workspace
        if previous_admin_key is None:
            os.environ.pop("CUTCTX_ADMIN_API_KEY", None)
        else:
            os.environ["CUTCTX_ADMIN_API_KEY"] = previous_admin_key


def main() -> None:
    workspace = Path("artifacts/agent-context-smoke-workspace")
    markdown_output = Path("artifacts/agent-context-smoke-report.md")
    json_output = Path("artifacts/agent-context-smoke-report.json")
    payload = generate_agent_context_smoke(
        workspace_dir=workspace,
        request_count=24,
        markdown_output=markdown_output,
        json_output=json_output,
    )
    print(
        json.dumps(
            {
                "requests": payload["summary"]["requests"],
                "telemetry_requests_observed": payload["telemetry"]["requests_observed"],
                "tokens_saved": payload["summary"]["tokens_saved"],
                "markdown_output": str(markdown_output),
                "json_output": str(json_output),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
