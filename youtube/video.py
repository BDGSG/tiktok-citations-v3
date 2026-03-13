"""Assemblage video FFmpeg — format 16:9, clips, fades, pan lent, color grading, YouTube-compatible."""
import logging
from pathlib import Path
from . import config
from app.utils import run_ffmpeg

logger = logging.getLogger("youtube-citations")

# Pan patterns: direction du mouvement lent (dx, dy par frame normalise)
# L'image est scalee a 112% puis crop anime pour simuler un mouvement
_PAN_PATTERNS = [
    ("left_to_right", "t*{margin}/{dur}", "{vmargin}/2"),
    ("right_to_left", "{margin}-t*{margin}/{dur}", "{vmargin}/2"),
    ("top_to_bottom", "{margin}/2", "t*{vmargin}/{dur}"),
    ("bottom_to_top", "{margin}/2", "{vmargin}-t*{vmargin}/{dur}"),
    ("center_static", "{margin}/2", "{vmargin}/2"),  # fallback statique avec scale
]


def _build_clip(
    image_path: str, clip_path: str, index: int, duration: float
) -> str:
    """Cree un clip 16:9 avec pan lent (scale 112% + crop anime) + fade in/out."""
    w = config.VIDEO_WIDTH
    h = config.VIDEO_HEIGHT
    fps = config.VIDEO_FPS
    fade_in = config.TRANSITION_FADE_IN
    fade_out_start = max(0, duration - config.TRANSITION_FADE_OUT)

    # Scale 112% puis crop anime pour simuler mouvement
    scale_factor = 1.12
    sw = int(w * scale_factor)
    sh = int(h * scale_factor)
    margin = sw - w    # marge horizontale pour pan
    vmargin = sh - h   # marge verticale pour pan

    # Selectionner un pattern de pan
    pattern_name, x_tpl, y_tpl = _PAN_PATTERNS[index % len(_PAN_PATTERNS)]
    x_expr = x_tpl.format(margin=margin, vmargin=vmargin, dur=f"{duration:.3f}")
    y_expr = y_tpl.format(margin=margin, vmargin=vmargin, dur=f"{duration:.3f}")

    vf = (
        f"scale={sw}:{sh}:force_original_aspect_ratio=increase,"
        f"crop={sw}:{sh},"
        f"crop={w}:{h}:{x_expr}:{y_expr},"
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
    concat_file = f"{config.YT_CLIPS_DIR}/concat.txt"
    with open(concat_file, "w") as f:
        for p in clip_paths:
            f.write(f"file '{p}'\n")

    cmd = (
        f'ffmpeg -y -f concat -safe 0 -i "{concat_file}" '
        f'-i "{audio_path}" '
        f"-c:v copy -c:a aac -b:a 192k -shortest "
        f'"{output_path}"'
    )
    run_ffmpeg(cmd, timeout=600)
    return output_path


def finalize_video(
    input_path: str, ass_path: str, output_path: str
) -> str:
    """Color grading + sous-titres, compatible YouTube.

    YouTube : H.264 High, niveau 4.1, movflags faststart, 1920x1080.
    """
    ass_escaped = ass_path.replace("\\", "/")
    fonts_escaped = config.FONTS_DIR.replace("\\", "/")

    vf = (
        "colorbalance=rs=-0.02:gs=-0.02:bs=0.04,"
        "eq=contrast=1.10:brightness=-0.02:saturation=0.90,"
        f"ass='{ass_escaped}':fontsdir='{fonts_escaped}'"
    )

    cmd = (
        f'ffmpeg -y -i "{input_path}" '
        f'-vf "{vf}" '
        f"-c:v libx264 -preset slow -crf 20 "
        f"-profile:v high -level 4.1 -pix_fmt yuv420p "
        f"-movflags +faststart "
        f"-c:a copy "
        f'"{output_path}"'
    )
    run_ffmpeg(cmd, timeout=1800)  # plus long pour video YouTube
    return output_path


def assemble_video(
    image_paths: list[str],
    audio_path: str,
    output_path: str,
    audio_duration: float,
    segment_durations: list[float] | None = None,
) -> str:
    """Pipeline : clips individuels -> concat -> raw video 16:9."""
    nb = len(image_paths)
    logger.info(f"Video YT: assembling {nb} images for {audio_duration:.1f}s ({audio_duration/60:.1f}min)")

    if segment_durations and len(segment_durations) == nb:
        durations = segment_durations
        logger.info(f"Video YT: synced durations (min={min(durations):.1f}s max={max(durations):.1f}s)")
    else:
        durations = _compute_even_durations(nb, audio_duration)

    clip_paths = []
    for i, (img_path, dur) in enumerate(zip(image_paths, durations)):
        clip_path = f"{config.YT_CLIPS_DIR}/clip_{i:03d}.mp4"
        _build_clip(img_path, clip_path, i, dur)
        clip_paths.append(clip_path)
        if (i + 1) % 10 == 0:
            logger.info(f"Video YT: {i + 1}/{nb} clips created")

    _concat_clips(clip_paths, audio_path, output_path)

    # Cleanup clips
    for p in clip_paths:
        Path(p).unlink(missing_ok=True)
    Path(f"{config.YT_CLIPS_DIR}/concat.txt").unlink(missing_ok=True)

    logger.info(f"Video YT: assembled -> {output_path}")
    return output_path


def _compute_even_durations(nb_images: int, total_duration: float) -> list[float]:
    """Repartition uniforme avec variation pour rythme naturel."""
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
