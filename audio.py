"""Audio helpers for frame sizing, conversion, and format validation."""

from __future__ import annotations

import numpy as np


def block_size_frames(sample_rate: int, block_duration_ms: int) -> int:
    """Return number of frames in one audio block."""
    return int(sample_rate * block_duration_ms / 1000)


def bytes_per_block(frames: int, channels: int, dtype: str) -> int:
    """Return expected byte-size for one audio block."""
    sample_bytes = np.dtype(dtype).itemsize
    return frames * channels * sample_bytes


def validate_audio_format(sample_rate: int, channels: int, dtype: str) -> None:
    """Validate supported MVP format and raise ValueError for mismatch."""
    if sample_rate != 48_000:
        raise ValueError(f"Unsupported sample_rate={sample_rate}. Expected 48000.")
    if channels != 1:
        raise ValueError(f"Unsupported channels={channels}. Expected 1.")
    if np.dtype(dtype) != np.int16:
        raise ValueError(f"Unsupported dtype={dtype}. Expected int16.")


def bytes_to_int16_mono(data: bytes) -> np.ndarray:
    """Convert raw bytes to mono int16 NumPy array."""
    return np.frombuffer(data, dtype=np.int16)
