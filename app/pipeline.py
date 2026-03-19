"""Orchestrateur principal — coordonne tous les modules."""
import time
import asyncio
import logging
from . import config
from . import content as content_mod
from . import tts as tts_mod
from . import images as images_mod
from . import video as video_mod
from . import subtitles as subtitles_mod
from . import music as music_mod
from . import publish as publish_mod
from .utils import clean_filename

logger = logging.getLogger("citations-v3")

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
    """Calcule la duree de chaque image basee sur les word timings TTS.

    Chaque image couvre un bloc de mots proportionnel. Le timestamp de debut/fin
    de chaque bloc est extrait des timepoints TTS, ce qui synchronise les
    changements d'image avec la narration.
    """
    if not word_timings or total_words < nb_images:
        return None

    # Construire mapping index -> temps
    time_map = {}
    for tp in word_timings:
        time_map[tp["index"]] = tp["time"]

    def _nearest_time(word_idx: int) -> float:
        """Trouve le timestamp le plus proche pour un index de mot."""
        if word_idx in time_map:
            return time_map[word_idx]
        # Chercher le plus proche
        best_idx = min(time_map.keys(), key=lambda k: abs(k - word_idx))
        return time_map[best_idx]

    words_per_image = total_words / nb_images
    durations = []
    buffer = 0.3  # petite marge pour que les images couvrent tout l'audio

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

        dur = max(end_t - start_t, 2.0)  # minimum 2s par image
        durations.append(dur)

    # Ajuster pour que la somme couvre bien la duree totale + marge
    target = total_duration + buffer
    current_total = sum(durations)
    if current_total > 0:
        scale = target / current_total
        durations = [d * scale for d in durations]

    return durations


async def run_pipeline():
    """Execute le pipeline complet de generation video."""
    global last_run_status, last_run_time, last_run_error

    start = time.time()
    date_str = config.get_date_str()
    last_run_status = "running"
    last_run_time = config.get_datetime_str()
    last_run_error = ""

    try:
        logger.info(f"{'=' * 60}")
        logger.info(f"Pipeline V3 starting for {date_str}")
        logger.info(f"{'=' * 60}")

        config.init_directories()

        # 0. Generer musique ambient si necessaire
        music_mod.ensure_music_exists()

        # 1. Charger historique
        logger.info("Step 1/7: Loading history...")
        history = publish_mod.load_sheet_history()
        exclusion_text = content_mod.build_exclusion_text(history)

        # 2. Generer contenu (Claude)
        logger.info("Step 2/7: Generating content (Claude)...")
        content_result = content_mod.generate_content(exclusion_text)
        auteur_clean = clean_filename(content_result["auteur"])
        filename = f"citation_{date_str}_{auteur_clean}"

        # 3. Generer audio (TTS)
        logger.info("Step 3/7: Generating audio (TTS)...")
        audio_result = tts_mod.generate_audio(content_result["script_complet"], filename)

        # 4. Generer images (Kie.ai — parallele)
        logger.info("Step 4/7: Generating images (Kie.ai)...")
        image_paths = await images_mod.generate_all_images(
            content_result["image_prompts"], filename
        )

        # 4b. Calculer durees images synchronisees avec la narration
        segment_durations = _calc_image_durations(
            nb_images=len(image_paths),
            word_timings=audio_result.word_timings,
            total_words=audio_result.word_count,
            total_duration=audio_result.duration,
        )

        # 5. Assembler video (FFmpeg)
        logger.info("Step 5/7: Assembling video (FFmpeg)...")
        raw_video = video_mod.assemble_video(
            image_paths,
            audio_result.audio_path,
            f"{config.VIDEOS_DIR}/raw_{filename}.mp4",
            audio_result.duration,
            segment_durations=segment_durations,
        )

        # 6. Generer sous-titres + color grading + graver (1 seule passe)
        logger.info("Step 6/7: Finalizing video (color grade + subtitles)...")
        ass_content = subtitles_mod.generate_ass(
            content_result["script_complet"],
            audio_result.word_timings,
            audio_result.duration,
            content_result.get("hook_text", ""),
            content_result.get("cta_text", "Save cette video"),
        )
        ass_path = f"{config.VIDEOS_DIR}/subs_{filename}.ass"
        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(ass_content)

        graded_video = video_mod.finalize_video(
            raw_video, ass_path, f"{config.VIDEOS_DIR}/graded_{filename}.mp4"
        )

        # 7. Mixer musique + publier
        logger.info("Step 7/7: Mixing music & publishing...")
        music_file = music_mod.select_music(
            content_result.get("mood"), audio_result.duration
        )
        final_video = music_mod.mix_music(
            graded_video,
            music_file,
            f"{config.VIDEOS_DIR}/final_{filename}.mp4",
            audio_result.duration,
        )

        # Cleanup intermediaires
        from pathlib import Path
        Path(raw_video).unlink(missing_ok=True)
        Path(graded_video).unlink(missing_ok=True)
        Path(ass_path).unlink(missing_ok=True)

        # Publier
        publish_mod.send_telegram_notification(
            content_result, audio_result.duration, final_video
        )
        publish_mod.log_to_sheets(content_result, audio_result.duration)
        publish_mod.save_local_log(content_result, audio_result.duration, final_video)

        # TikTok (try, ne fait pas echouer le pipeline)
        try:
            publish_mod.upload_tiktok(final_video, content_result)
        except Exception as e:
            logger.warning(f"TikTok upload failed (non-blocking): {e}")

        # YouTube Shorts (prive, non-blocking)
        try:
            from youtube import publish as yt_publish_mod
            tags_str = " ".join(f"#{t}" for t in content_result.get("tags", [])[:5])
            short_title = f"{content_result.get('hook', content_result.get('citation', '')[:50])} #Shorts {tags_str}"
            if len(short_title) > 100:
                short_title = short_title[:97] + "..."
            short_content = {
                "yt_title": short_title,
                "yt_description": (
                    f'"{content_result["citation"]}"\n'
                    f"— {content_result['auteur']}\n\n"
                    f"{content_result.get('takeaway', '')}\n\n"
                    f"#Shorts #citationdujour #motivation #philosophie {tags_str}"
                ),
                "yt_tags": ["Shorts", "citationdujour", "motivation", "philosophie"]
                    + content_result.get("tags", [])[:5],
            }
            yt_publish_mod.upload_youtube(final_video, short_content, is_short=True)
        except Exception as e:
            logger.warning(f"YouTube Shorts upload failed (non-blocking): {e}")

        elapsed = time.time() - start
        last_run_status = "success"
        logger.info(f"{'=' * 60}")
        logger.info(f"Pipeline complete in {elapsed:.0f}s")
        logger.info(f"Video: {final_video}")
        logger.info(f"Duration: {audio_result.duration:.1f}s | Words: {audio_result.word_count}")
        logger.info(f"{'=' * 60}")

    except Exception as e:
        elapsed = time.time() - start
        last_run_status = "error"
        last_run_error = str(e)
        logger.error(f"Pipeline FAILED after {elapsed:.0f}s: {e}", exc_info=True)
        try:
            publish_mod.send_telegram_error(str(e))
        except Exception:
            pass


def run_pipeline_sync():
    """Wrapper synchrone pour APScheduler."""
    asyncio.run(run_pipeline())
