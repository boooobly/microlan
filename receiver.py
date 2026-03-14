"""Receive UDP audio blocks and play them on output device."""

from __future__ import annotations

import argparse
import queue
import sys
import threading
import time

import numpy as np
import sounddevice as sd

from audio import block_size_frames, bytes_per_block, bytes_to_int16_mono, validate_audio_format
from config import BLOCK_DURATION_MS, CHANNELS, DTYPE, RECEIVE_HOST, SAMPLE_RATE
from network import create_udp_receiver_socket


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="UDP voice receiver (one-way MVP)")
    parser.add_argument("--port", required=True, type=int, help="UDP port to listen on")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        validate_audio_format(SAMPLE_RATE, CHANNELS, DTYPE)
        frames_per_block = block_size_frames(SAMPLE_RATE, BLOCK_DURATION_MS)
        block_bytes = bytes_per_block(frames_per_block, CHANNELS, DTYPE)
    except ValueError as exc:
        print(f"Format configuration error: {exc}", file=sys.stderr)
        return 1

    try:
        sock = create_udp_receiver_socket(RECEIVE_HOST, args.port)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1

    audio_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=100)
    stop_event = threading.Event()

    def receive_loop() -> None:
        while not stop_event.is_set():
            try:
                payload, _addr = sock.recvfrom(block_bytes)
                if len(payload) != block_bytes:
                    continue
                block = bytes_to_int16_mono(payload)
                if audio_queue.full():
                    try:
                        audio_queue.get_nowait()
                    except queue.Empty:
                        pass
                audio_queue.put_nowait(block)
            except OSError:
                break
            except Exception as exc:  # noqa: BLE001
                print(f"Receiver network loop error: {exc}", file=sys.stderr)

    def playback_callback(outdata, frames, _time_info, status) -> None:
        try:
            if status:
                print(f"Output stream warning: {status}", file=sys.stderr)

            if frames != frames_per_block:
                print(
                    f"Unexpected frame count: {frames} (expected {frames_per_block})",
                    file=sys.stderr,
                )

            try:
                block = audio_queue.get_nowait()
            except queue.Empty:
                outdata.fill(0)
                return

            if block.shape[0] != frames_per_block:
                outdata.fill(0)
                return

            outdata[:, 0] = block
        except Exception as exc:  # noqa: BLE001
            print(f"Audio callback error: {exc}", file=sys.stderr)
            raise sd.CallbackAbort from exc

    receiver_thread = threading.Thread(target=receive_loop, daemon=True)
    receiver_thread.start()

    print(f"Listening on {RECEIVE_HOST}:{args.port}. Press Ctrl+C to stop.")

    try:
        with sd.OutputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            blocksize=frames_per_block,
            callback=playback_callback,
        ):
            while True:
                time.sleep(1)
    except sd.PortAudioError as exc:
        print(f"Output device/stream error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Receiver stopped by user.")
        return 0
    finally:
        stop_event.set()
        sock.close()
        receiver_thread.join(timeout=1.0)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
