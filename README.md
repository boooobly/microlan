# UDP Voice MVP (Python)

Минимальный проект для **локальной односторонней передачи голоса** по UDP в одной сети:

- ПК1: `sender.py` (микрофон -> UDP)
- ПК2: `receiver.py` (UDP -> динамики)

Без GUI, без Opus, только MVP.

## Требования

- Python 3.11+
- Сеть: оба ПК в одной локальной сети

## Установка зависимостей

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
```

## Как узнать IP второго компьютера (Windows)

На ПК2 откройте `cmd` и выполните:

```bat
ipconfig
```

Найдите адаптер вашей сети и строку **IPv4 Address**, например `192.168.1.50`.

## Запуск receiver на ПК2

```bash
python receiver.py --port 5000
```

> `receiver.py` слушает `0.0.0.0:<port>`, то есть принимает пакеты на выбранном порту со всех интерфейсов.

## Запуск sender на ПК1

Подставьте IP ПК2 и тот же порт:

```bash
python sender.py --host 192.168.1.50 --port 5000
```

## Важно про Windows Firewall

Windows Firewall может блокировать входящий UDP-порт на ПК2.
Если не слышно звук — проверьте правило брандмауэра для выбранного порта (например, 5000/UDP).

## Структура проекта

- `config.py` — общие константы аудио и сети
- `audio.py` — расчёт размера блока, конвертация и валидация формата
- `network.py` — создание UDP sender/receiver сокетов
- `sender.py` — захват с микрофона и отправка UDP-блоков
- `receiver.py` — приём UDP-блоков и воспроизведение

## Следующий этап

- двусторонняя связь
- jitter buffer
- Opus
- push-to-talk
- упаковка в exe
