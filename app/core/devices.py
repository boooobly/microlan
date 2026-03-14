"""Audio device helpers for diagnostics and GUI selection."""

from __future__ import annotations

from typing import Any, Callable

import sounddevice as sd


def _safe_query_devices() -> list[dict[str, Any]]:
    devices = sd.query_devices()
    return [dict(d) for d in devices]


def list_input_devices_with_indices() -> list[tuple[int, dict[str, Any]]]:
    return [(idx, dev) for idx, dev in enumerate(_safe_query_devices()) if dev.get("max_input_channels", 0) > 0]


def list_output_devices_with_indices() -> list[tuple[int, dict[str, Any]]]:
    return [(idx, dev) for idx, dev in enumerate(_safe_query_devices()) if dev.get("max_output_channels", 0) > 0]


def get_default_input_device_index() -> int | None:
    default = sd.default.device
    if isinstance(default, (tuple, list)):
        return int(default[0]) if default[0] is not None and int(default[0]) >= 0 else None
    return int(default) if default is not None and int(default) >= 0 else None


def get_default_output_device_index() -> int | None:
    default = sd.default.device
    if isinstance(default, (tuple, list)):
        return int(default[1]) if default[1] is not None and int(default[1]) >= 0 else None
    return int(default) if default is not None and int(default) >= 0 else None


def human_device_label(index: int, info: dict[str, Any]) -> str:
    name = str(info.get("name", "Неизвестно"))
    in_ch = int(info.get("max_input_channels", 0))
    out_ch = int(info.get("max_output_channels", 0))
    return f"[{index}] {name} (вх:{in_ch} вых:{out_ch})"


def resolve_device_index_or_default(
    selected_index: int | None,
    *,
    direction: str,
    on_log: Callable[[str], None] | None = None,
) -> int | None:
    """Validate selected device index and fallback to default if needed."""

    if direction not in {"input", "output"}:
        raise ValueError("параметр direction должен быть input или output")

    available = dict(
        list_input_devices_with_indices() if direction == "input" else list_output_devices_with_indices()
    )
    if selected_index is not None and selected_index in available:
        return selected_index

    fallback = get_default_input_device_index() if direction == "input" else get_default_output_device_index()
    if fallback is not None and fallback in available:
        if selected_index is not None and on_log:
            on_log(f"устройство {direction} {selected_index} недоступно, переключено на устройство по умолчанию {fallback}")
        return fallback

    if on_log:
        on_log(f"предупреждение: нет доступного {direction} аудиоустройства")
    return None


def get_device_name(device_index: int | None) -> str:
    if device_index is None:
        return "Неизвестно"
    try:
        info = sd.query_devices(device_index)
        return str(info.get("name", "Неизвестно"))
    except Exception:  # noqa: BLE001
        return "Неизвестно"
