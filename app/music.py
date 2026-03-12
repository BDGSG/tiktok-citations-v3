"""Selection et mixage musique ambient."""
import os
import random
import logging
from pathlib import Path
from . import config
from .utils import run_ffmpeg

logger = logging.getLogger("citations-v3")


def select_music(mood: str | None, duration: float) -> str | None:
    """Selectionne un fichier musique au hasard selon le mood.

    Cherche d'abord dans MUSIC_DIR/{mood}/, puis fallback MUSIC_DIR/.
    Retourne None si aucune musique disponible.
    """
    candidates = []

    # 1. Dossier specifique au mood
    if mood:
        mood_dir = f"{config.MUSIC_DIR}/{mood}"
        if os.path.isdir(mood_dir):
            candidates = [
                os.path.join(mood_dir, f)
                for f in os.listdir(mood_dir)
                if f.endswith((".mp3", ".wav", ".ogg", ".m4a"))
            ]

    # 2. Fallback : dossier racine musique
    if not candidates:
        if os.path.isdir(config.MUSIC_DIR):
            candidates = [
                os.path.join(config.MUSIC_DIR, f)
                for f in os.listdir(config.MUSIC_DIR)
                if f.endswith((".mp3", ".wav", ".ogg", ".m4a"))
                and os.path.isfile(os.path.join(config.MUSIC_DIR, f))
            ]

    if not candidates:
        logger.warning("No background music found")
        return None

    selected = random.choice(candidates)
    logger.info(f"Music: selected {Path(selected).name}")
    return selected


def mix_music(
    video_path: str,
    music_path: str | None,
    output_path: str,
    duration: float,
) -> str:
    """Mixe la musique de fond avec la video.

    - Voix-off : 100% volume
    - Musique : 15% volume, fade in 2s, fade out 3s
    - Si pas de musique, copie la video telle quelle.
    """
    if not music_path or not os.path.isfile(music_path):
        logger.info("Music: no music, copying video as-is")
        import shutil
        shutil.copy2(video_path, output_path)
        return output_path

    fade_out_start = max(0, duration - config.MUSIC_FADE_OUT)

    cmd = (
        f'ffmpeg -y -i "{video_path}" -i "{music_path}" '
        f'-filter_complex "'
        f"[0:a]volume=1.0[voice];"
        f"[1:a]volume={config.MUSIC_VOLUME},"
        f"afade=t=in:d={config.MUSIC_FADE_IN},"
        f"afade=t=out:st={fade_out_start:.1f}:d={config.MUSIC_FADE_OUT}[music];"
        f'[voice][music]amix=inputs=2:duration=first[aout]" '
        f'-map 0:v -map "[aout]" -c:v copy -c:a aac -b:a 128k '
        f'-movflags +faststart -shortest '
        f'"{output_path}"'
    )
    run_ffmpeg(cmd, timeout=120)
    logger.info(f"Music: mixed -> {output_path}")
    return output_path
