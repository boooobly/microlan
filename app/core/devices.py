"""Audio device diagnostics helpers."""

from __future__ import annotations

from typing import Any

import sounddevice as sd


def list_input_devices() -> list[dict[str, Any]]:
    return [d for d in sd.query_devices() if d.get("max_input_channels", 0) > 0]


def list_output_devices() -> list[dict[str, Any]]:
    return [d for d in sd.query_devices() if d.get("max_output_channels", 0) > 0]


def get_default_input_device() -> Any:
    defaults = sd.default.device
    return defaults[0] if isinstance(defaults, (tuple, list)) else defaults


def get_default_output_device() -> Any:
    defaults = sd.default.device
    return defaults[1] if isinstance(defaults, (tuple, list)) else defaults


def get_device_name(device_index: Any) -> str:
    try:
        if device_index is None:
            return "Unknown"
        info = sd.query_devices(device_index)
        return str(info.get("name", "Unknown"))
    except Exception:  # noqa: BLE001
        return "Unknown"
