"""Generic helpers."""

from __future__ import annotations

from datetime import datetime


def timestamp_now() -> float:
    return datetime.now().timestamp()


def format_log_line(message: str) -> str:
    stamp = datetime.now().strftime("%H:%M:%S")
    return f"[{stamp}] {message}"
