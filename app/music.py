"""Selection et mixage musique ambient.

Genere des pads cinematiques riches via FFmpeg (aevalsrc + effets)
ou utilise des MP3 manuellement places dans MUSIC_DIR.

Pour de meilleurs resultats, telecharger des pistes ambient royalty-free
depuis Pixabay (https://pixabay.com/music/search/dark%20ambient/)
et les placer dans MUSIC_DIR/ ou MUSIC_DIR/{mood}/.
"""
import os
import random
import logging
from pathlib import Path
from . import config
from .utils import run_ffmpeg

logger = logging.getLogger("citations-v3")

# Presets cinematiques — chaque preset genere un pad ambient riche
# (note_midi, chord_type, tempo_lfo, warmth, label)
# chord_type: "minor" = fondamentale + tierce mineure + quinte
#             "sus" = fondamentale + quarte + quinte (suspendu, ethereal)
#             "power" = fondamentale + quinte (puissant, neutre)
AMBIENT_PRESETS = {
    "contemplative": {
        "freq": 65.41,    # C2
        "chord": "minor",
        "lfo_speed": 0.08,
        "warmth": 400,
        "label": "Contemplative Pad",
    },
    "dark_motivation": {
        "freq": 55.0,     # A1
        "chord": "power",
        "lfo_speed": 0.05,
        "warmth": 300,
        "label": "Dark Motivation Pad",
    },
    "resilience": {
        "freq": 73.42,    # D2
        "chord": "sus",
        "lfo_speed": 0.07,
        "warmth": 450,
        "label": "Resilience Pad",
    },
    "warrior": {
        "freq": 49.0,     # G1
        "chord": "power",
        "lfo_speed": 0.04,
        "warmth": 250,
        "label": "Warrior Pad",
    },
    "rebirth": {
        "freq": 82.41,    # E2
        "chord": "minor",
        "lfo_speed": 0.1,
        "warmth": 500,
        "label": "Rebirth Pad",
    },
}


def _chord_freqs(root: float, chord_type: str) -> list[float]:
    """Retourne les frequences d'un accord a partir de la fondamentale."""
    if chord_type == "minor":
        return [root, root * 1.1892, root * 1.4983]  # root, min3, 5th
    elif chord_type == "sus":
        return [root, root * 1.3348, root * 1.4983]  # root, 4th, 5th
    else:  # power
        return [root, root * 1.4983]  # root, 5th


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
    """Genere des pads ambients cinematiques si aucune musique n'est disponible.

    Si des fichiers MP3/WAV sont deja presents dans MUSIC_DIR (ou sous-dossiers),
    ils sont utilises en priorite. Sinon, genere 5 pads + 1 generique.

    Pour de meilleurs resultats, telecharger des pistes ambient depuis:
    - Pixabay: https://pixabay.com/music/search/dark%20ambient/
    - YouTube Audio Library (dans YouTube Studio)
    et les placer dans MUSIC_DIR/ ou MUSIC_DIR/{mood}/.
    """
    Path(config.MUSIC_DIR).mkdir(parents=True, exist_ok=True)

    if _has_music_files(config.MUSIC_DIR):
        return

    logger.info("Music: generating cinematic ambient pads (first run)...")
    logger.info("Music: TIP — pour une meilleure qualite, placez des MP3 ambient "
                "de Pixabay dans %s", config.MUSIC_DIR)

    for mood, preset in AMBIENT_PRESETS.items():
        mood_dir = os.path.join(config.MUSIC_DIR, mood)
        Path(mood_dir).mkdir(parents=True, exist_ok=True)
        output_path = os.path.join(mood_dir, f"ambient_{mood}.mp3")

        if os.path.isfile(output_path):
            continue

        _generate_cinematic_pad(output_path, preset)

    # Fichier generique
    generic_path = os.path.join(config.MUSIC_DIR, "ambient_generic.mp3")
    if not os.path.isfile(generic_path):
        _generate_cinematic_pad(generic_path, {
            "freq": 65.41,
            "chord": "minor",
            "lfo_speed": 0.06,
            "warmth": 380,
            "label": "Generic Cinematic Pad",
        })

    logger.info("Music: ambient pads generation complete")


def _generate_cinematic_pad(output_path: str, preset: dict) -> None:
    """Genere un pad ambient cinematique riche avec FFmpeg.

    Utilise aevalsrc pour des formes d'onde complexes (triangle filtree),
    avec tremolo LFO, chorus multi-voix, reverb multi-tap, et compression.
    """
    dur = 900  # 15 minutes
    root = preset["freq"]
    freqs = _chord_freqs(root, preset["chord"])
    lfo = preset["lfo_speed"]
    warmth = preset["warmth"]
    label = preset["label"]

    # Construire les inputs : pour chaque note de l'accord, 2 oscillateurs detunes
    inputs = []
    filter_parts = []
    mix_labels = []
    idx = 0

    for note_i, freq in enumerate(freqs):
        # Detune +3 cents et -3 cents pour chorus naturel
        f_up = round(freq * (2 ** (3 / 1200)), 4)
        f_down = round(freq * (2 ** (-3 / 1200)), 4)

        for f in [freq, f_up, f_down]:
            # aevalsrc avec forme d'onde triangle (plus douce que sine, plus riche en harmoniques)
            # triangle(t) = 2*abs(2*(f*t - floor(f*t + 0.5))) - 1
            expr = f"2*abs(2*({f}*t-floor({f}*t+0.5)))-1"
            inputs.append(f'-f lavfi -i "aevalsrc=\'{expr}\':d={dur}:s=44100"')

            # Volume decroissant par note (fondamentale plus forte)
            base_vol = 0.04 - note_i * 0.008
            vol = max(base_vol, 0.012)
            fade_in = 4 + idx * 1.5
            lbl = f"s{idx}"

            # Tremolo LFO pour mouvement organique (vitesse legerement differente par voix)
            lfo_this = round(lfo + idx * 0.003, 4)
            filter_parts.append(
                f"[{idx}:a]volume={vol},"
                f"afade=t=in:d={fade_in},"
                f"afade=t=out:st={dur - 10}:d=10,"
                f"tremolo=f={lfo_this}:d=0.3[{lbl}]"
            )
            mix_labels.append(f"[{lbl}]")
            idx += 1

    # Ajouter bruit rose filtre pour texture
    noise_idx = idx
    inputs.append(f'-f lavfi -i "anoisesrc=d={dur}:c=pink:r=44100:a=0.008"')
    filter_parts.append(
        f"[{noise_idx}:a]"
        f"lowpass=f={warmth},"
        f"highpass=f=30,"
        f"afade=t=in:d=3,"
        f"afade=t=out:st={dur - 6}:d=6,"
        f"tremolo=f={lfo * 0.5}:d=0.2[noise]"
    )
    mix_labels.append("[noise]")

    n_inputs = len(mix_labels)

    # Mix → chorus → reverb multi-tap → EQ → compression
    filter_chain = (
        ";".join(filter_parts)
        + f";{''.join(mix_labels)}amix=inputs={n_inputs}:normalize=0,"
        # Chorus FFmpeg pour epaisseur spatiale
        f"chorus=0.6:0.9:50|60|70:0.4|0.32|0.28:0.25|0.3|0.35:2|1.8|2.3,"
        # Reverb multi-tap (simule une grande salle)
        f"aecho=0.8:0.6:60|120|200|350:0.25|0.18|0.12|0.08,"
        # EQ : couper les aigus, garder la chaleur
        f"lowpass=f={warmth + 100},"
        f"highpass=f=25,"
        # Compression douce pour niveau constant
        f"acompressor=threshold=-20dB:ratio=3:attack=300:release=2000,"
        # Volume final
        f"volume=3.0[out]"
    )

    cmd = (
        f"ffmpeg -y "
        + " ".join(inputs)
        + f" -filter_complex \"{filter_chain}\" "
        + f'-map "[out]" -c:a libmp3lame -b:a 192k '
        + f'"{output_path}"'
    )

    try:
        run_ffmpeg(cmd, timeout=300)
        logger.info(f"Music: generated {label} -> {output_path}")
    except Exception as e:
        logger.warning(f"Music: failed to generate {label}: {e}")
        # Fallback ultra-simple en cas d'echec
        _generate_simple_fallback(output_path, root, dur)


def _generate_simple_fallback(output_path: str, freq: float, dur: int) -> None:
    """Fallback simple si la generation complexe echoue."""
    cmd = (
        f'ffmpeg -y '
        f'-f lavfi -i "sine=f={freq}:d={dur}:r=44100" '
        f'-f lavfi -i "sine=f={freq * 1.499}:d={dur}:r=44100" '
        f'-f lavfi -i "anoisesrc=d={dur}:c=pink:r=44100:a=0.005" '
        f'-filter_complex "'
        f"[0:a]volume=0.04,afade=t=in:d=5,afade=t=out:st={dur-8}:d=8[a];"
        f"[1:a]volume=0.02,afade=t=in:d=8,afade=t=out:st={dur-8}:d=8[b];"
        f"[2:a]lowpass=f=300,highpass=f=30,afade=t=in:d=3,afade=t=out:st={dur-5}:d=5[n];"
        f"[a][b][n]amix=inputs=3:normalize=0,"
        f"aecho=0.8:0.7:60|120:0.3|0.2,"
        f"lowpass=f=400,volume=3.0[out]\" "
        f'-map "[out]" -c:a libmp3lame -b:a 192k '
        f'"{output_path}"'
    )
    try:
        run_ffmpeg(cmd, timeout=180)
        logger.info(f"Music: generated fallback pad -> {output_path}")
    except Exception as e:
        logger.warning(f"Music: fallback generation also failed: {e}")


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

    # 2. Fallback : tous les sous-dossiers
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
    """Mixe la musique de fond avec la video.

    - Voix-off : 100% volume
    - Musique : volume configurable (12% par defaut pour YouTube)
    - Fade in/out pour transition douce
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
    timeout = 120 if duration < 300 else 600
    run_ffmpeg(cmd, timeout=timeout)
    logger.info(f"Music: mixed -> {output_path}")
    return output_path
