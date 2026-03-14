"""Capture microphone input and send audio blocks over UDP."""

from __future__ import annotations

import argparse
import sys
import time

import sounddevice as sd

from audio import block_size_frames, validate_audio_format
from config import BLOCK_DURATION_MS, CHANNELS, DTYPE, SAMPLE_RATE
from network import create_udp_sender_socket


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="UDP voice sender (one-way MVP)")
    parser.add_argument("--host", required=True, help="Receiver IP address")
    parser.add_argument("--port", required=True, type=int, help="Receiver UDP port")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        validate_audio_format(SAMPLE_RATE, CHANNELS, DTYPE)
        frames_per_block = block_size_frames(SAMPLE_RATE, BLOCK_DURATION_MS)
    except ValueError as exc:
        print(f"Format configuration error: {exc}", file=sys.stderr)
        return 1

    try:
        sock = create_udp_sender_socket()
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1

    def audio_callback(indata, frames, _time_info, status) -> None:
        try:
            if status:
                print(f"Input stream warning: {status}", file=sys.stderr)
            if frames != frames_per_block:
                print(
                    f"Unexpected frame count: {frames} (expected {frames_per_block})",
                    file=sys.stderr,
                )
            sock.sendto(indata.tobytes(), (args.host, args.port))
        except Exception as exc:  # noqa: BLE001
            print(f"Audio callback error: {exc}", file=sys.stderr)
            raise sd.CallbackAbort from exc

    print(f"Sending audio to {args.host}:{args.port}. Press Ctrl+C to stop.")

    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            blocksize=frames_per_block,
            callback=audio_callback,
        ):
            while True:
                time.sleep(1)
    except sd.PortAudioError as exc:
        print(f"Input device/stream error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Sender stopped by user.")
        return 0
    finally:
        sock.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
