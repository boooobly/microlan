# LAN Voice Calls (2 PCs in one local network)

Одно desktop-приложение для локальных голосовых звонков между двумя компьютерами в одной LAN.

## Стек
- Python 3.11+
- PySide6 (QtWidgets GUI)
- sounddevice
- numpy
- UDP signaling + UDP PCM audio

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

## Как звонить между двумя ПК
1. Запустите приложение на ПК1 и ПК2.
2. На каждом ПК в **Local settings** задайте:
   - Local signaling port
   - Local audio port
   - Нажмите **Apply / Restart listener**
3. На ПК1 в **Peer settings** укажите IP и порты ПК2.
4. Нажмите **Call**.
5. На ПК2 нажмите **Accept** (или **Decline**).
6. Для завершения нажмите **Hang Up**.

## Как узнать IP в Windows
Откройте `cmd` и выполните:
```bat
ipconfig
```
Возьмите IPv4 адрес активного адаптера и укажите его как `Peer IP` на другом ПК.

## Что есть в GUI
- **Local settings**: local signaling/audio ports, local IP, restart listener
- **Peer settings**: peer IP + ports
- **Call controls**: Call / Hang Up / Accept / Decline
- **Audio controls**:
  - Mic sensitivity (gain)
  - Noise gate enabled
  - Noise gate threshold
  - Noise suppression enabled *(пока заглушка, отключено в UI)*
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
- если выше — пропускается дальше

## Noise suppression
`Noise suppression` сейчас заглушка для следующего этапа (под RNNoise/другой denoise backend).
Pipeline уже подготовлен, но фактическое подавление пока не реализовано.

## Troubleshooting (есть звонок, но нет звука)
- Проверьте default input/output устройства ОС.
- Убедитесь, что микрофон и динамик не заняты другим приложением.
- Проверьте, что peer/local порты указаны корректно на обоих ПК.
- Разрешите `python.exe` в Windows Firewall или откройте UDP порты signaling/audio.
- Убедитесь, что оба ПК в одной LAN и пингуются.

## Ограничения текущего этапа
- Без Opus (raw PCM int16, 48kHz, mono, 20ms)
- Без интернет-звонков/NAT traversal
- Без инсталлятора/PyInstaller
