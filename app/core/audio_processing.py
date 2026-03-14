"""Audio DSP helpers for mic pipeline."""

from __future__ import annotations

import numpy as np


def _to_float32(audio_block: np.ndarray) -> np.ndarray:
    if audio_block.dtype == np.float32:
        return audio_block.copy()
    if audio_block.dtype == np.int16:
        return audio_block.astype(np.float32) / 32768.0
    return audio_block.astype(np.float32)


def _from_float32(float_block: np.ndarray, dtype: np.dtype) -> np.ndarray:
    clipped = np.clip(float_block, -1.0, 1.0)
    if dtype == np.int16:
        return (clipped * 32767.0).astype(np.int16)
    return clipped.astype(dtype)


def apply_input_gain(audio_block: np.ndarray, gain: float) -> np.ndarray:
    """Apply mic gain safely with clipping.

    Works with int16 or float32 arrays and returns same dtype as input.
    """

    if gain == 1.0:
        return audio_block
    original_dtype = audio_block.dtype
    float_block = _to_float32(audio_block)
    amplified = float_block * float(gain)
    return _from_float32(amplified, original_dtype)


def rms_level(audio_block: np.ndarray) -> float:
    """Return RMS level in normalized scale 0..1 (approximately)."""

    if audio_block.size == 0:
        return 0.0
    float_block = _to_float32(audio_block)
    rms = np.sqrt(np.mean(float_block * float_block, dtype=np.float64))
    return float(np.clip(rms, 0.0, 1.0))


def apply_noise_gate(audio_block: np.ndarray, threshold: float, enabled: bool) -> np.ndarray:
    """Simple gate: mute whole block when RMS < threshold.

    threshold uses normalized 0..1 RMS units.
    """

    if not enabled:
        return audio_block
    level = rms_level(audio_block)
    if level < float(threshold):
        return np.zeros_like(audio_block)
    return audio_block


def process_noise_suppression(audio_block: np.ndarray, enabled: bool) -> np.ndarray:
    """Placeholder hook for future denoise implementation (RNNoise/etc.)."""

    if not enabled:
        return audio_block
    return audio_block
