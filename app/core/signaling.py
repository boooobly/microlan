"""UDP signaling transport with JSON payloads."""

from __future__ import annotations

import json
import socket
import threading
from typing import Callable

from app.core.config import RECEIVE_HOST, SIGNALING_BUFFER_SIZE, SIGNALING_POLL_TIMEOUT_SEC
from app.core.utils import timestamp_now

SIGNAL_TYPES = {"CALL", "ACCEPT", "DECLINE", "HANGUP", "BUSY"}


def build_message(msg_type: str, from_ip: str, signaling_port: int, audio_port: int) -> dict:
    return {
        "type": msg_type,
        "from_ip": from_ip,
        "signaling_port": signaling_port,
        "audio_port": audio_port,
        "timestamp": timestamp_now(),
    }


def detect_local_ip() -> str:
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        return str(probe.getsockname()[0])
    except OSError:
        return "0.0.0.0"
    finally:
        probe.close()


def validate_signaling_payload(payload: dict) -> tuple[bool, str]:
    try:
        msg_type = str(payload["type"]).upper()
        if msg_type not in SIGNAL_TYPES:
            return False, f"неизвестный тип: {msg_type}"
        int(payload["signaling_port"])
        int(payload["audio_port"])
        float(payload.get("timestamp", 0))
    except (KeyError, TypeError, ValueError) as exc:
        return False, str(exc)
    return True, ""


class SignalingClient:
    def __init__(
        self,
        local_port: int,
        on_message: Callable[[dict, tuple[str, int]], None],
        on_log: Callable[[str], None],
    ) -> None:
        self.local_port = local_port
        self.on_message = on_message
        self.on_log = on_log
        self._socket: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind((RECEIVE_HOST, self.local_port))
            sock.settimeout(SIGNALING_POLL_TIMEOUT_SEC)
        except OSError as exc:
            raise RuntimeError(f"не удалось запустить прослушивание signaling на UDP {self.local_port}: {exc}") from exc

        self._socket = sock
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._socket:
            try:
                self._socket.close()
            except OSError:
                pass
        if self._thread:
            self._thread.join(timeout=1.0)
        self._thread = None
        self._socket = None

    def send(self, host: str, port: int, payload: dict) -> None:
        if not self._socket:
            raise RuntimeError("signaling не запущен")
        raw = json.dumps(payload).encode("utf-8")
        try:
            self._socket.sendto(raw, (host, int(port)))
        except OSError as exc:
            raise RuntimeError(f"не удалось отправить signaling на {host}:{port}: {exc}") from exc

    def _loop(self) -> None:
        assert self._socket is not None
        sock = self._socket
        while not self._stop_event.is_set():
            try:
                data, addr = sock.recvfrom(SIGNALING_BUFFER_SIZE)
            except socket.timeout:
                continue
            except OSError:
                break

            try:
                payload = json.loads(data.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self.on_log("некорректный signaling-пакет проигнорирован: ошибка декодирования")
                continue

            if not isinstance(payload, dict):
                self.on_log("некорректный signaling-пакет проигнорирован: ожидался объект")
                continue

            is_valid, reason = validate_signaling_payload(payload)
            if not is_valid:
                self.on_log(f"некорректный signaling-пакет проигнорирован: {reason}")
                continue

            self.on_message(payload, addr)
