"""Versioned, layered orchestration configuration persistence."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

from .models import OrchestrationConfig, config_from_dict, to_dict


class LayeredConfigStore:
    """Merge global → user → workspace → project configuration layers.

    List entities are merged by ``id`` and later layers replace earlier
    entities.  Settings and metadata are deep-merged.  Writes target one
    explicit layer and use atomic replacement.
    """

    ORDER = ("global", "user", "workspace", "project")

    def __init__(self, paths: dict[str, Path | str] | None = None) -> None:
        self.paths = {key: Path(value) for key, value in (paths or {}).items()}
        self._lock = threading.RLock()

    def load(self) -> OrchestrationConfig:
        with self._lock:
            return config_from_dict(self._load_merged())

    def preview(
        self, config: OrchestrationConfig, *, layer: str = "project"
    ) -> OrchestrationConfig:
        """Return the effective config if ``config`` replaced ``layer``, without writing."""
        if layer not in self.ORDER:
            raise ValueError(f"Unknown config layer: {layer}")
        if self.paths.get(layer) is None:
            raise ValueError(f"No path configured for {layer} orchestration config")
        with self._lock:
            return config_from_dict(self._load_merged(override=(layer, to_dict(config))))

    def _load_merged(self, *, override: tuple[str, dict[str, Any]] | None = None) -> dict[str, Any]:
        merged: dict[str, Any] = {"version": 1}
        override_layer, override_payload = override or (None, None)
        for layer in self.ORDER:
            if layer == override_layer:
                payload = override_payload
            else:
                path = self.paths.get(layer)
                if path is None or not path.exists():
                    continue
                with path.open("r", encoding="utf-8") as handle:
                    payload = json.load(handle)
            if payload is not None:
                merged = self._merge(merged, payload)
        return merged

    def save(self, config: OrchestrationConfig, *, layer: str = "project") -> None:
        self.save_payload(to_dict(config), layer=layer)

    def prepare_provider_patch(
        self,
        provider_id: str,
        values: dict[str, Any],
        *,
        layer: str = "project",
    ) -> tuple[dict[str, Any], OrchestrationConfig]:
        """Create a minimal provider override without flattening other layers."""
        if layer not in self.ORDER:
            raise ValueError(f"Unknown config layer: {layer}")
        if self.paths.get(layer) is None:
            raise ValueError(f"No path configured for {layer} orchestration config")
        with self._lock:
            payload = self._layer_payload(layer)
            providers = payload.setdefault("providers", [])
            if not isinstance(providers, list):
                raise ValueError(f"Invalid providers configuration in {layer} layer")
            for item in providers:
                if isinstance(item, dict) and str(item.get("id", "")) == provider_id:
                    item.update(values)
                    break
            else:
                providers.append({"id": provider_id, **values})
            effective = config_from_dict(self._load_merged(override=(layer, payload)))
            return payload, effective

    def save_payload(self, payload: dict[str, Any], *, layer: str = "project") -> None:
        if layer not in self.ORDER:
            raise ValueError(f"Unknown config layer: {layer}")
        path = self.paths.get(layer)
        if path is None:
            raise ValueError(f"No path configured for {layer} orchestration config")
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(payload, handle, indent=2, sort_keys=True)
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)

    def _layer_payload(self, layer: str) -> dict[str, Any]:
        path = self.paths.get(layer)
        if path is None or not path.exists():
            return {"version": 1}
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError(f"Invalid configuration object in {layer} layer")
        return payload

    @classmethod
    def _merge(cls, base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
        result = dict(base)
        for key, value in overlay.items():
            if key in {"providers", "models", "roles", "profiles", "bindings"} and isinstance(
                value, list
            ):

                def entity_id(item: dict[str, Any], entity_key: str = key) -> str | None:
                    if entity_key == "models":
                        provider = item.get("provider")
                        account_id = item.get("account_id")
                        model = item.get("id")
                        if not provider or not model:
                            return None
                        return (
                            f"{provider}:{account_id}:{model}"
                            if account_id
                            else f"{provider}:{model}"
                        )
                    identifier = item.get("id")
                    return str(identifier) if identifier is not None else None

                indexed = {
                    str(entity_id(item)): dict(item)
                    for item in result.get(key, [])
                    if isinstance(item, dict) and entity_id(item) is not None
                }
                order = list(indexed)
                for item in value:
                    if not isinstance(item, dict) or entity_id(item) is None:
                        continue
                    item_id = str(entity_id(item))
                    if item_id not in indexed:
                        order.append(item_id)
                    indexed[item_id] = cls._merge(indexed.get(item_id, {}), item)
                result[key] = [indexed[item_id] for item_id in order]
            elif (
                key == "settings" and isinstance(value, dict) and isinstance(result.get(key), dict)
            ):
                result[key] = cls._merge_settings(result[key], value)
            elif isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = cls._merge(result[key], value)
            else:
                result[key] = value
        return result

    @classmethod
    def _merge_settings(cls, base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
        """Merge policy limits monotonically across config layers.

        A lower-precedence organization/workspace policy must never be broadened
        by a project layer. Empty lists mean unrestricted only when no earlier
        layer set a limit; once a limit exists, an empty overlay preserves it.
        """
        result = dict(base)
        constrained_lists = {
            "allowed_providers",
            "allowed_regions",
            "allowed_data_classifications",
        }
        for key, value in overlay.items():
            if key in constrained_lists:
                if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                    raise ValueError(f"settings.{key} must be a list of strings")
                previous = result.get(key, [])
                if not isinstance(previous, list):
                    raise ValueError(f"settings.{key} must be a list of strings")
                if previous and value:
                    previous_values = {item.casefold() for item in previous}
                    result[key] = [item for item in value if item.casefold() in previous_values]
                elif previous:
                    result[key] = list(previous)
                else:
                    result[key] = list(value)
                continue
            result[key] = value
        return result


def default_config_paths(data_dir: Path | str | None = None) -> dict[str, Path]:
    root = Path(
        data_dir or os.environ.get("CUTCTX_ORCHESTRATION_DIR", "~/.cutctx/orchestration")
    ).expanduser()
    project_path = Path(
        os.environ.get("CUTCTX_ORCHESTRATION_CONFIG", Path.cwd() / ".cutctx" / "orchestration.json")
    ).expanduser()
    return {
        "global": root / "global.json",
        "user": root / "user.json",
        "workspace": root / "workspace.json",
        "project": project_path,
    }
