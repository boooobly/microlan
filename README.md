# LAN Voice Calls (2 PCs in one local network)

Одно desktop-приложение для локальных голосовых звонков между двумя компьютерами в одной LAN.

## Стек
- Python 3.11+
- PySide6 (QtWidgets GUI)
- sounddevice
- numpy
- UDP signaling + UDP PCM audio
- optional RNNoise Python binding (для noise suppression)

## Запуск
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
python -m app.main
```

Вход в приложение только через:
```bash
python -m app.main
```

## Optional: RNNoise backend
Noise suppression работает через optional backend.

Попробуйте установить один из поддерживаемых binding-пакетов:
```bash
pip install rnnoise
# или
pip install pyrnnoise
```

Если backend не установлен или не инициализировался:
- приложение продолжит работать,
- denoise просто bypass,
- в UI будет статус `Unavailable`.

## Как звонить между двумя ПК
1. Запустите приложение на ПК1 и ПК2.
2. На каждом ПК в **Local settings** задайте local signaling/audio ports и нажмите **Apply / Restart listener**.
3. В блоке **Audio devices** выберите нужные input/output устройства (или нажмите **Refresh devices**).
4. На ПК1 в **Peer settings** укажите IP и порты ПК2.
5. Нажмите **Call**.
6. На ПК2 нажмите **Accept** (или **Decline**).
7. Для завершения нажмите **Hang Up**.

## Как узнать IP в Windows
Откройте `cmd` и выполните:
```bat
ipconfig
```
Возьмите IPv4 адрес активного адаптера и укажите его как `Peer IP` на другом ПК.

## Что есть в GUI
- **Local settings**: local signaling/audio ports, local IP, restart listener
- **Audio devices**:
  - Input device
  - Output device
  - Refresh devices
- **Peer settings**: peer IP + ports
- **Call controls**: Call / Hang Up / Accept / Decline
- **Audio controls**:
  - Mic sensitivity (gain)
  - Noise gate enabled
  - Noise gate threshold
  - Noise suppression enabled + status (Available/Unavailable)
  - Mute microphone
  - Live Input level
- Status label
- Event log

## Как работает Mic sensitivity
`Mic sensitivity` управляет коэффициентом усиления микрофона до отправки в сеть.
- > 1.0 усиливает сигнал
- < 1.0 ослабляет сигнал
- clipping выполняется безопасно

## Как работает Noise gate
Простой block-level gate:
- считается RMS блока микрофона (нормированный диапазон 0..1)
- если RMS ниже `Noise gate threshold`, блок заменяется тишиной
- если выше — проходит дальше

## Как работает Noise suppression
В pipeline после gain/noise gate применяется denoise:
- если backend доступен и включен — блок обрабатывается RNNoise
- если backend недоступен — блок отправляется без denoise
- приложение не падает при отсутствии backend

## Как работает Mute microphone
При включенном `Mute microphone`:
- захват микрофона и индикатор уровня продолжают работать,
- но в сеть отправляется тишина вместо реального сигнала.

## Playback resilience
Добавлена мягкая устойчивость playback:
- если playback queue пустая — воспроизводится тишина,
- если queue переполнена — дропаются старые фреймы,
- overflow логируется с throttling (не слишком часто).

## Troubleshooting (есть звонок, но нет звука)
- Проверьте, что выбраны корректные Input/Output устройства в GUI.
- Если выбранное устройство исчезло, приложение fallback’ится на default устройство и пишет это в лог.
- Проверьте default input/output устройства ОС.
- Убедитесь, что микрофон и динамик не заняты другим приложением.
- Проверьте, что peer/local порты указаны корректно на обоих ПК.
- Разрешите `python.exe` в Windows Firewall или откройте UDP порты signaling/audio.
- Убедитесь, что оба ПК в одной LAN и пингуются.

## Ограничения текущего этапа
- Без Opus (raw PCM int16, 48kHz, mono, 20ms)
- Без интернет-звонков/NAT traversal
- Без инсталлятора/PyInstaller
- Без эхоподавления
