"""CutCtx Python SDK client."""

from __future__ import annotations

import threading
from typing import Any

try:
    import requests as _requests
except ImportError:
    _requests = None  # type: ignore[assignment]


class CutCtxClient:
    """Client for the CutCtx compression proxy.

    Args:
        proxy_url: Base URL of the CutCtx proxy (default: http://localhost:8787).
        api_key: License key sent as X-CutCtx-Key header.
        model: Target model name for cost estimation.
    """

    def __init__(
        self,
        proxy_url: str = "http://localhost:8787",
        api_key: str | None = None,
        model: str = "claude-sonnet-4-5",
    ) -> None:
        if _requests is None:
            raise ImportError(
                "requests library is required: pip install requests"
            )
        self._proxy_url = proxy_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._lock = threading.Lock()

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["X-CutCtx-Key"] = self._api_key
        return headers

    def compress(self, messages: list[dict[str, Any]], model: str | None = None) -> list[dict[str, Any]]:
        """Compress messages through the CutCtx proxy.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            model: Override model for this request.

        Returns:
            Compressed list of messages.
        """
        payload = {"messages": messages, "model": model or self._model}
        resp = _requests.post(
            f"{self._proxy_url}/v1/compress",
            json=payload,
            headers=self._headers(),
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json().get("messages", messages)

    def retrieve(self, ref: str) -> str:
        """Retrieve original content for a compression pointer.

        Args:
            ref: Compression reference string (e.g., '<<ccr:abc123>>').

        Returns:
            Original uncompressed content.
        """
        resp = _requests.get(
            f"{self._proxy_url}/v1/retrieve/{ref}",
            headers=self._headers(),
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("content", "")

    def stats(self) -> dict[str, Any]:
        """Get proxy statistics.

        Returns:
            Dictionary with request counts, token savings, etc.
        """
        headers = self._headers()
        admin_key = self._api_key
        if admin_key:
            headers["Authorization"] = f"Bearer {admin_key}"
        resp = _requests.get(
            f"{self._proxy_url}/stats",
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def health(self) -> dict[str, Any]:
        """Check proxy health.

        Returns:
            Health status dictionary.
        """
        resp = _requests.get(
            f"{self._proxy_url}/livez",
            timeout=5,
        )
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            return {"status": "ok"}
