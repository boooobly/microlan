"""Coordinates signaling, state transitions, and audio engine lifecycle."""

from __future__ import annotations

import socket
from dataclasses import dataclass
from typing import Callable

from app.core.audio_engine import AudioEngine
from app.core.config import DEFAULT_AUDIO_PORT, DEFAULT_SIGNALING_PORT
from app.core.signaling import SignalingClient, build_message
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
    ) -> None:
        self.on_state_changed = on_state_changed
        self.on_log = on_log

        self.state = CallState.IDLE
        self.local_signaling_port = DEFAULT_SIGNALING_PORT
        self.local_audio_port = DEFAULT_AUDIO_PORT

        self.signaling: SignalingClient | None = None
        self.audio_engine = AudioEngine(on_error=self._handle_audio_error)

        self.current_peer: Peer | None = None
        self.pending_peer: Peer | None = None

    def start_listener(self, signaling_port: int, audio_port: int) -> None:
        self.local_signaling_port = signaling_port
        self.local_audio_port = audio_port

        if self.signaling:
            self.signaling.stop()

        self.signaling = SignalingClient(local_port=signaling_port, on_message=self._on_signaling_message)
        self.signaling.start()
        self._set_state(CallState.IDLE, f"Ready. Listening signaling on UDP {signaling_port}")

    def shutdown(self) -> None:
        try:
            if self.state in {CallState.CALLING, CallState.RINGING, CallState.IN_CALL}:
                self.hangup()
        finally:
            self.audio_engine.stop()
            if self.signaling:
                self.signaling.stop()

    def call(self, ip: str, signaling_port: int, audio_port: int) -> None:
        if self.state not in {CallState.IDLE, CallState.ENDED}:
            self.on_log("Cannot start call: not in IDLE/ENDED")
            return
        if not self.signaling:
            self._set_state(CallState.ERROR, "Signaling not started")
            return

        self.current_peer = Peer(ip=ip, signaling_port=signaling_port, audio_port=audio_port)
        self._send_to_peer(self.current_peer, "CALL")
        self._set_state(CallState.CALLING, f"Calling {ip}:{signaling_port}...")

    def accept(self) -> None:
        if self.state != CallState.RINGING or not self.pending_peer:
            self.on_log("No incoming call to accept")
            return

        peer = self.pending_peer
        self.pending_peer = None
        self.current_peer = peer

        self._send_to_peer(peer, "ACCEPT")
        self._start_audio_for_peer(peer)

    def decline(self) -> None:
        if self.state != CallState.RINGING or not self.pending_peer:
            self.on_log("No incoming call to decline")
            return

        peer = self.pending_peer
        self.pending_peer = None
        self._send_to_peer(peer, "DECLINE")
        self._set_state(CallState.ENDED, "Call declined")

    def hangup(self) -> None:
        if self.state not in {CallState.CALLING, CallState.RINGING, CallState.IN_CALL}:
            self.on_log("Nothing to hang up")
            return

        if self.current_peer:
            self._send_to_peer(self.current_peer, "HANGUP")

        self.audio_engine.stop()
        self.current_peer = None
        self.pending_peer = None
        self._set_state(CallState.ENDED, "Call ended")

    def _start_audio_for_peer(self, peer: Peer) -> None:
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
        msg_type = str(message.get("type", "")).upper()
        from_ip = str(message.get("from_ip") or addr[0])
        signaling_port = int(message.get("signaling_port") or addr[1])
        audio_port = int(message.get("audio_port") or DEFAULT_AUDIO_PORT)
        peer = Peer(ip=from_ip, signaling_port=signaling_port, audio_port=audio_port)

        self.on_log(f"Signaling received: {msg_type} from {from_ip}:{signaling_port}")

        if msg_type == "CALL":
            if self.state in {CallState.CALLING, CallState.RINGING, CallState.IN_CALL}:
                self._send_to_peer(peer, "BUSY")
                return
            self.pending_peer = peer
            self._set_state(CallState.RINGING, f"Incoming call from {peer.ip}")
            return

        if msg_type == "ACCEPT":
            if self.state != CallState.CALLING or not self.current_peer:
                return
            self._start_audio_for_peer(self.current_peer)
            return

        if msg_type == "DECLINE":
            if self.state == CallState.CALLING:
                self.current_peer = None
                self._set_state(CallState.ENDED, "Call declined by peer")
            return

        if msg_type == "HANGUP":
            if self.state in {CallState.CALLING, CallState.RINGING, CallState.IN_CALL}:
                self.audio_engine.stop()
                self.current_peer = None
                self.pending_peer = None
                self._set_state(CallState.ENDED, "Peer ended the call")
            return

        if msg_type == "BUSY":
            if self.state == CallState.CALLING:
                self.current_peer = None
                self._set_state(CallState.ENDED, "Peer is busy")
            return

        if msg_type == "PING":
            return

    def _send_to_peer(self, peer: Peer, msg_type: str) -> None:
        if not self.signaling:
            self._set_state(CallState.ERROR, "Signaling not initialized")
            return

        from_ip = self._guess_local_ip(peer.ip)
        payload = build_message(
            msg_type=msg_type,
            from_ip=from_ip,
            signaling_port=self.local_signaling_port,
            audio_port=self.local_audio_port,
        )
        try:
            self.signaling.send(peer.ip, peer.signaling_port, payload)
            self.on_log(f"Signaling sent: {msg_type} -> {peer.ip}:{peer.signaling_port}")
        except RuntimeError as exc:
            self._set_state(CallState.ERROR, str(exc))

    def _guess_local_ip(self, peer_ip: str) -> str:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect((peer_ip, 9))
            return str(probe.getsockname()[0])
        except OSError:
            return "0.0.0.0"
        finally:
            probe.close()

    def _handle_audio_error(self, message: str) -> None:
        self.on_log(message)

    def _set_state(self, state: CallState, message: str) -> None:
        self.state = state
        self.on_state_changed(state, message)
        self.on_log(f"STATE -> {state.value}: {message}")
