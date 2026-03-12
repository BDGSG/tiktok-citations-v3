"""Selection et mixage musique ambient."""
import os
import random
import logging
from pathlib import Path
from . import config
from .utils import run_ffmpeg

logger = logging.getLogger("citations-v3")

# Presets ambients riches — 6 oscillateurs detunes + bruit filtre + reverb
# (fondamentale, quinte, octave, detune_cents, noise_type, noise_vol, label)
AMBIENT_PRESETS = {
    "contemplative": (65, 98, 130, 3, "pink", 0.006, "Contemplative Pad"),
    "dark_motivation": (55, 82, 110, 5, "brown", 0.008, "Dark Motivation Pad"),
    "resilience": (73, 110, 146, 4, "pink", 0.005, "Resilience Pad"),
    "warrior": (49, 73, 98, 6, "brown", 0.010, "Warrior Pad"),
    "rebirth": (82, 123, 164, 3, "pink", 0.005, "Rebirth Pad"),
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

    for mood, (f1, f2, f3, detune, noise_type, noise_vol, label) in AMBIENT_PRESETS.items():
        mood_dir = os.path.join(config.MUSIC_DIR, mood)
        Path(mood_dir).mkdir(parents=True, exist_ok=True)
        output_path = os.path.join(mood_dir, f"ambient_{mood}.mp3")

        if os.path.isfile(output_path):
            continue

        dur = 900  # 15 minutes
        # Detune: cree un chorus naturel (oscillateurs legerement desaccordes)
        f1d = round(f1 * (2 ** (detune / 1200)), 2)
        f2d = round(f2 * (2 ** (detune / 1200)), 2)
        f3d = round(f3 * (2 ** (-detune / 1200)), 2)

        cmd = (
            f'ffmpeg -y '
            # 6 oscillateurs : 3 fondamentaux + 3 detunes (chorus)
            f'-f lavfi -i "sine=f={f1}:d={dur}:r=44100" '
            f'-f lavfi -i "sine=f={f1d}:d={dur}:r=44100" '
            f'-f lavfi -i "sine=f={f2}:d={dur}:r=44100" '
            f'-f lavfi -i "sine=f={f2d}:d={dur}:r=44100" '
            f'-f lavfi -i "sine=f={f3}:d={dur}:r=44100" '
            f'-f lavfi -i "sine=f={f3d}:d={dur}:r=44100" '
            # Bruit filtre
            f'-f lavfi -i "anoisesrc=d={dur}:c={noise_type}:r=44100:a={noise_vol}" '
            f'-filter_complex "'
            # Fondamentale + detune -> chorus warm
            f"[0:a]volume=0.04,afade=t=in:d=5,afade=t=out:st={dur - 8}:d=8[s1];"
            f"[1:a]volume=0.035,afade=t=in:d=6,afade=t=out:st={dur - 8}:d=8[s1d];"
            # Quinte + detune
            f"[2:a]volume=0.03,afade=t=in:d=8,afade=t=out:st={dur - 8}:d=8[s2];"
            f"[3:a]volume=0.025,afade=t=in:d=9,afade=t=out:st={dur - 8}:d=8[s2d];"
            # Octave + detune
            f"[4:a]volume=0.02,afade=t=in:d=10,afade=t=out:st={dur - 8}:d=8[s3];"
            f"[5:a]volume=0.018,afade=t=in:d=11,afade=t=out:st={dur - 8}:d=8[s3d];"
            # Bruit filtre passe-bas
            f"[6:a]lowpass=f=300,highpass=f=40,afade=t=in:d=3,afade=t=out:st={dur - 5}:d=5[n];"
            # Mix 7 sources
            f"[s1][s1d][s2][s2d][s3][s3d][n]amix=inputs=7:normalize=0,"
            # Reverb (aecho multi-tap pour espace)
            f"aecho=0.8:0.7:40|80|120:0.3|0.2|0.15,"
            # Filtre passe-bas doux pour chaleur
            f"lowpass=f=500,highpass=f=30,"
            f"acompressor=threshold=-25dB:ratio=4:attack=200:release=1000,"
            f'volume=3.5[out]" '
            f'-map "[out]" -c:a libmp3lame -b:a 192k '
            f'"{output_path}"'
        )
        try:
            run_ffmpeg(cmd, timeout=180)
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
            f'-f lavfi -i "sine=f=65.11:d={dur}:r=44100" '
            f'-f lavfi -i "sine=f=98:d={dur}:r=44100" '
            f'-f lavfi -i "sine=f=130:d={dur}:r=44100" '
            f'-f lavfi -i "anoisesrc=d={dur}:c=pink:r=44100:a=0.005" '
            f'-filter_complex "'
            f"[0:a]volume=0.04,afade=t=in:d=5,afade=t=out:st={dur - 8}:d=8[s1];"
            f"[1:a]volume=0.035,afade=t=in:d=6,afade=t=out:st={dur - 8}:d=8[s1d];"
            f"[2:a]volume=0.025,afade=t=in:d=8,afade=t=out:st={dur - 8}:d=8[s2];"
            f"[3:a]volume=0.018,afade=t=in:d=10,afade=t=out:st={dur - 8}:d=8[s3];"
            f"[4:a]lowpass=f=300,highpass=f=40,afade=t=in:d=3,afade=t=out:st={dur - 5}:d=5[n];"
            f"[s1][s1d][s2][s3][n]amix=inputs=5:normalize=0,"
            f"aecho=0.8:0.7:40|80|120:0.3|0.2|0.15,"
            f"lowpass=f=450,highpass=f=30,"
            f"acompressor=threshold=-25dB:ratio=4:attack=200:release=1000,"
            f'volume=3.0[out]" '
            f'-map "[out]" -c:a libmp3lame -b:a 192k '
            f'"{generic_path}"'
        )
        try:
            run_ffmpeg(cmd, timeout=180)
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
