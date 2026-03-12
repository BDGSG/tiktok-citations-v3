"""Configuration YouTube — env vars, constantes, chemins."""
import os
from pathlib import Path
from datetime import datetime
import pytz

# -- Chemins --
BASE_PATH = os.getenv("BASE_PATH", "/data/tiktok_citations_v3")
YT_BASE = f"{BASE_PATH}/youtube"
YT_AUDIO_DIR = f"{YT_BASE}/audio"
YT_IMAGES_DIR = f"{YT_BASE}/images"
YT_VIDEOS_DIR = f"{YT_BASE}/videos"
YT_CLIPS_DIR = f"{YT_BASE}/clips"
YT_THUMBNAILS_DIR = f"{YT_BASE}/thumbnails"
YT_HISTORY_DIR = f"{YT_BASE}/history"
MUSIC_DIR = f"{BASE_PATH}/music"
SFX_DIR = f"{BASE_PATH}/sfx"
FONTS_DIR = f"{BASE_PATH}/fonts"
LOGO_PATH = f"{YT_BASE}/logo.png"

# -- Video 16:9 --
VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
VIDEO_FPS = 30
VIDEO_CRF = 18
NB_IMAGES = 50  # default, ajuste par Claude selon la longueur
IMAGE_ASPECT_RATIO = "16:9"
TRANSITION_FADE_IN = 0.8
TRANSITION_FADE_OUT = 0.6

# -- Thumbnail --
THUMB_WIDTH = 1280
THUMB_HEIGHT = 720

# -- TTS (reutilise les memes params) --
TTS_VOICE = "fr-FR-Neural2-B"
TTS_SPEED = 0.88
TTS_PITCH = -1.5
TTS_SAMPLE_RATE = 24000
TTS_MAX_SSML_BYTES = 4500

# -- Sous-titres 16:9 (plus petits, en bas) --
SUBTITLE_FONT = "Montserrat ExtraBold"
SUBTITLE_FONT_SIZE = 52
SUBTITLE_HOOK_SIZE = 68
SUBTITLE_CTA_SIZE = 44
SUBTITLE_HL_COLOR = "&H0000D4FF&"  # Dore BGR
SUBTITLE_NORMAL_COLOR = "&H80FFFFFF&"  # Blanc semi-transparent
SUBTITLE_BG_COLOR = "&HA0000000&"  # Noir semi-transparent
SUBTITLE_WORDS_PER_GROUP = 4
SUBTITLE_MARGIN_V = 80

# -- Musique --
MUSIC_VOLUME = 0.12  # un peu plus bas pour YouTube (video longue)
MUSIC_FADE_IN = 3.0
MUSIC_FADE_OUT = 5.0

# -- API Keys (reutilise les memes) --
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GCP_API_KEY = os.getenv("GCP_API_KEY", "")
KIE_API_KEY = os.getenv("KIE_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "7445971784")
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID_YT", os.getenv("GOOGLE_SHEETS_ID", ""))
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")

# -- YouTube OAuth2 --
YT_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID", "870842170043-dl0p16c970q7v9qlo2fg3moi1t5j5fa6.apps.googleusercontent.com")
YT_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "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")
YT_TOKEN_PATH = f"{YT_BASE}/youtube_token.json"

# -- Scheduler --
SCHEDULE_HOUR = int(os.getenv("YT_SCHEDULE_HOUR", "14"))
SCHEDULE_MINUTE = int(os.getenv("YT_SCHEDULE_MINUTE", "0"))
TZ = os.getenv("TZ", "Europe/Paris")

# -- Claude --
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
CLAUDE_MAX_TOKENS = 16384  # plus de tokens pour script long
SCRIPT_MIN_WORDS = 1500
SCRIPT_MAX_WORDS = 3000
MIN_IMAGE_PROMPTS = 35


def init_directories():
    """Cree tous les sous-dossiers YouTube + copie font si besoin."""
    import shutil
    for d in [YT_AUDIO_DIR, YT_IMAGES_DIR, YT_VIDEOS_DIR, YT_CLIPS_DIR,
              YT_THUMBNAILS_DIR, YT_HISTORY_DIR, MUSIC_DIR, SFX_DIR, FONTS_DIR]:
        Path(d).mkdir(parents=True, exist_ok=True)

    # Copier la font embarquee vers le volume persistant
    font_src = Path("/app/Montserrat-ExtraBold.ttf")
    font_dst = Path(FONTS_DIR) / "Montserrat-ExtraBold.ttf"
    if font_src.exists() and not font_dst.exists():
        shutil.copy2(font_src, font_dst)


def get_date_str() -> str:
    return datetime.now(pytz.timezone(TZ)).strftime("%Y-%m-%d")


def get_datetime_str() -> str:
    return datetime.now(pytz.timezone(TZ)).isoformat()
