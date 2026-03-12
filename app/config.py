"""Configuration centralisee - env vars, constantes, chemins."""
import os
from pathlib import Path
from datetime import datetime
import pytz

# -- Chemins --
BASE_PATH = os.getenv("BASE_PATH", "/data/tiktok_citations_v3")
AUDIO_DIR = f"{BASE_PATH}/audio"
IMAGES_DIR = f"{BASE_PATH}/images"
VIDEOS_DIR = f"{BASE_PATH}/videos"
CLIPS_DIR = f"{BASE_PATH}/clips"
MUSIC_DIR = f"{BASE_PATH}/music"
SFX_DIR = f"{BASE_PATH}/sfx"
FONTS_DIR = f"{BASE_PATH}/fonts"
HISTORY_DIR = f"{BASE_PATH}/history"
TOKEN_PATH = f"{BASE_PATH}/tiktok_token.json"

# -- Video --
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30
VIDEO_CRF = 18
NB_IMAGES = 18
IMAGE_ASPECT_RATIO = "9:16"
TRANSITION_FADE_IN = 0.6
TRANSITION_FADE_OUT = 0.5

# -- TTS --
TTS_VOICE = "fr-FR-Neural2-B"
TTS_SPEED = 0.88
TTS_PITCH = -1.5
TTS_SAMPLE_RATE = 24000
TTS_MAX_SSML_BYTES = 4500

# -- Sous-titres --
SUBTITLE_FONT = "Montserrat ExtraBold"
SUBTITLE_FONT_SIZE = 85
SUBTITLE_HOOK_SIZE = 100
SUBTITLE_CTA_SIZE = 64
SUBTITLE_HL_COLOR = "&H0000D4FF&"  # Dore BGR
SUBTITLE_NORMAL_COLOR = "&H80FFFFFF&"  # Blanc semi-transparent
SUBTITLE_BG_COLOR = "&HA0000000&"  # Noir semi-transparent
SUBTITLE_WORDS_PER_GROUP = 3
SUBTITLE_MARGIN_V = 200

# -- Musique --
MUSIC_VOLUME = 0.15
MUSIC_FADE_IN = 2.0
MUSIC_FADE_OUT = 3.0

# -- API Keys (Coolify env vars) --
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GCP_API_KEY = os.getenv("GCP_API_KEY", "")
KIE_API_KEY = os.getenv("KIE_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "7445971784")
TIKTOK_CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY", "")
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET", "")
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID", "1Nsft6-Rr9TwDejUrFvnBSvlm7Dc32GEQWm2wJ-4-hvs")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")

# -- Scheduler --
SCHEDULE_HOUR = int(os.getenv("SCHEDULE_HOUR", "17"))
SCHEDULE_MINUTE = int(os.getenv("SCHEDULE_MINUTE", "0"))
TZ = os.getenv("TZ", "Europe/Paris")

# -- Claude --
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
CLAUDE_MAX_TOKENS = 8192
SCRIPT_MIN_WORDS = 400
SCRIPT_MAX_WORDS = 700
MIN_IMAGE_PROMPTS = 15


def init_directories():
    """Cree tous les sous-dossiers necessaires + copie font si besoin."""
    import shutil
    for d in [AUDIO_DIR, IMAGES_DIR, VIDEOS_DIR, CLIPS_DIR,
              MUSIC_DIR, SFX_DIR, FONTS_DIR, HISTORY_DIR]:
        Path(d).mkdir(parents=True, exist_ok=True)

    # Copier la font embarquee vers le volume persistant
    font_src = Path("/app/Montserrat-ExtraBold.ttf")
    font_dst = Path(FONTS_DIR) / "Montserrat-ExtraBold.ttf"
    if font_src.exists() and not font_dst.exists():
        shutil.copy2(font_src, font_dst)


def get_date_str() -> str:
    """Date du jour au format YYYY-MM-DD (timezone Paris)."""
    return datetime.now(pytz.timezone(TZ)).strftime("%Y-%m-%d")


def get_datetime_str() -> str:
    """Datetime au format ISO pour les logs."""
    return datetime.now(pytz.timezone(TZ)).isoformat()
