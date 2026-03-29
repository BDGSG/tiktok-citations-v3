"""Selection et mixage musique ambient.

Genere 5 pads ambient distincts via FFmpeg (sine waves + harmoniques + effets).
Chaque mood a une signature sonore unique.
"""
import os
import random
import logging
from pathlib import Path
from . import config
from .utils import run_ffmpeg

logger = logging.getLogger("citations-v3")

# Each preset: base_freq, second_freq, third_freq, noise_amount, lowpass_cutoff
# These create distinctly different sounds
AMBIENT_PRESETS = {
    "contemplative": {
        "f1": 65.41,   # C2
        "f2": 77.78,   # Eb2 (minor third)
        "f3": 98.0,    # G2 (fifth)
        "noise_vol": 0.006,
        "lp": 400,
        "echo": "60|120:0.3|0.2",
        "label": "Contemplative — soft minor pad",
    },
    "dark_motivation": {
        "f1": 55.0,    # A1
        "f2": 82.41,   # E2 (fifth, power)
        "f3": 110.0,   # A2 (octave)
        "noise_vol": 0.008,
        "lp": 300,
        "echo": "80|160|300:0.25|0.15|0.08",
        "label": "Dark Motivation — deep power drone",
    },
    "resilience": {
        "f1": 73.42,   # D2
        "f2": 97.99,   # G2 (fourth)
        "f3": 110.0,   # A2 (fifth)
        "noise_vol": 0.005,
        "lp": 450,
        "echo": "50|100:0.25|0.15",
        "label": "Resilience — suspended fourth pad",
    },
    "warrior": {
        "f1": 49.0,    # G1 (deep)
        "f2": 73.42,   # D2 (fifth)
        "f3": 55.0,    # A1
        "noise_vol": 0.010,
        "lp": 250,
        "echo": "100|200|400:0.3|0.2|0.1",
        "label": "Warrior — aggressive low drone",
    },
    "rebirth": {
        "f1": 82.41,   # E2
        "f2": 103.83,  # Ab2 (minor third)
        "f3": 123.47,  # B2 (fifth)
        "noise_vol": 0.004,
        "lp": 500,
        "echo": "40|80:0.2|0.15",
        "label": "Rebirth — bright minor shimmer",
    },
}


def _has_music_files(directory: str) -> bool:
    """Verifie si un dossier contient des fichiers audio (recursif 1 niveau)."""
    if not os.path.isdir(directory):
        return False
    for entry in os.listdir(directory):
        full_path = os.path.join(directory, entry)
        if os.path.isfile(full_path) and entry.endswith((".mp3", ".wav", ".ogg", ".m4a")):
            return True
        if os.path.isdir(full_path):
            for sub in os.listdir(full_path):
                if sub.endswith((".mp3", ".wav", ".ogg", ".m4a")):
                    return True
    return False


def ensure_music_exists() -> None:
    """Genere des pads ambient si aucune musique n'est disponible."""
    Path(config.MUSIC_DIR).mkdir(parents=True, exist_ok=True)

    if _has_music_files(config.MUSIC_DIR):
        return

    logger.info("Music: generating ambient pads (first run)...")

    for mood, preset in AMBIENT_PRESETS.items():
        mood_dir = os.path.join(config.MUSIC_DIR, mood)
        Path(mood_dir).mkdir(parents=True, exist_ok=True)
        output_path = os.path.join(mood_dir, f"ambient_{mood}.mp3")

        if os.path.isfile(output_path):
            continue

        _generate_pad(output_path, preset)

    # Generic fallback
    generic_path = os.path.join(config.MUSIC_DIR, "ambient_generic.mp3")
    if not os.path.isfile(generic_path):
        _generate_pad(generic_path, AMBIENT_PRESETS["contemplative"])

    logger.info("Music: ambient pad generation complete")


def _generate_pad(output_path: str, preset: dict) -> None:
    """Genere un pad ambient via FFmpeg — simple 3-sine + pink noise approach."""
    dur = 900  # 15 minutes
    f1 = preset["f1"]
    f2 = preset["f2"]
    f3 = preset["f3"]
    noise_vol = preset["noise_vol"]
    lp = preset["lp"]
    echo_params = preset["echo"]
    label = preset["label"]

    cmd = (
        f'ffmpeg -y '
        f'-f lavfi -i "sine=f={f1}:d={dur}:r=44100" '
        f'-f lavfi -i "sine=f={f2}:d={dur}:r=44100" '
        f'-f lavfi -i "sine=f={f3}:d={dur}:r=44100" '
        f'-f lavfi -i "anoisesrc=d={dur}:c=pink:r=44100:a={noise_vol}" '
        f'-filter_complex "'
        f"[0:a]volume=0.04,afade=t=in:d=5,afade=t=out:st={dur-8}:d=8[a];"
        f"[1:a]volume=0.025,afade=t=in:d=7,afade=t=out:st={dur-8}:d=8[b];"
        f"[2:a]volume=0.015,afade=t=in:d=10,afade=t=out:st={dur-8}:d=8[c];"
        f"[3:a]lowpass=f={lp},highpass=f=25,afade=t=in:d=3,afade=t=out:st={dur-5}:d=5[n];"
        f"[a][b][c][n]amix=inputs=4:normalize=0,"
        f"aecho=0.8:0.6:{echo_params},"
        f"lowpass=f={lp + 100},"
        f"highpass=f=25,"
        f"volume=3.0[out]\" "
        f'-map "[out]" -c:a libmp3lame -b:a 192k '
        f'"{output_path}"'
    )

    try:
        run_ffmpeg(cmd, timeout=300)
        logger.info(f"Music: generated {label} -> {output_path}")
    except Exception as e:
        logger.warning(f"Music: failed to generate {label}: {e}")
        # Ultra-simple fallback
        _generate_ultra_simple(output_path, f1, dur)


def _generate_ultra_simple(output_path: str, freq: float, dur: int) -> None:
    """Fallback le plus simple possible."""
    cmd = (
        f'ffmpeg -y '
        f'-f lavfi -i "sine=f={freq}:d={dur}:r=44100" '
        f'-af "volume=0.03,afade=t=in:d=5,afade=t=out:st={dur-8}:d=8,lowpass=f=300" '
        f'-c:a libmp3lame -b:a 128k '
        f'"{output_path}"'
    )
    try:
        run_ffmpeg(cmd, timeout=120)
        logger.info(f"Music: ultra-simple fallback -> {output_path}")
    except Exception as e:
        logger.warning(f"Music: ultra-simple also failed: {e}")


def select_music(mood: str | None, duration: float) -> str | None:
    """Selectionne un fichier musique au hasard selon le mood."""
    candidates = []

    if mood:
        mood_dir = f"{config.MUSIC_DIR}/{mood}"
        if os.path.isdir(mood_dir):
            candidates = [
                os.path.join(mood_dir, f)
                for f in os.listdir(mood_dir)
                if f.endswith((".mp3", ".wav", ".ogg", ".m4a"))
            ]

    if not candidates:
        if os.path.isdir(config.MUSIC_DIR):
            for entry in os.listdir(config.MUSIC_DIR):
                full = os.path.join(config.MUSIC_DIR, entry)
                if os.path.isfile(full) and entry.endswith((".mp3", ".wav", ".ogg", ".m4a")):
                    candidates.append(full)
                elif os.path.isdir(full):
                    for sub in os.listdir(full):
                        sub_path = os.path.join(full, sub)
                        if sub.endswith((".mp3", ".wav", ".ogg", ".m4a")) and os.path.isfile(sub_path):
                            candidates.append(sub_path)

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
    """Mixe la musique de fond avec la video."""
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
    timeout = 120 if duration < 300 else 600
    run_ffmpeg(cmd, timeout=timeout)
    logger.info(f"Music: mixed -> {output_path}")
    return output_path
