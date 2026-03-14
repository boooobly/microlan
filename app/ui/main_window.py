"""Main Qt window for local LAN call control."""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
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
from app.core.states import CallState


class UiEvents(QObject):
    state_changed = Signal(str, str)
    log = Signal(str)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Mini LAN Voice Call MVP")
        self.resize(700, 420)

        self.events = UiEvents()
        self.events.state_changed.connect(self._on_state_changed)
        self.events.log.connect(self._append_log)

        self.call_manager = CallManager(
            on_state_changed=lambda state, text: self.events.state_changed.emit(state.value, text),
            on_log=lambda text: self.events.log.emit(text),
        )

        self._build_ui()
        self._start_signaling_from_inputs()

    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)

        form_layout = QGridLayout()
        layout.addLayout(form_layout)

        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("192.168.1.50")
        self.signaling_port_input = QLineEdit(str(DEFAULT_SIGNALING_PORT))
        self.audio_port_input = QLineEdit(str(DEFAULT_AUDIO_PORT))

        form_layout.addWidget(QLabel("Peer IP:"), 0, 0)
        form_layout.addWidget(self.ip_input, 0, 1)
        form_layout.addWidget(QLabel("Signaling Port:"), 1, 0)
        form_layout.addWidget(self.signaling_port_input, 1, 1)
        form_layout.addWidget(QLabel("Audio Port:"), 2, 0)
        form_layout.addWidget(self.audio_port_input, 2, 1)

        buttons_row = QHBoxLayout()
        layout.addLayout(buttons_row)

        self.call_button = QPushButton("Call")
        self.hangup_button = QPushButton("Hang Up")
        self.accept_button = QPushButton("Accept")
        self.decline_button = QPushButton("Decline")

        buttons_row.addWidget(self.call_button)
        buttons_row.addWidget(self.hangup_button)
        buttons_row.addWidget(self.accept_button)
        buttons_row.addWidget(self.decline_button)

        self.log_area = QPlainTextEdit()
        self.log_area.setReadOnly(True)
        layout.addWidget(self.log_area)

        status = QStatusBar(self)
        self.setStatusBar(status)
        self.statusBar().showMessage("Initializing...")

        self.call_button.clicked.connect(self._on_call_clicked)
        self.hangup_button.clicked.connect(self._on_hangup_clicked)
        self.accept_button.clicked.connect(self._on_accept_clicked)
        self.decline_button.clicked.connect(self._on_decline_clicked)

    def _parse_ports(self) -> tuple[int, int] | None:
        try:
            signaling_port = int(self.signaling_port_input.text().strip())
            audio_port = int(self.audio_port_input.text().strip())
            if not (1 <= signaling_port <= 65535 and 1 <= audio_port <= 65535):
                raise ValueError
            return signaling_port, audio_port
        except ValueError:
            QMessageBox.critical(self, "Invalid ports", "Ports must be integers in range 1..65535.")
            return None

    def _start_signaling_from_inputs(self) -> None:
        parsed = self._parse_ports()
        if not parsed:
            return
        signaling_port, audio_port = parsed
        try:
            self.call_manager.start_listener(signaling_port=signaling_port, audio_port=audio_port)
        except RuntimeError as exc:
            QMessageBox.critical(self, "Signaling error", str(exc))
            self.statusBar().showMessage("ERROR: failed to start signaling")

    def _on_call_clicked(self) -> None:
        ip = self.ip_input.text().strip()
        if not ip:
            QMessageBox.warning(self, "Missing IP", "Enter peer IP address.")
            return

        parsed = self._parse_ports()
        if not parsed:
            return
        signaling_port, audio_port = parsed

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

    def closeEvent(self, event) -> None:  # noqa: N802
        self.call_manager.shutdown()
        super().closeEvent(event)
