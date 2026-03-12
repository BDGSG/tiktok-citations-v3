"""Pipeline Shorts Sagesse — video courte 15-45s, format 9:16, upload YouTube Short."""
import time
import asyncio
import logging
from pathlib import Path
from . import config
from . import content as content_mod
from app import tts as tts_mod
from app import images as images_mod
from app import video as video_mod
from app import subtitles as subtitles_mod
from app import music as music_mod
from app import config as app_config
from app.utils import clean_filename

logger = logging.getLogger("shorts-sagesse")

last_run_status: str = "never"
last_run_time: str = ""
last_run_error: str = ""


async def run_pipeline():
    """Execute le pipeline Shorts Sagesse complet."""
    global last_run_status, last_run_time, last_run_error

    start = time.time()
    date_str = app_config.get_date_str()
    last_run_status = "running"
    last_run_time = app_config.get_datetime_str()
    last_run_error = ""

    try:
        logger.info(f"{'=' * 50}")
        logger.info(f"Shorts Sagesse Pipeline starting for {date_str}")
        logger.info(f"{'=' * 50}")

        config.init_directories()
        app_config.init_directories()
        music_mod.ensure_music_exists()

        # 1. Generer contenu (Kie.ai — court)
        logger.info("Step 1/5: Generating content...")
        content_result = content_mod.generate_content()
        content_type = content_result["content_type"]
        filename = f"short_{date_str}_{content_type}"

        word_count = len(content_result["script_complet"].split())
        logger.info(f"Content: {content_type} | {word_count} mots")

        # 2. TTS (court, 15-45s)
        logger.info("Step 2/5: Generating audio (TTS)...")
        audio_result = tts_mod.generate_audio(content_result["script_complet"], filename)
        logger.info(f"Audio: {audio_result.duration:.1f}s")

        # 3. Image (1 seule, 9:16)
        logger.info("Step 3/5: Generating image...")
        image_paths = await images_mod.generate_all_images(
            content_result["image_prompts"], filename
        )

        if not image_paths:
            raise RuntimeError("Aucune image generee")

        # 4. Assembler video (1 image + audio + sous-titres)
        logger.info("Step 4/5: Assembling video...")
        raw_video = video_mod.assemble_video(
            image_paths,
            audio_result.audio_path,
            f"{config.SHORTS_VIDEOS_DIR}/raw_{filename}.mp4",
            audio_result.duration,
            segment_durations=[audio_result.duration + 0.5],
        )

        # Sous-titres
        ass_content = subtitles_mod.generate_ass(
            content_result["script_complet"],
            audio_result.word_timings,
            audio_result.duration,
            content_result.get("hook_text", ""),
            "",  # pas de CTA pour les shorts
        )
        ass_path = f"{config.SHORTS_VIDEOS_DIR}/subs_{filename}.ass"
        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(ass_content)

        graded_video = video_mod.finalize_video(
            raw_video, ass_path, f"{config.SHORTS_VIDEOS_DIR}/graded_{filename}.mp4"
        )

        # Musique
        music_file = music_mod.select_music(
            content_result.get("mood"), audio_result.duration
        )
        final_video = music_mod.mix_music(
            graded_video,
            music_file,
            f"{config.SHORTS_VIDEOS_DIR}/final_{filename}.mp4",
            audio_result.duration,
        )

        # Cleanup
        Path(raw_video).unlink(missing_ok=True)
        Path(graded_video).unlink(missing_ok=True)
        Path(ass_path).unlink(missing_ok=True)

        # 5. Upload YouTube Short (prive)
        logger.info("Step 5/5: Uploading YouTube Short...")
        try:
            from youtube import publish as yt_publish_mod
            tags_str = " ".join(f"#{t}" for t in content_result.get("tags", [])[:5])
            short_title = f"{content_result.get('hook_text', 'Sagesse du jour')} #Shorts {tags_str}"
            if len(short_title) > 100:
                short_title = short_title[:97] + "..."
            short_content = {
                "yt_title": short_title,
                "yt_description": (
                    f"{content_result['script_complet'][:200]}\n\n"
                    f"#Shorts #sagesse #motivation #philosophie {tags_str}"
                ),
                "yt_tags": ["Shorts", "sagesse", "motivation", "philosophie"]
                    + content_result.get("tags", [])[:5],
            }
            result = yt_publish_mod.upload_youtube(final_video, short_content)
            if result:
                logger.info(f"YouTube Short uploaded: {result.get('video_id')}")
        except Exception as e:
            logger.warning(f"YouTube Short upload failed (non-blocking): {e}")

        # Telegram notification
        try:
            from youtube import publish as yt_publish_mod
            yt_publish_mod.send_telegram_text(
                f"<b>Shorts Sagesse — {content_type}</b>\n\n"
                f"{content_result['script_complet'][:300]}\n\n"
                f"Duree: {audio_result.duration:.0f}s | Mots: {word_count}"
            )
        except Exception:
            pass

        # Log local
        import json
        log = {
            "date": date_str,
            "datetime": app_config.get_datetime_str(),
            "platform": "shorts",
            "content_type": content_type,
            "script": content_result["script_complet"],
            "word_count": word_count,
            "duration": round(audio_result.duration, 1),
            "video_path": final_video,
            "tags": content_result.get("tags", []),
        }
        log_path = f"{config.SHORTS_HISTORY_DIR}/{date_str}_short.json"
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)

        elapsed = time.time() - start
        last_run_status = "success"
        logger.info(f"{'=' * 50}")
        logger.info(f"Shorts Sagesse complete in {elapsed:.0f}s")
        logger.info(f"Video: {final_video} | {audio_result.duration:.1f}s")
        logger.info(f"{'=' * 50}")

    except Exception as e:
        import traceback
        elapsed = time.time() - start
        last_run_status = "error"
        tb = traceback.format_exc()
        last_run_error = f"{e}\n\nTRACEBACK:\n{tb[-1000:]}"
        logger.error(f"Shorts Pipeline FAILED after {elapsed:.0f}s: {e}", exc_info=True)
        try:
            from youtube import publish as yt_publish_mod
            yt_publish_mod.send_telegram_text(
                f"<b>Shorts Sagesse — ERREUR</b>\n\n{str(e)[:500]}"
            )
        except Exception:
            pass


def run_pipeline_sync():
    asyncio.run(run_pipeline())
