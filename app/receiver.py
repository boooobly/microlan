"""CLI: прием аудио по UDP и воспроизведение на устройстве вывода."""

from __future__ import annotations

import argparse
import queue
import sys
import threading
import time

import sounddevice as sd

from app.audio import bytes_per_block, calc_blocksize, is_valid_block_length, validate_dtype
from app.config import (
    BLOCK_DURATION_MS,
    BLOCKSIZE,
    CHANNELS,
    DEFAULT_PORT,
    DTYPE,
    RECEIVER_HOST,
    SAMPLE_RATE,
)
from app.network import create_udp_receiver_socket


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="One-way UDP voice receiver")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"UDP port to listen on (default: {DEFAULT_PORT})")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        validate_dtype(DTYPE)
        blocksize = calc_blocksize(SAMPLE_RATE, BLOCK_DURATION_MS)
        if blocksize != BLOCKSIZE:
            raise ValueError("Configured BLOCKSIZE does not match calculated blocksize")
        packet_size = bytes_per_block(blocksize, CHANNELS, DTYPE)
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    try:
        sock = create_udp_receiver_socket(RECEIVER_HOST, args.port)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1

    blocks: queue.Queue[bytes] = queue.Queue(maxsize=100)
    stop_event = threading.Event()

    print(f"Listening on {RECEIVER_HOST}:{args.port}")
    print(f"Audio: sample_rate={SAMPLE_RATE}, blocksize={blocksize}, channels={CHANNELS}, dtype={DTYPE}")
    print("Press Ctrl+C to stop.")

    def recv_loop() -> None:
        while not stop_event.is_set():
            try:
                payload, _addr = sock.recvfrom(packet_size)
                if not is_valid_block_length(payload, packet_size):
                    continue
                if blocks.full():
                    try:
                        blocks.get_nowait()
                    except queue.Empty:
                        pass
                blocks.put_nowait(payload)
            except OSError:
                break
            except Exception as exc:  # noqa: BLE001
                print(f"Receiver socket loop error: {exc}", file=sys.stderr)

    def callback(outdata: bytearray, frames: int, _time_info, status) -> None:
        try:
            if status:
                print(f"Output stream warning: {status}", file=sys.stderr)
            if frames != blocksize:
                print(f"Unexpected frames count: {frames}, expected: {blocksize}", file=sys.stderr)

            try:
                block = blocks.get_nowait()
                outdata[:] = block
            except queue.Empty:
                outdata[:] = b"\x00" * len(outdata)
        except Exception as exc:  # noqa: BLE001
            print(f"Audio callback error: {exc}", file=sys.stderr)
            raise sd.CallbackAbort from exc

    thread = threading.Thread(target=recv_loop, daemon=True)
    thread.start()

    try:
        with sd.RawOutputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            blocksize=blocksize,
            callback=callback,
        ):
            while True:
                time.sleep(1)
    except sd.PortAudioError as exc:
        print(f"Output device/stream error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Receiver stopped.")
        return 0
    finally:
        stop_event.set()
        sock.close()
        thread.join(timeout=1.0)


if __name__ == "__main__":
    raise SystemExit(main())
