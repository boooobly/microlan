"""Audio device helpers (prepared for future GUI selection)."""

from __future__ import annotations

from typing import Any

import sounddevice as sd


def list_input_devices() -> list[dict[str, Any]]:
    devices = sd.query_devices()
    return [d for d in devices if d.get("max_input_channels", 0) > 0]


def list_output_devices() -> list[dict[str, Any]]:
    devices = sd.query_devices()
    return [d for d in devices if d.get("max_output_channels", 0) > 0]


def get_default_input_device() -> Any:
    defaults = sd.default.device
    return defaults[0] if isinstance(defaults, (list, tuple)) else defaults


def get_default_output_device() -> Any:
    defaults = sd.default.device
    return defaults[1] if isinstance(defaults, (list, tuple)) else defaults


def get_device_name(device_index: Any) -> str:
    try:
        if device_index is None:
            return "Unknown"
        if isinstance(device_index, str):
            return device_index
        info = sd.query_devices(device_index)
        return str(info.get("name", "Unknown"))
    except Exception:  # noqa: BLE001
        return "Unknown"
