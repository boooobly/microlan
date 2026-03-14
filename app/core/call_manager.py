"""Coordinates call state machine, signaling, and audio lifecycle."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable

from app.core.audio_engine import AudioEngine
from app.core.audio_processing import (
    noise_suppression_backend_details,
    noise_suppression_backend_status_text,
    noise_suppression_is_available,
)
from app.core.config import CALL_TIMEOUT_SECONDS, DEFAULT_AUDIO_PORT, DEFAULT_SIGNALING_PORT
from app.core.devices import get_device_name, resolve_device_index_or_default
from app.core.signaling import SignalingClient, build_message, detect_local_ip
from app.core.states import CallState


@dataclass
class Peer:
    ip: str
    signaling_port: int
    audio_port: int


class CallManager:
    def __init__(
        self,
        on_state_changed: Callable[[CallState, str], None],
        on_log: Callable[[str], None],
        on_input_level: Callable[[float], None] | None = None,
    ) -> None:
        self.on_state_changed = on_state_changed
        self.on_log = on_log

        self.state = CallState.IDLE
        self.local_signaling_port = DEFAULT_SIGNALING_PORT
        self.local_audio_port = DEFAULT_AUDIO_PORT

        self.signaling: SignalingClient | None = None
        self.audio_engine = AudioEngine(on_log=on_log, on_input_level=on_input_level)

        self.current_peer: Peer | None = None
        self.pending_peer: Peer | None = None
        self._call_timer: threading.Timer | None = None

    def restart_listener(self, signaling_port: int, audio_port: int) -> None:
        self.local_signaling_port = signaling_port
        self.local_audio_port = audio_port
        if self.signaling:
            self.signaling.stop()

        self.signaling = SignalingClient(
            local_port=signaling_port,
            on_message=self._on_signaling_message,
            on_log=self.on_log,
        )
        self.signaling.start()
        self.on_log(f"signaling listening on UDP {signaling_port}")
        self._set_state(CallState.IDLE, "Ready")

    def shutdown(self) -> None:
        self._cancel_call_timeout()
        self.audio_engine.stop()
        if self.signaling:
            self.signaling.stop()

    def update_audio_settings(
        self,
        selected_input_device: int | None,
        selected_output_device: int | None,
        mute_enabled: bool,
        mic_gain: float,
        noise_gate_enabled: bool,
        noise_gate_threshold: float,
        noise_suppression_enabled: bool,
    ) -> None:
        input_device = resolve_device_index_or_default(
            selected_input_device,
            direction="input",
            on_log=self.on_log,
        )
        output_device = resolve_device_index_or_default(
            selected_output_device,
            direction="output",
            on_log=self.on_log,
        )

        self.audio_engine.update_settings(
            selected_input_device=input_device,
            selected_output_device=output_device,
            mute_enabled=mute_enabled,
            mic_gain=mic_gain,
            noise_gate_enabled=noise_gate_enabled,
            noise_gate_threshold=noise_gate_threshold,
            noise_suppression_enabled=noise_suppression_enabled,
        )

    def noise_suppression_status(self) -> tuple[str, str, bool]:
        return (
            noise_suppression_backend_status_text(),
            noise_suppression_backend_details(),
            noise_suppression_is_available(),
        )

    def call(self, ip: str, signaling_port: int, audio_port: int) -> None:
        if self.state not in {CallState.IDLE, CallState.ENDED}:
            self.on_log("outgoing CALL ignored: invalid state")
            return
        if not self.signaling:
            self._set_state(CallState.ERROR, "Signaling listener is not active")
            return

        self.current_peer = Peer(ip=ip, signaling_port=signaling_port, audio_port=audio_port)
        in_name = get_device_name(self.audio_engine.settings.selected_input_device)
        out_name = get_device_name(self.audio_engine.settings.selected_output_device)
        self.on_log(f"audio devices for call: input={in_name}; output={out_name}")

        self._send(self.current_peer, "CALL")
        self._set_state(CallState.CALLING, f"Calling {ip}:{signaling_port}")
        self._start_call_timeout()

    def accept(self) -> None:
        if self.state != CallState.RINGING or not self.pending_peer:
            self.on_log("ACCEPT ignored: no ringing peer")
            return
        self.current_peer = self.pending_peer
        self.pending_peer = None
        self._send(self.current_peer, "ACCEPT")
        self._start_audio(self.current_peer)

    def decline(self) -> None:
        if self.state != CallState.RINGING or not self.pending_peer:
            self.on_log("DECLINE ignored: no ringing peer")
            return
        self._send(self.pending_peer, "DECLINE")
        self.pending_peer = None
        self._set_state(CallState.ENDED, "Incoming call declined")

    def hangup(self) -> None:
        if self.state not in {CallState.CALLING, CallState.RINGING, CallState.IN_CALL}:
            self.on_log("HANGUP ignored: no active call")
            return
        if self.current_peer:
            self._send(self.current_peer, "HANGUP")
        self._end_call("Call ended")

    def get_local_ip(self) -> str:
        return detect_local_ip()

    def _end_call(self, reason: str) -> None:
        self._cancel_call_timeout()
        self.audio_engine.stop()
        self.current_peer = None
        self.pending_peer = None
        self._set_state(CallState.ENDED, reason)

    def _start_audio(self, peer: Peer) -> None:
        self._cancel_call_timeout()
        try:
            self.audio_engine.start(
                remote_host=peer.ip,
                remote_audio_port=peer.audio_port,
                local_audio_port=self.local_audio_port,
            )
            self._set_state(CallState.IN_CALL, f"In call with {peer.ip}")
        except RuntimeError as exc:
            self._set_state(CallState.ERROR, str(exc))

    def _on_signaling_message(self, message: dict, addr: tuple[str, int]) -> None:
        try:
            msg_type = str(message["type"]).upper()
            peer = Peer(
                ip=str(message.get("from_ip") or addr[0]),
                signaling_port=int(message["signaling_port"]),
                audio_port=int(message["audio_port"]),
            )
        except (KeyError, ValueError, TypeError) as exc:
            self.on_log(f"invalid signaling payload ignored in manager: {exc}")
            return

        if msg_type == "CALL":
            if self.state in {CallState.CALLING, CallState.RINGING, CallState.IN_CALL}:
                self.on_log(f"incoming CALL from {peer.ip} -> BUSY")
                self._send(peer, "BUSY")
                return
            self.pending_peer = peer
            self._set_state(CallState.RINGING, f"Incoming call from {peer.ip}")
            return

        if msg_type == "ACCEPT":
            if self.state == CallState.CALLING and self.current_peer:
                self._start_audio(self.current_peer)
            return

        if msg_type == "DECLINE":
            if self.state == CallState.CALLING:
                self._end_call("Call declined by peer")
            return

        if msg_type == "HANGUP":
            if self.state in {CallState.CALLING, CallState.RINGING, CallState.IN_CALL}:
                self._end_call("Peer ended call")
            return

        if msg_type == "BUSY" and self.state == CallState.CALLING:
            self._end_call("Peer is busy")

    def _send(self, peer: Peer, msg_type: str) -> None:
        if not self.signaling:
            self.on_log(f"cannot send {msg_type}: signaling unavailable")
            return
        payload = build_message(
            msg_type=msg_type,
            from_ip=self.get_local_ip(),
            signaling_port=self.local_signaling_port,
            audio_port=self.local_audio_port,
        )
        try:
            self.signaling.send(peer.ip, peer.signaling_port, payload)
        except RuntimeError as exc:
            self.on_log(str(exc))
            self._set_state(CallState.ERROR, str(exc))

    def _start_call_timeout(self) -> None:
        self._cancel_call_timeout()
        self._call_timer = threading.Timer(CALL_TIMEOUT_SECONDS, self._on_call_timeout)
        self._call_timer.daemon = True
        self._call_timer.start()

    def _cancel_call_timeout(self) -> None:
        if self._call_timer:
            self._call_timer.cancel()
        self._call_timer = None

    def _on_call_timeout(self) -> None:
        if self.state == CallState.CALLING:
            self._end_call("Call timeout (25s)")

    def _set_state(self, state: CallState, text: str) -> None:
        self.state = state
        self.on_state_changed(state, text)
        self.on_log(f"state -> {state.value}: {text}")
