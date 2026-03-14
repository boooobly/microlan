"""Bi-directional raw PCM audio over UDP."""

from __future__ import annotations

import queue
import socket
import threading
import time
from dataclasses import dataclass
from typing import Callable

import numpy as np
import sounddevice as sd

from app.core.audio_processing import (
    apply_input_gain,
    apply_noise_gate,
    process_noise_suppression,
    rms_level,
)
from app.core.config import (
    AUDIO_QUEUE_MAX_FRAMES,
    CHANNELS,
    DTYPE,
    FRAMES_PER_BUFFER,
    INPUT_LEVEL_EMIT_INTERVAL_SEC,
    RECEIVE_HOST,
    SAMPLE_RATE,
)


@dataclass
class AudioSettings:
    mic_gain: float = 1.0
    noise_gate_enabled: bool = True
    noise_gate_threshold: float = 0.02
    noise_suppression_enabled: bool = False


class AudioEngine:
    def __init__(self, on_log: Callable[[str], None], on_input_level: Callable[[float], None] | None = None) -> None:
        self.on_log = on_log
        self.on_input_level = on_input_level
        self.settings = AudioSettings()

        self._udp_socket: socket.socket | None = None
        self._receiver_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._incoming = queue.Queue(maxsize=AUDIO_QUEUE_MAX_FRAMES)

        self._input_stream: sd.InputStream | None = None
        self._output_stream: sd.OutputStream | None = None

        self._remote_addr: tuple[str, int] | None = None
        self._last_level_emit = 0.0

    def update_settings(
        self,
        mic_gain: float,
        noise_gate_enabled: bool,
        noise_gate_threshold: float,
        noise_suppression_enabled: bool,
    ) -> None:
        self.settings = AudioSettings(
            mic_gain=float(mic_gain),
            noise_gate_enabled=bool(noise_gate_enabled),
            noise_gate_threshold=float(noise_gate_threshold),
            noise_suppression_enabled=bool(noise_suppression_enabled),
        )

    def start(self, remote_host: str, remote_audio_port: int, local_audio_port: int) -> None:
        self.stop()
        self._remote_addr = (remote_host, int(remote_audio_port))
        self._stop_event.clear()

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind((RECEIVE_HOST, int(local_audio_port)))
            sock.settimeout(0.2)
        except OSError as exc:
            raise RuntimeError(f"audio socket error on UDP {local_audio_port}: {exc}") from exc

        self._udp_socket = sock
        self._receiver_thread = threading.Thread(target=self._receiver_loop, daemon=True)
        self._receiver_thread.start()

        try:
            self._input_stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype=DTYPE,
                blocksize=FRAMES_PER_BUFFER,
                callback=self._input_callback,
            )
            self._output_stream = sd.OutputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype=DTYPE,
                blocksize=FRAMES_PER_BUFFER,
                callback=self._output_callback,
            )
            self._input_stream.start()
            self._output_stream.start()
        except Exception as exc:  # noqa: BLE001
            self.stop()
            raise RuntimeError(f"audio stream startup error: {exc}") from exc

        self.on_log(f"audio stream started: local UDP {local_audio_port} -> {remote_host}:{remote_audio_port}")

    def stop(self) -> None:
        self._stop_event.set()

        if self._input_stream:
            try:
                self._input_stream.stop()
                self._input_stream.close()
            except Exception:
                pass
            self._input_stream = None

        if self._output_stream:
            try:
                self._output_stream.stop()
                self._output_stream.close()
            except Exception:
                pass
            self._output_stream = None

        if self._udp_socket:
            try:
                self._udp_socket.close()
            except OSError:
                pass
            self._udp_socket = None

        if self._receiver_thread:
            self._receiver_thread.join(timeout=1.0)
            self._receiver_thread = None

        while not self._incoming.empty():
            try:
                self._incoming.get_nowait()
            except queue.Empty:
                break

    def _receiver_loop(self) -> None:
        sock = self._udp_socket
        if not sock:
            return
        while not self._stop_event.is_set():
            try:
                data, _addr = sock.recvfrom(FRAMES_PER_BUFFER * 2 * CHANNELS + 64)
            except socket.timeout:
                continue
            except OSError:
                break

            if not data:
                continue
            if self._incoming.full():
                try:
                    self._incoming.get_nowait()
                except queue.Empty:
                    pass
            try:
                self._incoming.put_nowait(data)
            except queue.Full:
                pass

    def _input_callback(self, indata, frames: int, _time_info, status) -> None:
        try:
            if status:
                self.on_log(f"input stream warning: {status}")
            if frames != FRAMES_PER_BUFFER or self._udp_socket is None or self._remote_addr is None:
                return

            block = np.copy(indata.reshape(-1))
            level = rms_level(block)
            now = time.monotonic()
            if self.on_input_level and now - self._last_level_emit >= INPUT_LEVEL_EMIT_INTERVAL_SEC:
                self._last_level_emit = now
                self.on_input_level(level)

            processed = apply_input_gain(block, self.settings.mic_gain)
            processed = apply_noise_gate(
                processed,
                threshold=self.settings.noise_gate_threshold,
                enabled=self.settings.noise_gate_enabled,
            )
            processed = process_noise_suppression(processed, enabled=self.settings.noise_suppression_enabled)
            self._udp_socket.sendto(processed.tobytes(), self._remote_addr)
        except Exception as exc:  # noqa: BLE001
            self.on_log(f"audio capture callback error: {exc}")
            raise sd.CallbackAbort from exc

    def _output_callback(self, outdata, frames: int, _time_info, status) -> None:
        try:
            if status:
                self.on_log(f"output stream warning: {status}")
            if frames != FRAMES_PER_BUFFER:
                outdata.fill(0)
                return
            try:
                raw = self._incoming.get_nowait()
            except queue.Empty:
                outdata.fill(0)
                return

            samples = np.frombuffer(raw, dtype=np.int16)
            if samples.size < FRAMES_PER_BUFFER:
                padded = np.zeros(FRAMES_PER_BUFFER, dtype=np.int16)
                padded[: samples.size] = samples
                samples = padded
            elif samples.size > FRAMES_PER_BUFFER:
                samples = samples[:FRAMES_PER_BUFFER]

            outdata[:, 0] = samples
        except Exception as exc:  # noqa: BLE001
            self.on_log(f"audio playback callback error: {exc}")
            raise sd.CallbackAbort from exc
