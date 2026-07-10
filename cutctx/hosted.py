"""Client helpers for Cutctx hosted compression."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class HostedCompressionResult:
    """Result returned by the hosted compression API."""

    text: str | None
    messages: list[dict[str, Any]]
    tokens_before: int
    tokens_after: int
    tokens_saved: int
    compression_ratio: float
    transforms_applied: list[str] = field(default_factory=list)
    model: str = ""
    input_kind: str = "messages"
    compatibility_mode: str = "messages"
    raw: dict[str, Any] = field(default_factory=dict)


class HostedCompressionError(RuntimeError):
    """Raised when the hosted compression API returns an error response."""

    def __init__(self, message: str, *, status_code: int, payload: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class HostedCompressionClient:
    """Small HTTP client for ``POST /v1/hosted/compress``.

    The endpoint is intentionally simpler than the proxy API: callers pass
    either raw ``text`` or chat ``messages`` and receive compressed text/messages
    plus token savings metadata.
    """

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def compress_text(
        self,
        text: str,
        *,
        model: str = "gpt-4o",
        **options: Any,
    ) -> HostedCompressionResult:
        """Compress a raw text payload."""
        return self._post({"text": text, "model": model, **options})

    def compress_messages(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str = "gpt-4o",
        **options: Any,
    ) -> HostedCompressionResult:
        """Compress chat messages."""
        return self._post({"messages": messages, "model": model, **options})

    def _post(self, payload: dict[str, Any]) -> HostedCompressionResult:
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover - dependency is installed in test env
            raise HostedCompressionError(
                "httpx is required for HostedCompressionClient",
                status_code=0,
                payload=None,
            ) from exc

        headers: dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = httpx.post(
            f"{self.base_url}/v1/hosted/compress",
            json=payload,
            headers=headers,
            timeout=self.timeout,
        )
        try:
            data = response.json()
        except ValueError:
            data = {"error": {"message": response.text}}

        if response.status_code >= 400:
            error = data.get("error") if isinstance(data, dict) else None
            message = "Hosted compression request failed"
            if isinstance(error, dict) and error.get("message"):
                message = str(error["message"])
            elif isinstance(data, dict) and data.get("detail"):
                message = str(data["detail"])
            raise HostedCompressionError(
                message,
                status_code=response.status_code,
                payload=data,
            )

        return HostedCompressionResult(
            text=data.get("text"),
            messages=list(data.get("messages") or []),
            tokens_before=int(data.get("tokens_before") or 0),
            tokens_after=int(data.get("tokens_after") or 0),
            tokens_saved=int(data.get("tokens_saved") or 0),
            compression_ratio=float(data.get("compression_ratio") or 0.0),
            transforms_applied=list(data.get("transforms_applied") or []),
            model=str(data.get("model") or payload.get("model") or ""),
            input_kind=str(data.get("input_kind") or "messages"),
            compatibility_mode=str(
                data.get("compatibility_mode")
                or payload.get("compatibility_mode")
                or ("tool_output" if "text" in payload else "messages")
            ),
            raw=data,
        )
