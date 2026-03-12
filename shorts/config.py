"""Configuration Shorts Sagesse — videos courtes 15-45s, format 9:16."""
import os
from app import config as app_config

# Reutilise les chemins de base de app/
BASE_PATH = app_config.BASE_PATH
SHORTS_DIR = f"{BASE_PATH}/shorts"
SHORTS_HISTORY_DIR = f"{BASE_PATH}/shorts/history"
SHORTS_VIDEOS_DIR = f"{BASE_PATH}/shorts/videos"
SHORTS_IMAGES_DIR = f"{BASE_PATH}/shorts/images"
SHORTS_AUDIO_DIR = f"{BASE_PATH}/shorts/audio"

# Schedule
SCHEDULE_HOUR = int(os.getenv("SHORTS_SCHEDULE_HOUR", "10"))
SCHEDULE_MINUTE = int(os.getenv("SHORTS_SCHEDULE_MINUTE", "0"))

# Contenu
SCRIPT_MIN_WORDS = 40
SCRIPT_MAX_WORDS = 100
NB_IMAGES = 1

# API (reutilise app config)
KIE_API_KEY = app_config.KIE_API_KEY

# Formats de contenu aleatoires
CONTENT_TYPES = [
    "idee",         # Idee/reflexion inspirante
    "situation",    # Situation de vie + comment en sortir
    "conseil",      # Conseil de sagesse intemporel
]


def init_directories():
    from pathlib import Path
    for d in [SHORTS_DIR, SHORTS_HISTORY_DIR, SHORTS_VIDEOS_DIR,
              SHORTS_IMAGES_DIR, SHORTS_AUDIO_DIR]:
        Path(d).mkdir(parents=True, exist_ok=True)
