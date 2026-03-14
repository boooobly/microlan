# UDP Voice MVP (Python)

Минимальный проект для локальной односторонней передачи голоса по UDP в одной сети:

- ПК1: `sender` захватывает микрофон и отправляет UDP-пакеты
- ПК2: `receiver` принимает UDP-пакеты и сразу воспроизводит звук

Проект без GUI, без Opus и без записи в файлы.

## Структура проекта

- `app/config.py`
- `app/audio.py`
- `app/network.py`
- `app/sender.py`
- `app/receiver.py`
- `requirements.txt`
- `.gitignore`
- `README.md`

## Требования

- Python 3.11+
- Оба компьютера в одной локальной сети

## Установка

```bash
python -m venv .venv
```

Активация виртуального окружения:

```bash
# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate
```

Установка зависимостей:

```bash
pip install -r requirements.txt
```

## Как узнать IP второго компьютера в Windows

На ПК2 откройте `cmd` и выполните:

```bat
ipconfig
```

Найдите IPv4 адрес активного адаптера, например `192.168.1.50`.

## Запуск receiver на ПК2

```bash
python -m app.receiver --port 5000
```

## Запуск sender на ПК1

Подставьте IP ПК2:

```bash
python -m app.sender --host 192.168.1.50 --port 5000
```

## Важно: Windows Firewall

Windows Firewall может блокировать входящий UDP-порт на ПК2.
Если звук не приходит, разрешите входящие UDP-соединения для выбранного порта (например, 5000).

## Ограничения MVP

- Только односторонняя связь (`sender -> receiver`)
- Нет jitter buffer
- Нет сжатия (Opus)
- Нет GUI
- Нет записи аудио в файлы

## Следующий этап

- двусторонняя связь
- jitter buffer
- Opus
- push-to-talk
- упаковка в exe
