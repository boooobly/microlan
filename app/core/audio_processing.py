"""Audio DSP helpers for mic pipeline, including optional RNNoise backend."""

from __future__ import annotations

from typing import Callable

import numpy as np

RNNOISE_FRAME_SIZE = 480  # 10 ms at 48 kHz

_BACKEND_READY = False
_BACKEND_NAME = "Недоступно"
_BACKEND_ERROR: str | None = None
_BACKEND_WARNED = False
_RNNOISE_CLASS = None

# Try loading known Python bindings without hard dependency.
try:
    from rnnoise import RNNoise as _RNNOISE_CLASS  # type: ignore[import-not-found]

    _BACKEND_READY = True
    _BACKEND_NAME = "rnnoise"
except Exception as exc_rnnoise:  # noqa: BLE001
    try:
        from pyrnnoise import RNNoise as _RNNOISE_CLASS  # type: ignore[import-not-found]

        _BACKEND_READY = True
        _BACKEND_NAME = "pyrnnoise"
    except Exception as exc_pyrnnoise:  # noqa: BLE001
        _BACKEND_ERROR = f"не удалось импортировать rnnoise ({exc_rnnoise}); не удалось импортировать pyrnnoise ({exc_pyrnnoise})"


def noise_suppression_is_available() -> bool:
    return _BACKEND_READY


def noise_suppression_backend_status_text() -> str:
    return "Доступно" if _BACKEND_READY else "Недоступно"


def noise_suppression_backend_details() -> str:
    if _BACKEND_READY:
        return f"Бэкенд RNNoise: {_BACKEND_NAME}"
    return f"Бэкенд RNNoise недоступен: {_BACKEND_ERROR or 'биндинг не установлен'}"


def _to_float32(audio_block: np.ndarray) -> np.ndarray:
    if audio_block.dtype == np.float32:
        return audio_block.astype(np.float32, copy=True)
    if audio_block.dtype == np.int16:
        return audio_block.astype(np.float32) / 32768.0
    return audio_block.astype(np.float32)


def _from_float32(float_block: np.ndarray, dtype: np.dtype) -> np.ndarray:
    clipped = np.clip(float_block, -1.0, 1.0)
    if dtype == np.int16:
        return (clipped * 32767.0).astype(np.int16)
    return clipped.astype(dtype)


def apply_input_gain(audio_block: np.ndarray, gain: float) -> np.ndarray:
    """Apply mic gain safely with clipping and preserve input dtype."""

    if gain == 1.0:
        return audio_block
    original_dtype = audio_block.dtype
    float_block = _to_float32(audio_block)
    amplified = float_block * float(gain)
    return _from_float32(amplified, original_dtype)


def rms_level(audio_block: np.ndarray) -> float:
    """Return normalized RMS level in 0..1 range."""

    if audio_block.size == 0:
        return 0.0
    float_block = _to_float32(audio_block)
    rms = np.sqrt(np.mean(float_block * float_block, dtype=np.float64))
    return float(np.clip(rms, 0.0, 1.0))


def apply_noise_gate(audio_block: np.ndarray, threshold: float, enabled: bool) -> np.ndarray:
    """Mute whole frame when normalized RMS level is below threshold (0..1)."""

    if not enabled:
        return audio_block
    if rms_level(audio_block) < float(threshold):
        return np.zeros_like(audio_block)
    return audio_block


class _NoiseSuppressor:
    """Stateful adapter around optional RNNoise backend."""

    def __init__(self) -> None:
        self._model = _RNNOISE_CLASS() if _BACKEND_READY and _RNNOISE_CLASS else None

    def process(self, audio_block: np.ndarray) -> np.ndarray:
        if self._model is None:
            return audio_block

        original_dtype = audio_block.dtype
        float_block = _to_float32(audio_block).reshape(-1)
        output = np.empty_like(float_block)

        # RNNoise bindings usually process fixed 480-sample chunks.
        for offset in range(0, float_block.size, RNNOISE_FRAME_SIZE):
            chunk = float_block[offset : offset + RNNOISE_FRAME_SIZE]
            if chunk.size < RNNOISE_FRAME_SIZE:
                padded = np.zeros(RNNOISE_FRAME_SIZE, dtype=np.float32)
                padded[: chunk.size] = chunk
                denoised = self._model.process_frame(padded)
                output[offset : offset + chunk.size] = np.asarray(denoised, dtype=np.float32)[: chunk.size]
            else:
                denoised = self._model.process_frame(chunk)
                output[offset : offset + RNNOISE_FRAME_SIZE] = np.asarray(denoised, dtype=np.float32)[
                    :RNNOISE_FRAME_SIZE
                ]

        return _from_float32(output, original_dtype)


_SUPPRESSOR = _NoiseSuppressor()


def process_noise_suppression(
    audio_block: np.ndarray,
    enabled: bool,
    on_log: Callable[[str], None] | None = None,
) -> np.ndarray:
    """Process audio via optional RNNoise backend when enabled.

    If backend is unavailable the input is returned untouched and warning is logged once.
    """

    global _BACKEND_WARNED
    if not enabled:
        return audio_block

    if not _BACKEND_READY:
        if not _BACKEND_WARNED and on_log:
            _BACKEND_WARNED = True
            on_log(noise_suppression_backend_details())
        return audio_block

    try:
        return _SUPPRESSOR.process(audio_block)
    except Exception as exc:  # noqa: BLE001
        if not _BACKEND_WARNED and on_log:
            _BACKEND_WARNED = True
            on_log(f"сбой бэкенда шумоподавления, обработка отключена: {exc}")
        return audio_block
