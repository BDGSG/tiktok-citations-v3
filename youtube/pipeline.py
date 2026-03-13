"""Orchestrateur YouTube — coordonne tous les modules pour video longue 10-20 min."""
import time
import asyncio
import logging
from . import config
from . import content as content_mod
from . import images as images_mod
from . import video as video_mod
from . import subtitles as subtitles_mod
from . import banner as banner_mod
from . import publish as publish_mod
from app import tts as tts_mod
from app import music as music_mod
from app.utils import clean_filename

logger = logging.getLogger("youtube-citations")

# Etat global pour suivi
last_run_status: str = "never"
last_run_time: str = ""
last_run_error: str = ""


def _calc_image_durations(
    nb_images: int,
    word_timings: list[dict],
    total_words: int,
    total_duration: float,
) -> list[float]:
    """Calcule la duree de chaque image basee sur les word timings TTS."""
    if not word_timings or total_words < nb_images:
        return None

    time_map = {}
    for tp in word_timings:
        time_map[tp["index"]] = tp["time"]

    def _nearest_time(word_idx: int) -> float:
        if word_idx in time_map:
            return time_map[word_idx]
        best_idx = min(time_map.keys(), key=lambda k: abs(k - word_idx))
        return time_map[best_idx]

    words_per_image = total_words / nb_images
    durations = []
    buffer = 0.3

    for i in range(nb_images):
        start_word = int(i * words_per_image)
        end_word = int((i + 1) * words_per_image)

        if i == 0:
            start_t = 0.0
        else:
            start_t = _nearest_time(start_word)

        if i == nb_images - 1:
            end_t = total_duration + buffer
        else:
            end_t = _nearest_time(end_word)

        dur = max(end_t - start_t, 2.0)
        durations.append(dur)

    target = total_duration + buffer
    current_total = sum(durations)
    if current_total > 0:
        scale = target / current_total
        durations = [d * scale for d in durations]

    return durations


def _generate_chapters_description(
    content: dict, word_timings: list[dict], total_duration: float
) -> str:
    """Genere les timestamps des chapitres pour la description YouTube.

    Utilise les chapitres definis par Claude et les word timings TTS
    pour calculer les timestamps reels.
    """
    chapitres = content.get("chapitres", [])
    if not chapitres:
        return ""

    total_words = len(content["script_complet"].split())
    time_map = {}
    for tp in word_timings:
        time_map[tp["index"]] = tp["time"]

    lines = ["\n\nCHAPITRES :"]
    for chap in chapitres:
        mot_idx = chap.get("mot_index_approx", 0)
        # Trouver le timestamp le plus proche
        if mot_idx in time_map:
            t = time_map[mot_idx]
        elif time_map:
            closest = min(time_map.keys(), key=lambda k: abs(k - mot_idx))
            t = time_map[closest]
        else:
            # Estimation proportionnelle
            t = (mot_idx / max(total_words, 1)) * total_duration

        # Formater en MM:SS
        minutes = int(t // 60)
        seconds = int(t % 60)
        timestamp = f"{minutes:02d}:{seconds:02d}"
        lines.append(f"{timestamp} — {chap['titre']}")

    return "\n".join(lines)


async def run_pipeline():
    """Execute le pipeline YouTube complet (video longue 10-20 min)."""
    global last_run_status, last_run_time, last_run_error

    start = time.time()
    date_str = config.get_date_str()
    last_run_status = "running"
    last_run_time = config.get_datetime_str()
    last_run_error = ""

    try:
        logger.info(f"{'=' * 60}")
        logger.info(f"YouTube Pipeline starting for {date_str}")
        logger.info(f"{'=' * 60}")

        config.init_directories()

        # 0. Generer musique ambient si necessaire
        music_mod.ensure_music_exists()

        # 1. Charger historique
        logger.info("Step 1/8: Loading history...")
        history = publish_mod.load_sheet_history()
        exclusion_text = content_mod.build_exclusion_text(history)

        # 2. Generer contenu (Claude — script long)
        logger.info("Step 2/8: Generating YouTube content (Claude)...")
        content_result = content_mod.generate_content(exclusion_text)
        auteur_clean = clean_filename(content_result["auteur"])
        filename = f"yt_{date_str}_{auteur_clean}"

        word_count = len(content_result["script_complet"].split())
        logger.info(f"Script: {word_count} words, {len(content_result['image_prompts'])} image prompts")

        # 3. Generer audio (TTS — meme module, script plus long)
        logger.info("Step 3/8: Generating audio (TTS)...")
        audio_result = tts_mod.generate_audio(content_result["script_complet"], filename)
        duration_min = audio_result.duration / 60
        logger.info(f"Audio: {duration_min:.1f} min ({audio_result.duration:.0f}s)")

        # 4. Generer images 16:9 (Kie.ai)
        logger.info(f"Step 4/8: Generating {len(content_result['image_prompts'])} images 16:9 (Kie.ai)...")
        image_paths = await images_mod.generate_all_images(
            content_result["image_prompts"], filename
        )

        # 4b. Calculer durees images synchronisees
        segment_durations = _calc_image_durations(
            nb_images=len(image_paths),
            word_timings=audio_result.word_timings,
            total_words=audio_result.word_count,
            total_duration=audio_result.duration,
        )

        # 5. Assembler video 16:9
        logger.info("Step 5/8: Assembling video 16:9 (FFmpeg)...")
        raw_video = video_mod.assemble_video(
            image_paths,
            audio_result.audio_path,
            f"{config.YT_VIDEOS_DIR}/raw_{filename}.mp4",
            audio_result.duration,
            segment_durations=segment_durations,
        )

        # 6. Sous-titres + color grading
        logger.info("Step 6/8: Finalizing video (color grade + subtitles)...")
        ass_content = subtitles_mod.generate_ass(
            content_result["script_complet"],
            audio_result.word_timings,
            audio_result.duration,
            content_result.get("hook_text", ""),
            content_result.get("cta_text", "Si cette idée t'a fait voir les choses autrement, tu sais quoi faire."),
            original_words=audio_result.original_words,
            word_start_times=audio_result.word_start_times,
        )
        ass_path = f"{config.YT_VIDEOS_DIR}/subs_{filename}.ass"
        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(ass_content)

        graded_video = video_mod.finalize_video(
            raw_video, ass_path, f"{config.YT_VIDEOS_DIR}/graded_{filename}.mp4"
        )

        # 7. Mixer musique + generer thumbnail
        logger.info("Step 7/8: Mixing music & generating thumbnail...")

        # Musique
        music_file = music_mod.select_music(
            content_result.get("mood"), audio_result.duration
        )
        final_video = music_mod.mix_music(
            graded_video,
            music_file,
            f"{config.YT_VIDEOS_DIR}/final_{filename}.mp4",
            audio_result.duration,
        )

        # Thumbnail
        thumbnail_path = banner_mod.generate_thumbnail(
            background_image=image_paths[0] if image_paths else "",
            thumbnail_text=content_result.get("thumbnail_text", "CITATION"),
            filename=filename,
            author=content_result.get("auteur", ""),
        )

        # Generer les timestamps des chapitres
        chapters_text = _generate_chapters_description(
            content_result, audio_result.word_timings, audio_result.duration
        )
        if chapters_text and content_result.get("yt_description"):
            content_result["yt_description"] += chapters_text

        # Cleanup intermediaires
        from pathlib import Path
        Path(raw_video).unlink(missing_ok=True)
        Path(graded_video).unlink(missing_ok=True)
        Path(ass_path).unlink(missing_ok=True)

        # 8. Publier
        logger.info("Step 8/8: Publishing...")
        publish_mod.send_telegram_notification(
            content_result, audio_result.duration, final_video, thumbnail_path
        )
        publish_mod.log_to_sheets(content_result, audio_result.duration)
        publish_mod.save_local_log(content_result, audio_result.duration, final_video, thumbnail_path)

        # YouTube upload (non-blocking)
        try:
            publish_mod.upload_youtube(final_video, content_result, thumbnail_path)
        except Exception as e:
            logger.warning(f"YouTube upload failed (non-blocking): {e}")

        elapsed = time.time() - start
        last_run_status = "success"
        logger.info(f"{'=' * 60}")
        logger.info(f"YouTube Pipeline complete in {elapsed:.0f}s ({elapsed/60:.1f}min)")
        logger.info(f"Video: {final_video}")
        logger.info(f"Thumbnail: {thumbnail_path}")
        logger.info(f"Duration: {duration_min:.1f}min | Words: {audio_result.word_count}")
        logger.info(f"Title: {content_result.get('yt_title', 'N/A')}")
        logger.info(f"{'=' * 60}")

    except Exception as e:
        import traceback
        elapsed = time.time() - start
        last_run_status = "error"
        tb = traceback.format_exc()
        last_run_error = f"{e}\n\nTRACEBACK:\n{tb[-1000:]}"
        logger.error(f"YouTube Pipeline FAILED after {elapsed:.0f}s: {e}", exc_info=True)
        try:
            publish_mod.send_telegram_error(str(e))
        except Exception:
            pass


def run_pipeline_sync():
    """Wrapper synchrone pour APScheduler."""
    asyncio.run(run_pipeline())
