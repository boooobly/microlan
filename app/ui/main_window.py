"""Main Qt window for LAN voice calls."""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.core.call_manager import CallManager
from app.core.config import (
    DEFAULT_AUDIO_PORT,
    DEFAULT_SIGNALING_PORT,
    MIC_GAIN_DEFAULT,
    NOISE_GATE_ENABLED_DEFAULT,
    NOISE_GATE_THRESHOLD_DEFAULT,
    NOISE_SUPPRESSION_ENABLED_DEFAULT,
)
from app.core.devices import (
    get_default_input_device,
    get_default_output_device,
    get_device_name,
    list_input_devices,
    list_output_devices,
)
from app.core.states import CallState
from app.core.utils import format_log_line


class UiEvents(QObject):
    state_changed = Signal(str, str)
    log = Signal(str)
    input_level = Signal(float)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("LAN Voice Calls")
        self.resize(820, 700)

        self.events = UiEvents()
        self.events.state_changed.connect(self._on_state_changed)
        self.events.log.connect(self._append_log)
        self.events.input_level.connect(self._on_input_level)

        self.call_manager = CallManager(
            on_state_changed=lambda s, t: self.events.state_changed.emit(s.value, t),
            on_log=lambda text: self.events.log.emit(format_log_line(text)),
            on_input_level=lambda level: self.events.input_level.emit(level),
        )

        self._build_ui()
        self._refresh_local_ip()
        self._apply_audio_settings()
        self._log_device_diagnostics()
        self._restart_listener()

    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        local_group = QGroupBox("Local settings")
        local_form = QFormLayout(local_group)
        self.local_signaling_port_input = QLineEdit(str(DEFAULT_SIGNALING_PORT))
        self.local_audio_port_input = QLineEdit(str(DEFAULT_AUDIO_PORT))
        self.local_ip_label = QLabel("Unknown")
        self.apply_listener_button = QPushButton("Apply / Restart listener")
        local_form.addRow("Local signaling port", self.local_signaling_port_input)
        local_form.addRow("Local audio port", self.local_audio_port_input)
        local_form.addRow("Local IP", self.local_ip_label)
        local_form.addRow(self.apply_listener_button)
        root.addWidget(local_group)

        peer_group = QGroupBox("Peer settings")
        peer_form = QFormLayout(peer_group)
        self.peer_ip_input = QLineEdit()
        self.peer_ip_input.setPlaceholderText("192.168.1.50")
        self.peer_signaling_port_input = QLineEdit(str(DEFAULT_SIGNALING_PORT))
        self.peer_audio_port_input = QLineEdit(str(DEFAULT_AUDIO_PORT))
        peer_form.addRow("Peer IP", self.peer_ip_input)
        peer_form.addRow("Peer signaling port", self.peer_signaling_port_input)
        peer_form.addRow("Peer audio port", self.peer_audio_port_input)
        root.addWidget(peer_group)

        call_group = QGroupBox("Call controls")
        call_row = QHBoxLayout(call_group)
        self.call_button = QPushButton("Call")
        self.hangup_button = QPushButton("Hang Up")
        self.accept_button = QPushButton("Accept")
        self.decline_button = QPushButton("Decline")
        call_row.addWidget(self.call_button)
        call_row.addWidget(self.hangup_button)
        call_row.addWidget(self.accept_button)
        call_row.addWidget(self.decline_button)
        root.addWidget(call_group)

        audio_group = QGroupBox("Audio controls")
        audio_form = QFormLayout(audio_group)
        self.mic_gain_slider = QSlider(Qt.Horizontal)
        self.mic_gain_slider.setRange(0, 300)
        self.mic_gain_slider.setValue(int(MIC_GAIN_DEFAULT * 100))
        self.mic_gain_label = QLabel(f"{MIC_GAIN_DEFAULT:.2f}x")
        gain_row = QHBoxLayout()
        gain_row.addWidget(self.mic_gain_slider)
        gain_row.addWidget(self.mic_gain_label)

        self.noise_gate_enabled = QCheckBox("Noise gate enabled")
        self.noise_gate_enabled.setChecked(NOISE_GATE_ENABLED_DEFAULT)

        self.noise_gate_slider = QSlider(Qt.Horizontal)
        self.noise_gate_slider.setRange(0, 200)
        self.noise_gate_slider.setValue(int(NOISE_GATE_THRESHOLD_DEFAULT * 1000))
        self.noise_gate_label = QLabel(f"{NOISE_GATE_THRESHOLD_DEFAULT:.3f}")
        ng_row = QHBoxLayout()
        ng_row.addWidget(self.noise_gate_slider)
        ng_row.addWidget(self.noise_gate_label)

        self.noise_suppression_enabled = QCheckBox("Noise suppression enabled (not implemented)")
        self.noise_suppression_enabled.setChecked(NOISE_SUPPRESSION_ENABLED_DEFAULT)
        self.noise_suppression_enabled.setEnabled(False)

        self.input_level_label = QLabel("Input level: 0.000")

        audio_form.addRow("Mic sensitivity", gain_row)
        audio_form.addRow("Noise gate", self.noise_gate_enabled)
        audio_form.addRow("Noise gate threshold", ng_row)
        audio_form.addRow("Noise suppression", self.noise_suppression_enabled)
        audio_form.addRow("Live", self.input_level_label)
        root.addWidget(audio_group)

        self.status_label = QLabel("Status: Initializing")
        root.addWidget(self.status_label)

        self.log_area = QPlainTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setPlaceholderText("Event log")
        root.addWidget(self.log_area)

        self.apply_listener_button.clicked.connect(self._on_apply_listener)
        self.call_button.clicked.connect(self._on_call)
        self.hangup_button.clicked.connect(self.call_manager.hangup)
        self.accept_button.clicked.connect(self.call_manager.accept)
        self.decline_button.clicked.connect(self.call_manager.decline)

        self.mic_gain_slider.valueChanged.connect(self._on_audio_controls_changed)
        self.noise_gate_enabled.checkStateChanged.connect(self._on_audio_controls_changed)
        self.noise_gate_slider.valueChanged.connect(self._on_audio_controls_changed)

    def _parse_port(self, text: str) -> int:
        value = int(text.strip())
        if not 1 <= value <= 65535:
            raise ValueError("Port must be in 1..65535")
        return value

    def _parse_local(self) -> tuple[int, int]:
        return (
            self._parse_port(self.local_signaling_port_input.text()),
            self._parse_port(self.local_audio_port_input.text()),
        )

    def _parse_peer(self) -> tuple[str, int, int]:
        ip = self.peer_ip_input.text().strip()
        if not ip:
            raise ValueError("Peer IP is required")
        return (
            ip,
            self._parse_port(self.peer_signaling_port_input.text()),
            self._parse_port(self.peer_audio_port_input.text()),
        )

    def _on_apply_listener(self) -> None:
        try:
            self._refresh_local_ip()
            self._restart_listener()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid local settings", str(exc))
        except RuntimeError as exc:
            QMessageBox.critical(self, "Listener error", str(exc))

    def _restart_listener(self) -> None:
        signaling_port, audio_port = self._parse_local()
        self.call_manager.restart_listener(signaling_port=signaling_port, audio_port=audio_port)

    def _on_call(self) -> None:
        try:
            ip, sig_port, audio_port = self._parse_peer()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid peer settings", str(exc))
            return
        self.call_manager.call(ip=ip, signaling_port=sig_port, audio_port=audio_port)

    def _refresh_local_ip(self) -> None:
        self.local_ip_label.setText(self.call_manager.get_local_ip())

    def _on_audio_controls_changed(self) -> None:
        self._apply_audio_settings()

    def _apply_audio_settings(self) -> None:
        gain = self.mic_gain_slider.value() / 100.0
        gate_threshold = self.noise_gate_slider.value() / 1000.0
        self.mic_gain_label.setText(f"{gain:.2f}x")
        self.noise_gate_label.setText(f"{gate_threshold:.3f}")

        self.call_manager.update_audio_settings(
            mic_gain=gain,
            noise_gate_enabled=self.noise_gate_enabled.isChecked(),
            noise_gate_threshold=gate_threshold,
            noise_suppression_enabled=self.noise_suppression_enabled.isChecked(),
        )

    def _on_state_changed(self, state_value: str, message: str) -> None:
        state = CallState(state_value)
        self.status_label.setText(f"Status: {state.value} — {message}")
        self.call_button.setEnabled(state in {CallState.IDLE, CallState.ENDED})
        self.accept_button.setEnabled(state == CallState.RINGING)
        self.decline_button.setEnabled(state == CallState.RINGING)
        self.hangup_button.setEnabled(state in {CallState.CALLING, CallState.RINGING, CallState.IN_CALL})

    def _on_input_level(self, level: float) -> None:
        self.input_level_label.setText(f"Input level: {level:.3f}")

    def _append_log(self, message: str) -> None:
        self.log_area.appendPlainText(message)

    def _log_device_diagnostics(self) -> None:
        try:
            input_devices = list_input_devices()
            output_devices = list_output_devices()
            if not input_devices:
                self.events.log.emit(format_log_line("warning: no input audio devices found"))
                self.status_label.setText("Status: WARNING — No input device")
            if not output_devices:
                self.events.log.emit(format_log_line("warning: no output audio devices found"))
                self.status_label.setText("Status: WARNING — No output device")

            self.events.log.emit(
                format_log_line(f"default input device: {get_device_name(get_default_input_device())}")
            )
            self.events.log.emit(
                format_log_line(f"default output device: {get_device_name(get_default_output_device())}")
            )
        except Exception as exc:  # noqa: BLE001
            self.events.log.emit(format_log_line(f"device diagnostics failed: {exc}"))

    def closeEvent(self, event) -> None:  # noqa: N802
        self.call_manager.shutdown()
        super().closeEvent(event)
