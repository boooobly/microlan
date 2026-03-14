"""Bidirectional raw PCM audio transport over UDP."""

from __future__ import annotations

import queue
import socket
import threading
from typing import Callable

import sounddevice as sd

from app.core.config import AUDIO_QUEUE_MAX_BLOCKS, BLOCKSIZE, CHANNELS, DTYPE, RECEIVE_HOST, SAMPLE_RATE


class AudioEngine:
    def __init__(self, on_error: Callable[[str], None]) -> None:
        self.on_error = on_error
        self._send_sock: socket.socket | None = None
        self._recv_sock: socket.socket | None = None
        self._recv_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._incoming_blocks: queue.Queue[bytes] = queue.Queue(maxsize=AUDIO_QUEUE_MAX_BLOCKS)
        self._input_stream: sd.RawInputStream | None = None
        self._output_stream: sd.RawOutputStream | None = None
        self.remote_host: str | None = None
        self.remote_audio_port: int | None = None
        self.local_audio_port: int | None = None

    def start(self, remote_host: str, remote_audio_port: int, local_audio_port: int) -> None:
        if self.is_running:
            return

        self.remote_host = remote_host
        self.remote_audio_port = remote_audio_port
        self.local_audio_port = local_audio_port

        try:
            self._send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._recv_sock.bind((RECEIVE_HOST, local_audio_port))
        except OSError as exc:
            self.stop()
            raise RuntimeError(f"Failed to open audio UDP sockets: {exc}") from exc

        self._stop_event.clear()
        self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._recv_thread.start()

        try:
            self._input_stream = sd.RawInputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype=DTYPE,
                blocksize=BLOCKSIZE,
                callback=self._input_callback,
            )
            self._output_stream = sd.RawOutputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype=DTYPE,
                blocksize=BLOCKSIZE,
                callback=self._output_callback,
            )
            self._input_stream.start()
            self._output_stream.start()
        except sd.PortAudioError as exc:
            self.stop()
            raise RuntimeError(f"Audio device/stream error: {exc}") from exc
        except Exception as exc:
            self.stop()
            raise RuntimeError(f"Failed to start audio engine: {exc}") from exc

    def stop(self) -> None:
        self._stop_event.set()

        if self._input_stream:
            try:
                self._input_stream.stop()
                self._input_stream.close()
            except Exception:
                pass
        if self._output_stream:
            try:
                self._output_stream.stop()
                self._output_stream.close()
            except Exception:
                pass

        self._input_stream = None
        self._output_stream = None

        if self._send_sock:
            try:
                self._send_sock.close()
            except OSError:
                pass
        if self._recv_sock:
            try:
                self._recv_sock.close()
            except OSError:
                pass

        self._send_sock = None
        self._recv_sock = None

        if self._recv_thread:
            self._recv_thread.join(timeout=1.0)
        self._recv_thread = None

        while not self._incoming_blocks.empty():
            try:
                self._incoming_blocks.get_nowait()
            except queue.Empty:
                break

    @property
    def is_running(self) -> bool:
        return self._input_stream is not None and self._output_stream is not None

    def _recv_loop(self) -> None:
        assert self._recv_sock is not None
        recv_sock = self._recv_sock
        expected_size = BLOCKSIZE * CHANNELS * 2
        while not self._stop_event.is_set():
            try:
                payload, _addr = recv_sock.recvfrom(expected_size)
                if len(payload) != expected_size:
                    continue
                if self._incoming_blocks.full():
                    try:
                        self._incoming_blocks.get_nowait()
                    except queue.Empty:
                        pass
                self._incoming_blocks.put_nowait(payload)
            except OSError:
                break
            except Exception as exc:
                self.on_error(f"Audio receive error: {exc}")

    def _input_callback(self, indata: bytes, frames: int, _time_info, status) -> None:
        try:
            if status:
                self.on_error(f"Input stream warning: {status}")
            if frames != BLOCKSIZE:
                return
            if not self._send_sock or not self.remote_host or not self.remote_audio_port:
                return
            self._send_sock.sendto(indata, (self.remote_host, self.remote_audio_port))
        except Exception as exc:  # noqa: BLE001
            self.on_error(f"Audio input callback error: {exc}")
            raise sd.CallbackAbort from exc

    def _output_callback(self, outdata: bytearray, frames: int, _time_info, status) -> None:
        try:
            if status:
                self.on_error(f"Output stream warning: {status}")
            if frames != BLOCKSIZE:
                outdata[:] = b"\x00" * len(outdata)
                return
            try:
                block = self._incoming_blocks.get_nowait()
            except queue.Empty:
                outdata[:] = b"\x00" * len(outdata)
                return
            outdata[:] = block
        except Exception as exc:  # noqa: BLE001
            self.on_error(f"Audio output callback error: {exc}")
            raise sd.CallbackAbort from exc
