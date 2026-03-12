"""Assemblage video FFmpeg — clips individuels, fades, color grading, TikTok-compatible."""
import math
import logging
from pathlib import Path
from . import config
from .utils import run_ffmpeg

logger = logging.getLogger("citations-v3")


def _build_clip(
    image_path: str, clip_path: str, index: int, duration: float
) -> str:
    """Cree un clip individuel avec scale + crop + fade in/out."""
    w = config.VIDEO_WIDTH
    h = config.VIDEO_HEIGHT
    fps = config.VIDEO_FPS
    fade_in = config.TRANSITION_FADE_IN
    fade_out_start = max(0, duration - config.TRANSITION_FADE_OUT)

    vf = (
        f"scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h},"
        f"setsar=1,format=yuv420p,"
        f"fade=t=in:st=0:d={fade_in},"
        f"fade=t=out:st={fade_out_start}:d={config.TRANSITION_FADE_OUT}"
    )

    cmd = (
        f'ffmpeg -y -loop 1 -t {duration:.3f} -i "{image_path}" '
        f'-vf "{vf}" '
        f"-c:v libx264 -preset fast -crf 20 -r {fps} -an "
        f'"{clip_path}"'
    )
    run_ffmpeg(cmd, timeout=120)
    return clip_path


def _concat_clips(clip_paths: list[str], audio_path: str, output_path: str) -> str:
    """Concatene les clips et ajoute l'audio."""
    concat_file = f"{config.CLIPS_DIR}/concat.txt"
    with open(concat_file, "w") as f:
        for p in clip_paths:
            f.write(f"file '{p}'\n")

    cmd = (
        f'ffmpeg -y -f concat -safe 0 -i "{concat_file}" '
        f'-i "{audio_path}" '
        f"-c:v copy -c:a aac -b:a 192k -shortest "
        f'"{output_path}"'
    )
    run_ffmpeg(cmd, timeout=300)
    return output_path


def finalize_video(
    input_path: str, ass_path: str, output_path: str
) -> str:
    """Color grading + sous-titres en UNE SEULE passe, compatible TikTok.

    Combine : teal/orange color grading + ASS subtitles + profile H.264 High + movflags faststart.
    """
    ass_escaped = ass_path.replace("\\", "/")
    fonts_escaped = config.FONTS_DIR.replace("\\", "/")

    vf = (
        "colorbalance=rs=-0.02:gs=-0.02:bs=0.04,"
        "eq=contrast=1.12:brightness=-0.03:saturation=0.88,"
        f"ass='{ass_escaped}':fontsdir='{fonts_escaped}'"
    )

    cmd = (
        f'ffmpeg -y -i "{input_path}" '
        f'-vf "{vf}" '
        f"-c:v libx264 -preset fast -crf 23 "
        f"-profile:v high -level 4.1 -pix_fmt yuv420p "
        f"-movflags +faststart "
        f"-c:a copy "
        f'"{output_path}"'
    )
    run_ffmpeg(cmd, timeout=600)
    return output_path


def assemble_video(
    image_paths: list[str],
    audio_path: str,
    output_path: str,
    audio_duration: float,
    segment_durations: list[float] | None = None,
) -> str:
    """Pipeline complet : clips individuels -> concat -> raw video.

    Si segment_durations est fourni, utilise ces durees (sync narration).
    Sinon, distribue uniformement.
    """
    nb = len(image_paths)
    logger.info(f"Video: assembling {nb} images for {audio_duration:.1f}s")

    # 1. Durees des segments
    if segment_durations and len(segment_durations) == nb:
        durations = segment_durations
        logger.info(f"Video: using narration-synced durations (min={min(durations):.1f}s max={max(durations):.1f}s)")
    else:
        durations = _compute_even_durations(nb, audio_duration)

    # 2. Creer les clips individuels
    clip_paths = []
    for i, (img_path, dur) in enumerate(zip(image_paths, durations)):
        clip_path = f"{config.CLIPS_DIR}/clip_{i:02d}.mp4"
        _build_clip(img_path, clip_path, i, dur)
        clip_paths.append(clip_path)
        if (i + 1) % 5 == 0:
            logger.info(f"Video: {i + 1}/{nb} clips created")

    # 3. Concat + audio
    _concat_clips(clip_paths, audio_path, output_path)

    # 4. Cleanup clips
    for p in clip_paths:
        Path(p).unlink(missing_ok=True)
    Path(f"{config.CLIPS_DIR}/concat.txt").unlink(missing_ok=True)

    logger.info(f"Video: assembled -> {output_path}")
    return output_path


def _compute_even_durations(nb_images: int, total_duration: float) -> list[float]:
    """Fallback : repartition uniforme avec legere variation."""
    buffer = 0.5
    available = total_duration + buffer
    base = available / nb_images
    durations = []
    for i in range(nb_images):
        if i == 0 or i == nb_images - 1:
            durations.append(base * 1.15)
        elif i == nb_images // 2:
            durations.append(base * 1.1)
        else:
            durations.append(base * 0.95)
    total = sum(durations)
    return [d * available / total for d in durations]
