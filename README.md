# Mini LAN Voice Call MVP

Локальное desktop-приложение для голосового звонка между **двумя ПК в одной сети**.

Это MVP "мини-дискорда":
- позвонить на второй компьютер,
- принять или отклонить вызов,
- говорить в обе стороны,
- завершить звонок.

## Технологии

- Python 3.11+
- PySide6 (GUI)
- sounddevice (аудио)
- UDP signaling + UDP audio

## Структура проекта

```text
app/
  __init__.py
  main.py
  ui/
    __init__.py
    main_window.py
  core/
    __init__.py
    config.py
    states.py
    signaling.py
    audio_engine.py
    call_manager.py
    devices.py
requirements.txt
README.md
.gitignore
```

## Установка

```bash
python -m venv .venv
```

Активируйте окружение:

```bash
# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate
```

Установите зависимости:

```bash
pip install -r requirements.txt
```

## Запуск приложения

На **обоих** компьютерах запускается одна и та же программа:

```bash
python -m app.main
```

## Как узнать IP второго ПК в Windows

На ПК2 откройте `cmd` и выполните:

```bat
ipconfig
```

Найдите IPv4 активного адаптера, например `192.168.1.50`.

## Как сделать звонок (быстрый сценарий)

1. Запустите приложение на ПК1 и ПК2.
2. На обоих ПК укажите одинаковые порты signaling/audio (по умолчанию уже заполнены).
3. На ПК1 введите IP ПК2 и нажмите **Call**.
4. На ПК2 нажмите **Accept** (или **Decline**).
5. Для завершения нажмите **Hang Up**.

## Windows Firewall

Windows Firewall может блокировать UDP-трафик.
Разрешите приложению Python (или откройте используемые UDP-порты signaling/audio) для входящих подключений.

## Тестирование звонка

- Убедитесь, что оба ПК в одной подсети (например, 192.168.1.x).
- Проверьте, что на обоих ПК есть рабочие устройства ввода/вывода звука.
- Если вызов проходит, но звука нет — проверьте выбор устройств по умолчанию в ОС и Firewall.

## Текущие ограничения MVP

- Нет кодека Opus (сырой PCM `int16`, 48 кГц, mono, 20 мс блок)
- Нет jitter buffer
- Нет mute
- Нет выбора устройства из GUI (используются дефолтные устройства)
- Нет аккаунтов, БД, истории, записи в файл

## Что планируется дальше

- Opus
- jitter buffer
- mute
- выбор устройств
- exe installer
