"""Simple UDP JSON signaling transport."""

from __future__ import annotations

import json
import socket
import threading
import time
from typing import Callable

from app.core.config import RECEIVE_HOST, SIGNALING_BUFFER_SIZE, SIGNALING_POLL_TIMEOUT_SEC


def build_message(msg_type: str, from_ip: str, signaling_port: int, audio_port: int) -> dict:
    return {
        "type": msg_type,
        "from_ip": from_ip,
        "signaling_port": signaling_port,
        "audio_port": audio_port,
        "timestamp": time.time(),
    }


def detect_local_ip() -> str:
    """Best-effort local LAN IP detection."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        return str(probe.getsockname()[0])
    except OSError:
        return "0.0.0.0"
    finally:
        probe.close()


class SignalingClient:
    """Background UDP listener + sender for signaling messages."""

    def __init__(
        self,
        local_port: int,
        on_message: Callable[[dict, tuple[str, int]], None],
        on_log: Callable[[str], None],
    ) -> None:
        self.local_port = local_port
        self.on_message = on_message
        self.on_log = on_log
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind((RECEIVE_HOST, self.local_port))
            sock.settimeout(SIGNALING_POLL_TIMEOUT_SEC)
            self._sock = sock
        except OSError as exc:
            raise RuntimeError(f"listener start error on UDP {self.local_port}: {exc}") from exc

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
        if self._thread:
            self._thread.join(timeout=1.0)
        self._thread = None
        self._sock = None

    def send(self, host: str, port: int, payload: dict) -> None:
        if not self._sock:
            raise RuntimeError("signaling socket is not initialized")
        try:
            raw = json.dumps(payload).encode("utf-8")
            self._sock.sendto(raw, (host, port))
        except OSError as exc:
            raise RuntimeError(f"failed to send signaling message to {host}:{port}: {exc}") from exc

    def _loop(self) -> None:
        assert self._sock is not None
        sock = self._sock
        while not self._stop_event.is_set():
            try:
                data, addr = sock.recvfrom(SIGNALING_BUFFER_SIZE)
            except socket.timeout:
                continue
            except OSError as exc:
                if not self._stop_event.is_set():
                    self.on_log(f"listener receive error: {exc}")
                break

            try:
                message = json.loads(data.decode("utf-8"))
                if not isinstance(message, dict):
                    self.on_log("invalid signaling payload ignored")
                    continue
                self.on_message(message, addr)
            except Exception:
                self.on_log("invalid signaling payload ignored")
