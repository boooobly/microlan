"""Общие константы для MVP передачи голоса по UDP."""

SAMPLE_RATE = 48_000
CHANNELS = 1
DTYPE = "int16"
BLOCK_DURATION_MS = 20

# Количество сэмплов на один аудиоблок (20 мс при 48 кГц = 960 сэмплов)
BLOCKSIZE = int(SAMPLE_RATE * BLOCK_DURATION_MS / 1000)

DEFAULT_PORT = 5000
RECEIVER_HOST = "0.0.0.0"
