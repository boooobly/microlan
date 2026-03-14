"""Main Qt window for local LAN call control."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from app.core.call_manager import CallManager
from app.core.config import DEFAULT_AUDIO_PORT, DEFAULT_SIGNALING_PORT
from app.core.devices import (
    get_default_input_device,
    get_default_output_device,
    get_device_name,
    list_input_devices,
    list_output_devices,
)
from app.core.states import CallState


class UiEvents(QObject):
    state_changed = Signal(str, str)
    log = Signal(str)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Mini LAN Voice Call MVP")
        self.resize(760, 500)

        self.events = UiEvents()
        self.events.state_changed.connect(self._on_state_changed)
        self.events.log.connect(self._append_log)

        self.call_manager = CallManager(
            on_state_changed=lambda state, text: self.events.state_changed.emit(state.value, text),
            on_log=lambda text: self.events.log.emit(text),
        )

        self._build_ui()
        self._refresh_local_ip_label()
        self._log_device_diagnostics()
        self._apply_local_listener_settings()

    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        local_group = QGroupBox("Local settings")
        local_form = QFormLayout(local_group)
        self.local_signaling_port_input = QLineEdit(str(DEFAULT_SIGNALING_PORT))
        self.local_audio_port_input = QLineEdit(str(DEFAULT_AUDIO_PORT))
        self.local_ip_label = QLabel("Unknown")
        self.apply_listener_button = QPushButton("Apply / Restart listener")
        local_form.addRow("Local signaling port:", self.local_signaling_port_input)
        local_form.addRow("Local audio port:", self.local_audio_port_input)
        local_form.addRow("Local IP:", self.local_ip_label)
        local_form.addRow(self.apply_listener_button)
        layout.addWidget(local_group)

        peer_group = QGroupBox("Peer settings")
        peer_form = QFormLayout(peer_group)
        self.peer_ip_input = QLineEdit()
        self.peer_ip_input.setPlaceholderText("192.168.1.50")
        self.peer_signaling_port_input = QLineEdit(str(DEFAULT_SIGNALING_PORT))
        self.peer_audio_port_input = QLineEdit(str(DEFAULT_AUDIO_PORT))
        peer_form.addRow("Peer IP:", self.peer_ip_input)
        peer_form.addRow("Peer signaling port:", self.peer_signaling_port_input)
        peer_form.addRow("Peer audio port:", self.peer_audio_port_input)
        layout.addWidget(peer_group)

        buttons_row = QHBoxLayout()
        self.call_button = QPushButton("Call")
        self.hangup_button = QPushButton("Hang Up")
        self.accept_button = QPushButton("Accept")
        self.decline_button = QPushButton("Decline")
        buttons_row.addWidget(self.call_button)
        buttons_row.addWidget(self.hangup_button)
        buttons_row.addWidget(self.accept_button)
        buttons_row.addWidget(self.decline_button)
        layout.addLayout(buttons_row)

        self.log_area = QPlainTextEdit()
        self.log_area.setReadOnly(True)
        layout.addWidget(self.log_area)

        status = QStatusBar(self)
        self.setStatusBar(status)
        self.statusBar().showMessage("Initializing...")

        self.apply_listener_button.clicked.connect(self._on_apply_listener_clicked)
        self.call_button.clicked.connect(self._on_call_clicked)
        self.hangup_button.clicked.connect(self._on_hangup_clicked)
        self.accept_button.clicked.connect(self._on_accept_clicked)
        self.decline_button.clicked.connect(self._on_decline_clicked)

    def _refresh_local_ip_label(self) -> None:
        local_ip = self.call_manager.get_local_ip()
        self.local_ip_label.setText(local_ip if local_ip else "Unknown")

    def _parse_port(self, text: str) -> int:
        port = int(text.strip())
        if not 1 <= port <= 65535:
            raise ValueError
        return port

    def _parse_local_ports(self) -> tuple[int, int]:
        return (
            self._parse_port(self.local_signaling_port_input.text()),
            self._parse_port(self.local_audio_port_input.text()),
        )

    def _parse_peer_settings(self) -> tuple[str, int, int]:
        ip = self.peer_ip_input.text().strip()
        if not ip:
            raise ValueError("Peer IP is required")
        return (
            ip,
            self._parse_port(self.peer_signaling_port_input.text()),
            self._parse_port(self.peer_audio_port_input.text()),
        )

    def _apply_local_listener_settings(self) -> None:
        signaling_port, audio_port = self._parse_local_ports()
        self.call_manager.restart_listener(signaling_port=signaling_port, audio_port=audio_port)
        self.statusBar().showMessage(f"Listener active on UDP {signaling_port} (audio {audio_port})")

    def _on_apply_listener_clicked(self) -> None:
        try:
            self._refresh_local_ip_label()
            self._apply_local_listener_settings()
        except ValueError:
            QMessageBox.critical(self, "Invalid ports", "Local ports must be integers in range 1..65535.")
        except RuntimeError as exc:
            QMessageBox.critical(self, "Listener error", str(exc))

    def _on_call_clicked(self) -> None:
        try:
            ip, signaling_port, audio_port = self._parse_peer_settings()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid peer settings", str(exc))
            return

        self.call_manager.call(ip=ip, signaling_port=signaling_port, audio_port=audio_port)

    def _on_hangup_clicked(self) -> None:
        self.call_manager.hangup()

    def _on_accept_clicked(self) -> None:
        self.call_manager.accept()

    def _on_decline_clicked(self) -> None:
        self.call_manager.decline()

    def _on_state_changed(self, state: str, message: str) -> None:
        self.statusBar().showMessage(f"{state}: {message}")
        state_enum = CallState(state)
        self.call_button.setEnabled(state_enum in {CallState.IDLE, CallState.ENDED})
        self.accept_button.setEnabled(state_enum == CallState.RINGING)
        self.decline_button.setEnabled(state_enum == CallState.RINGING)
        self.hangup_button.setEnabled(state_enum in {CallState.CALLING, CallState.IN_CALL, CallState.RINGING})

    def _append_log(self, text: str) -> None:
        self.log_area.appendPlainText(text)

    def _log_device_diagnostics(self) -> None:
        try:
            input_devices = list_input_devices()
            output_devices = list_output_devices()
            if not input_devices:
                self.events.log.emit("warning: no input audio devices found")
            if not output_devices:
                self.events.log.emit("warning: no output audio devices found")

            default_in = get_default_input_device()
            default_out = get_default_output_device()

            self.events.log.emit(f"default input device: {get_device_name(default_in)}")
            self.events.log.emit(f"default output device: {get_device_name(default_out)}")
        except Exception as exc:  # noqa: BLE001
            self.events.log.emit(f"device diagnostics error: {exc}")

    def closeEvent(self, event) -> None:  # noqa: N802
        self.call_manager.shutdown()
        super().closeEvent(event)
