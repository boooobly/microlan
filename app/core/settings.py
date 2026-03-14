"""Persistent UI settings storage via QSettings."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSettings

from app.core.config import (
    APP_NAME,
    APP_ORG,
    DEFAULT_AUDIO_PORT,
    DEFAULT_SIGNALING_PORT,
    MIC_GAIN_DEFAULT,
    NOISE_GATE_ENABLED_DEFAULT,
    NOISE_GATE_THRESHOLD_DEFAULT,
    NOISE_SUPPRESSION_ENABLED_DEFAULT,
)


@dataclass
class AppSettingsData:
    local_signaling_port: int = DEFAULT_SIGNALING_PORT
    local_audio_port: int = DEFAULT_AUDIO_PORT
    peer_ip: str = ""
    peer_signaling_port: int = DEFAULT_SIGNALING_PORT
    peer_audio_port: int = DEFAULT_AUDIO_PORT
    selected_input_device: int | None = None
    selected_output_device: int | None = None
    mic_gain: float = MIC_GAIN_DEFAULT
    noise_gate_enabled: bool = NOISE_GATE_ENABLED_DEFAULT
    noise_gate_threshold: float = NOISE_GATE_THRESHOLD_DEFAULT
    noise_suppression_enabled: bool = NOISE_SUPPRESSION_ENABLED_DEFAULT
    mute_microphone: bool = False


class SettingsStore:
    def __init__(self) -> None:
        self._settings = QSettings(APP_ORG, APP_NAME)

    def load(self) -> AppSettingsData:
        data = AppSettingsData()
        data.local_signaling_port = self._get_int("network/local_signaling_port", data.local_signaling_port)
        data.local_audio_port = self._get_int("network/local_audio_port", data.local_audio_port)
        data.peer_ip = str(self._settings.value("peer/ip", data.peer_ip))
        data.peer_signaling_port = self._get_int("peer/signaling_port", data.peer_signaling_port)
        data.peer_audio_port = self._get_int("peer/audio_port", data.peer_audio_port)
        data.selected_input_device = self._get_optional_int("audio/input_device", None)
        data.selected_output_device = self._get_optional_int("audio/output_device", None)
        data.mic_gain = self._get_float("audio/mic_gain", data.mic_gain)
        data.noise_gate_enabled = self._get_bool("audio/noise_gate_enabled", data.noise_gate_enabled)
        data.noise_gate_threshold = self._get_float("audio/noise_gate_threshold", data.noise_gate_threshold)
        data.noise_suppression_enabled = self._get_bool(
            "audio/noise_suppression_enabled",
            data.noise_suppression_enabled,
        )
        data.mute_microphone = self._get_bool("audio/mute_microphone", data.mute_microphone)
        return data

    def save(self, data: AppSettingsData) -> None:
        self._settings.setValue("network/local_signaling_port", data.local_signaling_port)
        self._settings.setValue("network/local_audio_port", data.local_audio_port)
        self._settings.setValue("peer/ip", data.peer_ip)
        self._settings.setValue("peer/signaling_port", data.peer_signaling_port)
        self._settings.setValue("peer/audio_port", data.peer_audio_port)
        self._settings.setValue("audio/input_device", data.selected_input_device)
        self._settings.setValue("audio/output_device", data.selected_output_device)
        self._settings.setValue("audio/mic_gain", data.mic_gain)
        self._settings.setValue("audio/noise_gate_enabled", data.noise_gate_enabled)
        self._settings.setValue("audio/noise_gate_threshold", data.noise_gate_threshold)
        self._settings.setValue("audio/noise_suppression_enabled", data.noise_suppression_enabled)
        self._settings.setValue("audio/mute_microphone", data.mute_microphone)
        self._settings.sync()

    def _get_int(self, key: str, default: int) -> int:
        raw = self._settings.value(key, default)
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default

    def _get_optional_int(self, key: str, default: int | None) -> int | None:
        raw = self._settings.value(key, default)
        if raw in (None, "", "None"):
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default

    def _get_float(self, key: str, default: float) -> float:
        raw = self._settings.value(key, default)
        try:
            return float(raw)
        except (TypeError, ValueError):
            return default

    def _get_bool(self, key: str, default: bool) -> bool:
        raw = self._settings.value(key, default)
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str):
            return raw.strip().lower() in {"1", "true", "yes", "on"}
        return bool(raw)
