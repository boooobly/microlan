"""UDP socket creation helpers."""

from __future__ import annotations

import socket


def create_udp_sender_socket() -> socket.socket:
    """Create UDP socket for sending audio blocks."""
    try:
        return socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    except OSError as exc:
        raise RuntimeError(f"Failed to create UDP sender socket: {exc}") from exc


def create_udp_receiver_socket(host: str, port: int) -> socket.socket:
    """Create and bind UDP socket for receiving audio blocks."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((host, port))
        return sock
    except OSError as exc:
        raise RuntimeError(f"Failed to open UDP receiver socket on {host}:{port}: {exc}") from exc
