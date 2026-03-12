"""Selection et mixage musique ambient."""
import os
import random
import logging
from pathlib import Path
from . import config
from .utils import run_ffmpeg

logger = logging.getLogger("citations-v3")

# Definitions de pads ambients generables via FFmpeg
# Chaque mood = (frequence_basse, freq_quinte, freq_octave, type_bruit, label)
AMBIENT_PRESETS = {
    "contemplative": (65, 98, 130, "pink", "Contemplative Pad"),
    "dark_motivation": (55, 82, 110, "brown", "Dark Motivation Pad"),
    "resilience": (73, 110, 146, "pink", "Resilience Pad"),
    "warrior": (49, 73, 98, "brown", "Warrior Pad"),
    "rebirth": (82, 123, 164, "pink", "Rebirth Pad"),
}


def ensure_music_exists() -> None:
    """Genere des pads ambients avec FFmpeg si le dossier musique est vide.

    Cree 5 fichiers MP3 de 15 min chacun avec des couches de sinus
    harmoniques + bruit filtre pour un fond sonore cinematique.
    """
    Path(config.MUSIC_DIR).mkdir(parents=True, exist_ok=True)
    existing = [
        f for f in os.listdir(config.MUSIC_DIR)
        if f.endswith((".mp3", ".wav", ".ogg", ".m4a"))
        and os.path.isfile(os.path.join(config.MUSIC_DIR, f))
    ]
    if existing:
        return

    logger.info("Music: generating ambient pads (first run)...")

    for mood, (f1, f2, f3, noise_type, label) in AMBIENT_PRESETS.items():
        mood_dir = os.path.join(config.MUSIC_DIR, mood)
        Path(mood_dir).mkdir(parents=True, exist_ok=True)
        output_path = os.path.join(mood_dir, f"ambient_{mood}.mp3")

        if os.path.isfile(output_path):
            continue

        dur = 900  # 15 minutes
        cmd = (
            f'ffmpeg -y '
            f'-f lavfi -i "sine=f={f1}:d={dur}:r=44100" '
            f'-f lavfi -i "sine=f={f2}:d={dur}:r=44100" '
            f'-f lavfi -i "sine=f={f3}:d={dur}:r=44100" '
            f'-f lavfi -i "anoisesrc=d={dur}:c={noise_type}:r=44100:a=0.01" '
            f'-filter_complex "'
            f"[0:a]volume=0.06,afade=t=in:d=5,afade=t=out:st={dur - 8}:d=8[s1];"
            f"[1:a]volume=0.04,afade=t=in:d=8,afade=t=out:st={dur - 8}:d=8[s2];"
            f"[2:a]volume=0.03,afade=t=in:d=10,afade=t=out:st={dur - 8}:d=8[s3];"
            f"[3:a]volume=0.008,lowpass=f=400,afade=t=in:d=3,afade=t=out:st={dur - 5}:d=5[n];"
            f"[s1][s2][s3][n]amix=inputs=4:normalize=0,"
            f"aecho=0.8:0.88:60:0.4,"
            f"lowpass=f=600,"
            f'volume=3.0[out]" '
            f'-map "[out]" -c:a libmp3lame -b:a 128k '
            f'"{output_path}"'
        )
        try:
            run_ffmpeg(cmd, timeout=120)
            logger.info(f"Music: generated {label} -> {output_path}")
        except Exception as e:
            logger.warning(f"Music: failed to generate {mood}: {e}")

    # Fichier generique dans le dossier racine
    generic_path = os.path.join(config.MUSIC_DIR, "ambient_generic.mp3")
    if not os.path.isfile(generic_path):
        dur = 900
        cmd = (
            f'ffmpeg -y '
            f'-f lavfi -i "sine=f=65:d={dur}:r=44100" '
            f'-f lavfi -i "sine=f=98:d={dur}:r=44100" '
            f'-f lavfi -i "anoisesrc=d={dur}:c=pink:r=44100:a=0.008" '
            f'-filter_complex "'
            f"[0:a]volume=0.05,afade=t=in:d=5,afade=t=out:st={dur - 8}:d=8[s1];"
            f"[1:a]volume=0.03,afade=t=in:d=8,afade=t=out:st={dur - 8}:d=8[s2];"
            f"[2:a]volume=0.006,lowpass=f=350,afade=t=in:d=3,afade=t=out:st={dur - 5}:d=5[n];"
            f"[s1][s2][n]amix=inputs=3:normalize=0,"
            f"aecho=0.8:0.88:60:0.4,"
            f"lowpass=f=500,"
            f'volume=2.5[out]" '
            f'-map "[out]" -c:a libmp3lame -b:a 128k '
            f'"{generic_path}"'
        )
        try:
            run_ffmpeg(cmd, timeout=120)
            logger.info(f"Music: generated generic ambient -> {generic_path}")
        except Exception as e:
            logger.warning(f"Music: failed to generate generic: {e}")

    logger.info("Music: ambient pads generation complete")


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
    # Timeout plus long pour videos YouTube (10-20 min)
    timeout = 120 if duration < 300 else 600
    run_ffmpeg(cmd, timeout=timeout)
    logger.info(f"Music: mixed -> {output_path}")
    return output_path
