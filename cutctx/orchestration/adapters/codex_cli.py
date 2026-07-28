from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any

from ..artifact_store import ArtifactBlobStore
from ..harness_adapter import ArtifactRef, HarnessCapabilities, HarnessRunContext, HarnessRunResult


class CodexCliAdapter:
    harness_id = "codex_cli"

    def __init__(
        self,
        *,
        blob_store: ArtifactBlobStore,
        binary: str | None = None,
    ) -> None:
        self.blob_store = blob_store
        self.binary = binary or os.environ.get("CUTCTX_CODEX_CLI_BIN", "codex")
        self._active: dict[str, asyncio.subprocess.Process] = {}

    def capabilities(self) -> HarnessCapabilities:
        return HarnessCapabilities(stream=False, cancel=True, resume=False, artifact_emit=True)

    async def health(self) -> dict[str, Any]:
        return {"harness": self.harness_id, "binary": self.binary}

    async def run(self, ctx: HarnessRunContext) -> HarnessRunResult:
        run_id = ctx.run_id or uuid.uuid4().hex
        env = {**os.environ, **ctx.env}
        env.setdefault("CUTCTX_PROXY_URL", os.environ.get("CUTCTX_PROXY_URL", "http://127.0.0.1:8787"))
        proc = await asyncio.create_subprocess_exec(
            self.binary,
            "exec",
            ctx.prompt,
            cwd=ctx.workspace_ref or None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        self._active[run_id] = proc
        stdout, stderr = await proc.communicate()
        self._active.pop(run_id, None)
        status = "completed" if proc.returncode == 0 else "failed"
        stdout_ref = self.blob_store.put(stdout, media_type="text/plain").blob_id
        stderr_ref = self.blob_store.put(stderr, media_type="text/plain").blob_id
        artifacts: list[ArtifactRef] = []
        text = stdout.decode("utf-8", errors="replace")
        if "diff --git" in text:
            artifacts.append(
                self.blob_store.ref_for_text(text, media_type="text/x-patch", provenance={"harness": self.harness_id})
            )
        return HarnessRunResult(
            status=status,
            artifacts=artifacts,
            stdout_ref=stdout_ref,
            stderr_ref=stderr_ref,
            metadata={"returncode": str(proc.returncode or 0)},
        )

    async def cancel(self, run_id: str) -> None:
        proc = self._active.get(run_id)
        if proc is not None and proc.returncode is None:
            proc.terminate()
