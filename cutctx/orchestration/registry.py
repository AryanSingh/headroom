"""Dynamic, capability-rich model registry."""

from __future__ import annotations

import builtins
import json
import os
import tempfile
import threading
from pathlib import Path

from .models import Capability, ModelRecord, to_dict
from .providers import ProviderAdapter


class DynamicModelRegistry:
    def __init__(self, cache_path: Path | str | None = None) -> None:
        self.cache_path = Path(cache_path) if cache_path else None
        self._models: dict[str, ModelRecord] = {}
        self._configured_keys: set[str] = set()
        self._lock = threading.RLock()
        self._load_cache()
        self._seed_legacy_models()

    def register(self, model: ModelRecord) -> ModelRecord:
        with self._lock:
            self._register_unlocked(model)
        return model

    def register_many(self, models: list[ModelRecord]) -> None:
        with self._lock:
            for model in models:
                self._register_unlocked(model)
            self._save_cache()

    def sync_configured(self, models: list[ModelRecord]) -> None:
        """Atomically replace models owned by configuration, pruning removed entries."""
        with self._lock:
            for key in self._configured_keys:
                self._models.pop(key, None)
            self._configured_keys = {model.deployment_key for model in models}
            for model in models:
                self._register_unlocked(model)
            self._save_cache()

    def _register_unlocked(self, model: ModelRecord) -> None:
        if model.account_id:
            self._models.pop(model.key, None)
        elif any(
            existing.account_id and existing.key == model.key for existing in self._models.values()
        ):
            return
        self._models[model.deployment_key] = model

    def get(self, key: str) -> ModelRecord | None:
        with self._lock:
            direct = self._models.get(key)
            if direct is not None and direct.account_id:
                return direct
            canonical_matches = [model for model in self._models.values() if model.key == key]
            if len(canonical_matches) == 1:
                return canonical_matches[0]
            if canonical_matches:
                return None
            id_matches = [model for model in self._models.values() if model.id == key]
            return id_matches[0] if len(id_matches) == 1 else None

    def list(
        self,
        *,
        provider: str | None = None,
        required_capabilities: set[str] | None = None,
        available_only: bool = False,
    ) -> list[ModelRecord]:
        required = required_capabilities or set()
        with self._lock:
            return sorted(
                (
                    model
                    for model in self._models.values()
                    if (provider is None or model.provider == provider)
                    and (not available_only or model.available)
                    and model.supports(required)
                ),
                key=lambda item: item.deployment_key,
            )

    async def refresh(self, adapter: ProviderAdapter) -> builtins.list[ModelRecord]:
        models = await adapter.refresh_models()
        account_id = adapter.account.id
        provider = adapter.account.provider
        with self._lock:
            stale = [
                key
                for key, model in self._models.items()
                if model.provider == provider and model.account_id == account_id
            ]
            for key in stale:
                del self._models[key]
            for model in models:
                model.account_id = account_id
                self._register_unlocked(model)
            self._save_cache()
        return models

    def mark_provider_available(
        self,
        provider: str,
        available: bool,
        *,
        account_id: str | None = None,
    ) -> None:
        with self._lock:
            for model in self._models.values():
                if model.provider == provider and (
                    account_id is None or model.account_id == account_id
                ):
                    model.available = available

    def _seed_legacy_models(self) -> None:
        try:
            from cutctx.models.registry import ModelRegistry

            for info in ModelRegistry.list_models():
                capabilities = set()
                if info.supports_tools:
                    capabilities.add(Capability.TOOL_CALLING.value)
                if info.supports_vision:
                    capabilities.add(Capability.VISION.value)
                if info.supports_streaming:
                    capabilities.add(Capability.STREAMING.value)
                if info.supports_json_mode:
                    capabilities.update(
                        {Capability.JSON_MODE.value, Capability.STRUCTURED_OUTPUTS.value}
                    )
                if info.context_window >= 128_000:
                    capabilities.add(Capability.LONG_CONTEXT.value)
                record = ModelRecord(
                    provider=info.provider,
                    id=info.name,
                    display_name=info.name,
                    capabilities=capabilities,
                    context_length=info.context_window,
                    max_output_tokens=info.max_output_tokens,
                    recommended_usage=[info.notes] if info.notes else [],
                )
                if not any(model.key == record.key for model in self._models.values()):
                    self._models[record.deployment_key] = record
        except Exception:
            pass

        record = ModelRecord(
            provider="openai",
            id="gpt-5.4-mini",
            display_name="GPT-5.4 Mini",
            capabilities={
                Capability.REASONING.value,
                Capability.STREAMING.value,
                Capability.TOOL_CALLING.value,
                Capability.JSON_MODE.value,
                Capability.STRUCTURED_OUTPUTS.value,
                Capability.LONG_CONTEXT.value,
            },
            available=True,
            recommended_usage=["Fast worker", "Cost-efficient reasoning", "Coding subtasks"],
        )
        if not any(model.key == record.key for model in self._models.values()):
            self._models[record.deployment_key] = record

    def _load_cache(self) -> None:
        if self.cache_path is None or not self.cache_path.exists():
            return
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
            for item in payload.get("models", []):
                item = dict(item)
                item["capabilities"] = set(item.get("capabilities", []))
                model = ModelRecord(**item)
                self._register_unlocked(model)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return

    def _save_cache(self) -> None:
        if self.cache_path is None:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{self.cache_path.name}.", dir=self.cache_path.parent
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(
                    {"version": 1, "models": [to_dict(model) for model in self.list()]},
                    handle,
                    indent=2,
                    sort_keys=True,
                )
                handle.write("\n")
            os.replace(temporary, self.cache_path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
