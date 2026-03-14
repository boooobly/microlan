"""Вспомогательные функции для работы с аудиоблоками."""

from __future__ import annotations

import numpy as np


def calc_blocksize(sample_rate: int, block_duration_ms: int) -> int:
    """Рассчитать размер блока в сэмплах."""
    return int(sample_rate * block_duration_ms / 1000)


def validate_dtype(dtype: str) -> None:
    """Проверить, что используется поддерживаемый формат int16."""
    if np.dtype(dtype) != np.int16:
        raise ValueError(f"Unsupported dtype '{dtype}'. Expected 'int16'.")


def bytes_per_block(blocksize: int, channels: int, dtype: str) -> int:
    """Вернуть ожидаемый размер UDP-пакета (аудиоблока) в байтах."""
    return blocksize * channels * np.dtype(dtype).itemsize


def is_valid_block_length(block: bytes, expected_size: int) -> bool:
    """Проверить, что длина блока совпадает с ожидаемой."""
    return len(block) == expected_size
