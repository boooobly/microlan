"""Централизованные пользовательские тексты (русский язык)."""

from __future__ import annotations

from app.core.states import CallState

STATE_LABELS: dict[str, str] = {
    CallState.IDLE.value: "Ожидание",
    CallState.CALLING.value: "Исходящий звонок",
    CallState.RINGING.value: "Входящий звонок",
    CallState.IN_CALL.value: "В разговоре",
    CallState.ENDED.value: "Завершено",
    CallState.ERROR.value: "Ошибка",
}

UI_TEXTS = {
    "window_title": "LAN голосовые звонки",
    "group_local": "Локальные настройки",
    "group_devices": "Аудиоустройства",
    "group_peer": "Настройки второго ПК",
    "group_call": "Управление звонком",
    "group_audio": "Настройки звука",
    "btn_apply_listener": "Применить / Перезапустить прослушивание",
    "btn_refresh_devices": "Обновить устройства",
    "btn_call": "Позвонить",
    "btn_hangup": "Завершить",
    "btn_accept": "Принять",
    "btn_decline": "Отклонить",
    "label_local_signaling_port": "Локальный порт signaling",
    "label_local_audio_port": "Локальный аудиопорт",
    "label_local_ip": "Локальный IP",
    "label_input_device": "Устройство ввода",
    "label_output_device": "Устройство вывода",
    "label_peer_ip": "IP второго ПК",
    "label_peer_signaling_port": "Порт signaling второго ПК",
    "label_peer_audio_port": "Аудиопорт второго ПК",
    "label_mic_sensitivity": "Чувствительность микрофона",
    "label_noise_gate": "Шумовой порог включен",
    "label_noise_gate_threshold": "Порог шума",
    "label_noise_suppression": "Шумоподавление",
    "label_noise_suppression_status": "Состояние:",
    "label_mic_mute": "Микрофон",
    "label_input_level": "Уровень сигнала",
    "checkbox_noise_gate": "Шумовой порог включен",
    "checkbox_noise_suppression": "Шумоподавление",
    "checkbox_mute": "Выключить микрофон",
    "status_init": "Статус: Инициализация",
    "log_placeholder": "Журнал событий",
    "peer_ip_placeholder": "192.168.1.50",
    "unknown": "Неизвестно",
}

ERROR_TEXTS = {
    "title_invalid_local": "Некорректные локальные настройки",
    "title_listener_error": "Ошибка прослушивания",
    "title_invalid_peer": "Некорректные настройки второго ПК",
    "err_port_range": "Порт должен быть в диапазоне 1..65535",
    "err_peer_ip_required": "Укажите IP второго ПК",
}


def state_display_name(state_value: str) -> str:
    return STATE_LABELS.get(state_value, state_value)


def format_status_line(state_value: str, message: str) -> str:
    readable = state_display_name(state_value)
    msg = message.strip()
    if msg:
        return f"Статус: {readable}, {msg}"
    return f"Статус: {readable}"
