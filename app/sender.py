"""CLI: захват с микрофона и отправка блоков по UDP."""

from __future__ import annotations

import argparse
import sys
import time

import sounddevice as sd

from app.audio import calc_blocksize, validate_dtype
from app.config import BLOCK_DURATION_MS, BLOCKSIZE, CHANNELS, DEFAULT_PORT, DTYPE, SAMPLE_RATE
from app.network import create_udp_sender_socket


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="One-way UDP voice sender")
    parser.add_argument("--host", required=True, help="IP address of receiver (ПК2)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Receiver UDP port (default: {DEFAULT_PORT})")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        validate_dtype(DTYPE)
        blocksize = calc_blocksize(SAMPLE_RATE, BLOCK_DURATION_MS)
        if blocksize != BLOCKSIZE:
            raise ValueError("Configured BLOCKSIZE does not match calculated blocksize")
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    try:
        sock = create_udp_sender_socket()
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1

    print(f"Sending to {args.host}:{args.port}")
    print(f"Audio: sample_rate={SAMPLE_RATE}, blocksize={blocksize}, channels={CHANNELS}, dtype={DTYPE}")
    print("Press Ctrl+C to stop.")

    def callback(indata: bytes, frames: int, _time_info, status) -> None:
        try:
            if status:
                print(f"Input stream warning: {status}", file=sys.stderr)
            if frames != blocksize:
                print(f"Unexpected frames count: {frames}, expected: {blocksize}", file=sys.stderr)
            sock.sendto(indata, (args.host, args.port))
        except Exception as exc:  # noqa: BLE001
            print(f"Audio callback error: {exc}", file=sys.stderr)
            raise sd.CallbackAbort from exc

    try:
        with sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            blocksize=blocksize,
            callback=callback,
        ):
            while True:
                time.sleep(1)
    except sd.PortAudioError as exc:
        print(f"Input device/stream error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Sender stopped.")
        return 0
    finally:
        sock.close()


if __name__ == "__main__":
    raise SystemExit(main())
