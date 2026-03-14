"""Main Qt window for LAN voice calls."""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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

from app.core.audio_processing import noise_suppression_is_available
from app.core.call_manager import CallManager
from app.core.config import (
    APP_ICON_RELATIVE_PATH,
    APP_NAME,
    APP_VERSION,
    DEFAULT_AUDIO_PORT,
    DEFAULT_SIGNALING_PORT,
    MIC_GAIN_DEFAULT,
    NOISE_GATE_ENABLED_DEFAULT,
    NOISE_GATE_THRESHOLD_DEFAULT,
    NOISE_SUPPRESSION_ENABLED_DEFAULT,
)
from app.core.devices import (
    get_default_input_device_index,
    get_default_output_device_index,
    get_device_name,
    human_device_label,
    list_input_devices_with_indices,
    list_output_devices_with_indices,
)
from app.core.i18n import ERROR_TEXTS, UI_TEXTS, format_status_line
from app.core.settings import AppSettingsData, SettingsStore
from app.core.states import CallState
from app.core.utils import format_log_line


class UiEvents(QObject):
    state_changed = Signal(str, str)
    log = Signal(str)
    input_level = Signal(float)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(860, 820)

        self.events = UiEvents()
        self.events.state_changed.connect(self._on_state_changed)
        self.events.log.connect(self._append_log)
        self.events.input_level.connect(self._on_input_level)

        self.call_manager = CallManager(
            on_state_changed=lambda s, t: self.events.state_changed.emit(s.value, t),
            on_log=lambda text: self.events.log.emit(format_log_line(text)),
            on_input_level=lambda level: self.events.input_level.emit(level),
        )

        self._settings_store = SettingsStore()
        self._is_initializing = True

        self._input_devices: list[tuple[int, dict]] = []
        self._output_devices: list[tuple[int, dict]] = []

        self._build_ui()
        self._try_apply_icon()
        self._refresh_local_ip()
        self._refresh_noise_suppression_status()
        self._loaded_settings = self._load_settings_to_ui()
        self._refresh_devices()
        self._apply_saved_device_selection(self._loaded_settings)
        self._apply_audio_settings()
        self._log_device_diagnostics()
        self._restart_listener()
        self._save_current_settings()
        self._update_diagnostics()
        self._is_initializing = False

    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        local_group = QGroupBox(UI_TEXTS["group_local"])
        local_form = QFormLayout(local_group)
        self.local_signaling_port_input = QLineEdit(str(DEFAULT_SIGNALING_PORT))
        self.local_audio_port_input = QLineEdit(str(DEFAULT_AUDIO_PORT))
        self.local_ip_label = QLabel(UI_TEXTS["unknown"])
        self.apply_listener_button = QPushButton(UI_TEXTS["btn_apply_listener"])
        local_form.addRow(UI_TEXTS["label_local_signaling_port"], self.local_signaling_port_input)
        local_form.addRow(UI_TEXTS["label_local_audio_port"], self.local_audio_port_input)
        local_form.addRow(UI_TEXTS["label_local_ip"], self.local_ip_label)
        local_form.addRow(self.apply_listener_button)
        root.addWidget(local_group)

        devices_group = QGroupBox(UI_TEXTS["group_devices"])
        devices_form = QFormLayout(devices_group)
        self.input_device_combo = QComboBox()
        self.output_device_combo = QComboBox()
        self.refresh_devices_button = QPushButton(UI_TEXTS["btn_refresh_devices"])
        devices_form.addRow(UI_TEXTS["label_input_device"], self.input_device_combo)
        devices_form.addRow(UI_TEXTS["label_output_device"], self.output_device_combo)
        devices_form.addRow(self.refresh_devices_button)
        root.addWidget(devices_group)

        peer_group = QGroupBox(UI_TEXTS["group_peer"])
        peer_form = QFormLayout(peer_group)
        self.peer_ip_input = QLineEdit()
        self.peer_ip_input.setPlaceholderText(UI_TEXTS["peer_ip_placeholder"])
        self.peer_signaling_port_input = QLineEdit(str(DEFAULT_SIGNALING_PORT))
        self.peer_audio_port_input = QLineEdit(str(DEFAULT_AUDIO_PORT))
        peer_form.addRow(UI_TEXTS["label_peer_ip"], self.peer_ip_input)
        peer_form.addRow(UI_TEXTS["label_peer_signaling_port"], self.peer_signaling_port_input)
        peer_form.addRow(UI_TEXTS["label_peer_audio_port"], self.peer_audio_port_input)
        root.addWidget(peer_group)

        call_group = QGroupBox(UI_TEXTS["group_call"])
        call_row = QHBoxLayout(call_group)
        self.call_button = QPushButton(UI_TEXTS["btn_call"])
        self.hangup_button = QPushButton(UI_TEXTS["btn_hangup"])
        self.accept_button = QPushButton(UI_TEXTS["btn_accept"])
        self.decline_button = QPushButton(UI_TEXTS["btn_decline"])
        call_row.addWidget(self.call_button)
        call_row.addWidget(self.hangup_button)
        call_row.addWidget(self.accept_button)
        call_row.addWidget(self.decline_button)
        root.addWidget(call_group)

        audio_group = QGroupBox(UI_TEXTS["group_audio"])
        audio_form = QFormLayout(audio_group)
        self.mic_gain_slider = QSlider(Qt.Horizontal)
        self.mic_gain_slider.setRange(0, 300)
        self.mic_gain_slider.setValue(int(MIC_GAIN_DEFAULT * 100))
        self.mic_gain_label = QLabel(f"{MIC_GAIN_DEFAULT:.2f}x")
        gain_row = QHBoxLayout()
        gain_row.addWidget(self.mic_gain_slider)
        gain_row.addWidget(self.mic_gain_label)

        self.noise_gate_enabled = QCheckBox(UI_TEXTS["checkbox_noise_gate"])
        self.noise_gate_enabled.setChecked(NOISE_GATE_ENABLED_DEFAULT)

        self.noise_gate_slider = QSlider(Qt.Horizontal)
        self.noise_gate_slider.setRange(0, 200)
        self.noise_gate_slider.setValue(int(NOISE_GATE_THRESHOLD_DEFAULT * 1000))
        self.noise_gate_label = QLabel(f"{NOISE_GATE_THRESHOLD_DEFAULT:.3f}")
        gate_row = QHBoxLayout()
        gate_row.addWidget(self.noise_gate_slider)
        gate_row.addWidget(self.noise_gate_label)

        self.noise_suppression_enabled = QCheckBox(UI_TEXTS["checkbox_noise_suppression"])
        self.noise_suppression_enabled.setChecked(NOISE_SUPPRESSION_ENABLED_DEFAULT)
        self.noise_suppression_status = QLabel("Недоступно")

        suppression_row = QHBoxLayout()
        suppression_row.addWidget(self.noise_suppression_enabled)
        suppression_row.addWidget(QLabel(UI_TEXTS["label_noise_suppression_status"]))
        suppression_row.addWidget(self.noise_suppression_status)
        suppression_row.addStretch(1)

        self.mute_mic_checkbox = QCheckBox(UI_TEXTS["checkbox_mute"])
        self.mute_mic_checkbox.setChecked(False)

        self.input_level_label = QLabel(f"{UI_TEXTS['label_input_level']}: 0.000")

        audio_form.addRow(UI_TEXTS["label_mic_sensitivity"], gain_row)
        audio_form.addRow(UI_TEXTS["label_noise_gate"], self.noise_gate_enabled)
        audio_form.addRow(UI_TEXTS["label_noise_gate_threshold"], gate_row)
        audio_form.addRow(UI_TEXTS["label_noise_suppression"], suppression_row)
        audio_form.addRow(UI_TEXTS["label_mic_mute"], self.mute_mic_checkbox)
        audio_form.addRow(UI_TEXTS["label_input_level"], self.input_level_label)
        root.addWidget(audio_group)

        diagnostics_group = QGroupBox(UI_TEXTS["group_diagnostics"])
        diagnostics_form = QFormLayout(diagnostics_group)
        self.diag_version_label = QLabel(f"{APP_NAME} v{APP_VERSION}")
        self.diag_listener_label = QLabel(UI_TEXTS["listener_stopped"])
        self.diag_noise_label = QLabel(UI_TEXTS["unknown"])
        self.diag_devices_label = QLabel(UI_TEXTS["unknown"])
        diagnostics_form.addRow(UI_TEXTS["label_diag_version"], self.diag_version_label)
        diagnostics_form.addRow(UI_TEXTS["label_diag_listener"], self.diag_listener_label)
        diagnostics_form.addRow(UI_TEXTS["label_diag_noise"], self.diag_noise_label)
        diagnostics_form.addRow(UI_TEXTS["label_diag_devices"], self.diag_devices_label)
        root.addWidget(diagnostics_group)

        self.status_label = QLabel(UI_TEXTS["status_init"])
        root.addWidget(self.status_label)

        self.log_area = QPlainTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setPlaceholderText(UI_TEXTS["log_placeholder"])
        root.addWidget(self.log_area)

        self.apply_listener_button.clicked.connect(self._on_apply_listener)
        self.refresh_devices_button.clicked.connect(self._on_refresh_devices)
        self.call_button.clicked.connect(self._on_call)
        self.hangup_button.clicked.connect(self.call_manager.hangup)
        self.accept_button.clicked.connect(self.call_manager.accept)
        self.decline_button.clicked.connect(self.call_manager.decline)

        self.local_signaling_port_input.editingFinished.connect(self._save_current_settings)
        self.local_audio_port_input.editingFinished.connect(self._save_current_settings)
        self.peer_ip_input.editingFinished.connect(self._save_current_settings)
        self.peer_signaling_port_input.editingFinished.connect(self._save_current_settings)
        self.peer_audio_port_input.editingFinished.connect(self._save_current_settings)

        self.input_device_combo.currentIndexChanged.connect(self._on_audio_controls_changed)
        self.output_device_combo.currentIndexChanged.connect(self._on_audio_controls_changed)
        self.mic_gain_slider.valueChanged.connect(self._on_audio_controls_changed)
        self.noise_gate_enabled.checkStateChanged.connect(self._on_audio_controls_changed)
        self.noise_gate_slider.valueChanged.connect(self._on_audio_controls_changed)
        self.noise_suppression_enabled.checkStateChanged.connect(self._on_audio_controls_changed)
        self.mute_mic_checkbox.checkStateChanged.connect(self._on_audio_controls_changed)

    def _try_apply_icon(self) -> None:
        icon = QIcon(APP_ICON_RELATIVE_PATH)
        if not icon.isNull():
            self.setWindowIcon(icon)

    def _parse_port(self, text: str) -> int:
        value = int(text.strip())
        if not 1 <= value <= 65535:
            raise ValueError(ERROR_TEXTS["err_port_range"])
        return value

    def _parse_local(self) -> tuple[int, int]:
        return (
            self._parse_port(self.local_signaling_port_input.text()),
            self._parse_port(self.local_audio_port_input.text()),
        )

    def _parse_peer(self) -> tuple[str, int, int]:
        ip = self.peer_ip_input.text().strip()
        if not ip:
            raise ValueError(ERROR_TEXTS["err_peer_ip_required"])
        return (
            ip,
            self._parse_port(self.peer_signaling_port_input.text()),
            self._parse_port(self.peer_audio_port_input.text()),
        )

    def _selected_input_device_index(self) -> int | None:
        idx = self.input_device_combo.currentIndex()
        if idx < 0:
            return None
        return self.input_device_combo.itemData(idx)

    def _selected_output_device_index(self) -> int | None:
        idx = self.output_device_combo.currentIndex()
        if idx < 0:
            return None
        return self.output_device_combo.itemData(idx)

    def _on_apply_listener(self) -> None:
        try:
            self._refresh_local_ip()
            self._refresh_devices()
            self._restart_listener()
            self._apply_audio_settings()
            self._save_current_settings()
        except ValueError as exc:
            QMessageBox.warning(self, ERROR_TEXTS["title_invalid_local"], str(exc))
            self.events.log.emit(format_log_line(f"ошибка локальных настроек: {exc}"))
        except RuntimeError as exc:
            QMessageBox.critical(self, ERROR_TEXTS["title_listener_error"], str(exc))
            self.events.log.emit(format_log_line(f"ошибка запуска listener: {exc}"))

    def _restart_listener(self) -> None:
        signaling_port, audio_port = self._parse_local()
        self.call_manager.restart_listener(signaling_port=signaling_port, audio_port=audio_port)
        self._update_diagnostics()

    def _on_call(self) -> None:
        try:
            ip, sig_port, audio_port = self._parse_peer()
            self._validate_before_call()
        except ValueError as exc:
            QMessageBox.warning(self, ERROR_TEXTS["title_precheck_failed"], str(exc))
            self.events.log.emit(format_log_line(f"проверка перед звонком не пройдена: {exc}"))
            return

        self.call_manager.call(ip=ip, signaling_port=sig_port, audio_port=audio_port)
        self._save_current_settings()

    def _validate_before_call(self) -> None:
        if not self.peer_ip_input.text().strip():
            raise ValueError(ERROR_TEXTS["err_peer_ip_required"])
        if not self.call_manager.signaling:
            raise ValueError(ERROR_TEXTS["err_listener_required"])
        if self._selected_output_device_index() is None:
            raise ValueError(ERROR_TEXTS["err_output_required"])
        if not self.mute_mic_checkbox.isChecked() and self._selected_input_device_index() is None:
            raise ValueError(ERROR_TEXTS["err_input_required"])

    def _refresh_local_ip(self) -> None:
        self.local_ip_label.setText(self.call_manager.get_local_ip())

    def _refresh_devices(self) -> None:
        selected_in = self._selected_input_device_index()
        selected_out = self._selected_output_device_index()
        default_in = get_default_input_device_index()
        default_out = get_default_output_device_index()

        self._input_devices = list_input_devices_with_indices()
        self._output_devices = list_output_devices_with_indices()

        self.input_device_combo.blockSignals(True)
        self.output_device_combo.blockSignals(True)
        self.input_device_combo.clear()
        self.output_device_combo.clear()

        for index, info in self._input_devices:
            self.input_device_combo.addItem(human_device_label(index, info), index)
        for index, info in self._output_devices:
            self.output_device_combo.addItem(human_device_label(index, info), index)

        in_target = selected_in if selected_in is not None else default_in
        out_target = selected_out if selected_out is not None else default_out
        self._select_combo_by_value(self.input_device_combo, in_target)
        self._select_combo_by_value(self.output_device_combo, out_target)

        self.input_device_combo.blockSignals(False)
        self.output_device_combo.blockSignals(False)

        self._update_diagnostics()

    @staticmethod
    def _select_combo_by_value(combo: QComboBox, value: int | None) -> bool:
        if combo.count() == 0:
            return False
        if value is None:
            combo.setCurrentIndex(0)
            return True
        found_idx = combo.findData(value)
        combo.setCurrentIndex(found_idx if found_idx >= 0 else 0)
        return found_idx >= 0

    def _on_refresh_devices(self) -> None:
        self._refresh_devices()
        self._apply_audio_settings()
        self._save_current_settings()

    def _refresh_noise_suppression_status(self) -> None:
        status, details, available = self.call_manager.noise_suppression_status()
        self.noise_suppression_status.setText(status)
        self.noise_suppression_status.setStyleSheet("color: green;" if available else "color: darkred;")
        self.noise_suppression_status.setToolTip(details)
        if not available and self.noise_suppression_enabled.isChecked():
            self.noise_suppression_enabled.setChecked(False)
        if not available:
            self.events.log.emit(format_log_line(details))
        self._update_diagnostics()

    def _on_audio_controls_changed(self) -> None:
        self._apply_audio_settings()
        self._save_current_settings()
        self._update_diagnostics()

    def _apply_audio_settings(self) -> None:
        gain = self.mic_gain_slider.value() / 100.0
        gate_threshold = self.noise_gate_slider.value() / 1000.0
        self.mic_gain_label.setText(f"{gain:.2f}x")
        self.noise_gate_label.setText(f"{gate_threshold:.3f}")

        denoise_enabled = self.noise_suppression_enabled.isChecked() and noise_suppression_is_available()

        self.call_manager.update_audio_settings(
            selected_input_device=self._selected_input_device_index(),
            selected_output_device=self._selected_output_device_index(),
            mute_enabled=self.mute_mic_checkbox.isChecked(),
            mic_gain=gain,
            noise_gate_enabled=self.noise_gate_enabled.isChecked(),
            noise_gate_threshold=gate_threshold,
            noise_suppression_enabled=denoise_enabled,
        )

    def _load_settings_to_ui(self) -> AppSettingsData:
        data = self._settings_store.load()

        local_sig = self._safe_port(data.local_signaling_port, DEFAULT_SIGNALING_PORT, "локальный signaling порт")
        local_audio = self._safe_port(data.local_audio_port, DEFAULT_AUDIO_PORT, "локальный аудиопорт")
        peer_sig = self._safe_port(data.peer_signaling_port, DEFAULT_SIGNALING_PORT, "порт signaling второго ПК")
        peer_audio = self._safe_port(data.peer_audio_port, DEFAULT_AUDIO_PORT, "аудиопорт второго ПК")

        self.local_signaling_port_input.setText(str(local_sig))
        self.local_audio_port_input.setText(str(local_audio))
        self.peer_ip_input.setText(data.peer_ip.strip())
        self.peer_signaling_port_input.setText(str(peer_sig))
        self.peer_audio_port_input.setText(str(peer_audio))

        self.mic_gain_slider.setValue(max(0, min(300, int(data.mic_gain * 100))))
        self.noise_gate_enabled.setChecked(bool(data.noise_gate_enabled))
        self.noise_gate_slider.setValue(max(0, min(200, int(data.noise_gate_threshold * 1000))))
        self.noise_suppression_enabled.setChecked(bool(data.noise_suppression_enabled))
        self.mute_mic_checkbox.setChecked(bool(data.mute_microphone))
        return data

    def _apply_saved_device_selection(self, data: AppSettingsData) -> None:
        in_ok = self._select_combo_by_value(self.input_device_combo, data.selected_input_device)
        out_ok = self._select_combo_by_value(self.output_device_combo, data.selected_output_device)
        if data.selected_input_device is not None and not in_ok:
            self.events.log.emit(
                format_log_line("сохраненное устройство ввода недоступно, выбран default")
            )
        if data.selected_output_device is not None and not out_ok:
            self.events.log.emit(
                format_log_line("сохраненное устройство вывода недоступно, выбран default")
            )

    def _safe_port(self, value: int, default: int, label: str) -> int:
        if 1 <= int(value) <= 65535:
            return int(value)
        self.events.log.emit(format_log_line(f"некорректный {label} в настройках, применен default {default}"))
        return default

    def _save_current_settings(self) -> None:
        if self._is_initializing:
            return

        settings = AppSettingsData(
            local_signaling_port=self._safe_port_or_default(self.local_signaling_port_input.text(), DEFAULT_SIGNALING_PORT),
            local_audio_port=self._safe_port_or_default(self.local_audio_port_input.text(), DEFAULT_AUDIO_PORT),
            peer_ip=self.peer_ip_input.text().strip(),
            peer_signaling_port=self._safe_port_or_default(self.peer_signaling_port_input.text(), DEFAULT_SIGNALING_PORT),
            peer_audio_port=self._safe_port_or_default(self.peer_audio_port_input.text(), DEFAULT_AUDIO_PORT),
            selected_input_device=self._selected_input_device_index(),
            selected_output_device=self._selected_output_device_index(),
            mic_gain=self.mic_gain_slider.value() / 100.0,
            noise_gate_enabled=self.noise_gate_enabled.isChecked(),
            noise_gate_threshold=self.noise_gate_slider.value() / 1000.0,
            noise_suppression_enabled=self.noise_suppression_enabled.isChecked(),
            mute_microphone=self.mute_mic_checkbox.isChecked(),
        )
        self._settings_store.save(settings)

    def _safe_port_or_default(self, value: str, default: int) -> int:
        try:
            return self._safe_port(int(value.strip()), default, "порт")
        except (ValueError, TypeError):
            return default

    def _on_state_changed(self, state_value: str, message: str) -> None:
        state = CallState(state_value)
        self.status_label.setText(format_status_line(state.value, message))
        self.call_button.setEnabled(state in {CallState.IDLE, CallState.ENDED})
        self.accept_button.setEnabled(state == CallState.RINGING)
        self.decline_button.setEnabled(state == CallState.RINGING)
        self.hangup_button.setEnabled(state in {CallState.CALLING, CallState.RINGING, CallState.IN_CALL})
        self._update_diagnostics()

    def _on_input_level(self, level: float) -> None:
        self.input_level_label.setText(f"{UI_TEXTS['label_input_level']}: {level:.3f}")

    def _append_log(self, message: str) -> None:
        self.log_area.appendPlainText(message)

    def _log_device_diagnostics(self) -> None:
        if not self._input_devices:
            self.events.log.emit(format_log_line("предупреждение: устройства ввода не найдены"))
            self.status_label.setText("Статус: Ошибка, устройство ввода не найдено")
        if not self._output_devices:
            self.events.log.emit(format_log_line("предупреждение: устройства вывода не найдены"))
            self.status_label.setText("Статус: Ошибка, устройство вывода не найдено")

        self.events.log.emit(
            format_log_line(f"устройство ввода по умолчанию: {get_device_name(get_default_input_device_index())}")
        )
        self.events.log.emit(
            format_log_line(f"устройство вывода по умолчанию: {get_device_name(get_default_output_device_index())}")
        )

    def _update_diagnostics(self) -> None:
        self.diag_listener_label.setText(
            UI_TEXTS["listener_running"] if self.call_manager.signaling else UI_TEXTS["listener_stopped"]
        )
        self.diag_noise_label.setText(self.noise_suppression_status.text())
        in_name = get_device_name(self._selected_input_device_index())
        out_name = get_device_name(self._selected_output_device_index())
        self.diag_devices_label.setText(f"Ввод: {in_name}; Вывод: {out_name}")

    def closeEvent(self, event) -> None:  # noqa: N802
        self._save_current_settings()
        self.call_manager.shutdown()
        super().closeEvent(event)
