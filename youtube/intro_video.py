"""Generation de la video d'introduction de la chaine Citation du Jour.

Usage:
    POST /generate/intro  (endpoint dans main.py)
    ou: python -m youtube.intro_video
"""
import asyncio
import logging
import time
from pathlib import Path
from . import config
from . import video as video_mod
from . import images as images_mod
from . import subtitles as subtitles_mod
from . import publish as publish_mod
from app import tts as tts_mod
from app import music as music_mod

logger = logging.getLogger("youtube-citations")

# Script de la video d'introduction (voix-off)
INTRO_SCRIPT = """
Imagine un endroit où chaque jour, une seule idée peut changer ta façon de voir le monde.

Bienvenue sur Citation du Jour.

Ici, on ne se contente pas de lire des phrases sur un joli fond d'écran. On plonge au cœur de la pensée des plus grands esprits de l'histoire.

Marc Aurèle, empereur romain et philosophe stoïcien. Sénèque, qui écrivait sous la menace de Néron. Épictète, ancien esclave devenu maître de sagesse. Nietzsche, Montaigne, Confucius, Camus.

Leurs mots ont traversé les siècles. Et ils parlent encore. Peut-être plus fort que jamais.

Chaque vidéo est un voyage. Un script profond, une voix-off immersive, des visuels cinématiques. Pas de superficiel. Pas de clichés motivationnels vides. Juste de la substance.

On décortique la citation. On raconte l'histoire du penseur. On montre comment sa sagesse s'applique à ta vie, aujourd'hui, concrètement.

Du stoïcisme antique au développement personnel moderne. De la philosophie grecque aux défis du quotidien.

Si tu cherches à comprendre le monde autrement, à développer ta résilience, à trouver ta propre philosophie de vie, alors tu es au bon endroit.

Une nouvelle vidéo chaque jour. Abonne-toi, active la cloche, et laisse la sagesse des siècles transformer ton quotidien.

Citation du Jour. La philosophie, pour de vrai.
"""

INTRO_TITLE = "Citation du Jour — Bande-annonce de la chaîne"

INTRO_DESCRIPTION = """Bienvenue sur Citation du Jour ! 🎬

Cette vidéo présente notre chaîne et ce que vous y trouverez :

• Une nouvelle citation philosophique décryptée chaque jour
• Les plus grands penseurs : Marc Aurèle, Sénèque, Épictète, Nietzsche, Montaigne, Confucius...
• Du stoïcisme antique au développement personnel moderne
• Des visuels cinématiques et une voix-off immersive
• Des analyses profondes, pas des phrases motivationnelles creuses

Abonnez-vous et activez la cloche 🔔 pour ne rien manquer !

TikTok : @cdjour

#Citations #Philosophie #Sagesse #Stoïcisme #DéveloppementPersonnel #CitationDuJour #Motivation #BandeAnnonce
"""

INTRO_TAGS = [
    "citation du jour", "philosophie", "sagesse", "stoïcisme",
    "développement personnel", "motivation", "marc aurèle", "sénèque",
    "épictète", "nietzsche", "montaigne", "confucius", "camus",
    "citations inspirantes", "bande-annonce", "trailer", "chaîne youtube",
    "philosophie de vie", "sagesse antique", "leçons de vie",
]

# Prompts d'images pour la video d'introduction
INTRO_IMAGE_PROMPTS = [
    "vast cosmic nebula with golden light rays piercing through darkness, sense of infinite possibility",
    "ancient Greek marble bust of Marcus Aurelius in dramatic side lighting, dark moody background",
    "stormy ocean waves crashing against ancient Roman ruins at sunset, dramatic clouds",
    "old leather-bound books stacked with golden candlelight illuminating dusty library",
    "Seneca writing at a wooden desk by candlelight in ancient Rome, dramatic chiaroscuro",
    "Epictetus teaching students in an ancient Greek courtyard, warm golden hour light",
    "silhouette of a solitary figure standing on a mountain peak at dawn, vast landscape below",
    "Nietzsche walking alone on a misty mountain path, dark romantic painting style",
    "ancient Greek temple columns at golden hour with volumetric light beams",
    "close-up of weathered hands holding an old scroll with ancient text, dramatic lighting",
    "cinematic landscape of rolling hills under dramatic storm clouds with sun breaking through",
    "abstract sacred geometry patterns emerging from darkness, gold and teal colors",
    "person meditating in a dark room with a single beam of light from above",
    "ancient philosopher statue overlooking a modern city at night, double exposure",
    "sunrise over ancient ruins with mist and golden light, sense of rebirth",
]


async def generate_intro():
    """Genere la video d'introduction de la chaine."""
    start = time.time()
    config.init_directories()
    music_mod.ensure_music_exists()

    filename = "intro_citation_du_jour"

    logger.info("=" * 60)
    logger.info("Generating channel intro video")
    logger.info("=" * 60)

    # 1. TTS
    logger.info("Step 1/5: Generating voiceover...")
    audio_result = tts_mod.generate_audio(INTRO_SCRIPT, filename)
    logger.info(f"Audio: {audio_result.duration:.1f}s ({audio_result.duration/60:.1f}min)")

    # 2. Images
    logger.info(f"Step 2/5: Generating {len(INTRO_IMAGE_PROMPTS)} images...")
    image_paths = await images_mod.generate_all_images(INTRO_IMAGE_PROMPTS, filename)

    # 3. Assembler video
    logger.info("Step 3/5: Assembling video...")
    raw_video = video_mod.assemble_video(
        image_paths,
        audio_result.audio_path,
        f"{config.YT_VIDEOS_DIR}/raw_{filename}.mp4",
        audio_result.duration,
    )

    # 4. Sous-titres + color grading
    logger.info("Step 4/5: Adding subtitles and color grading...")
    ass_content = subtitles_mod.generate_ass(
        INTRO_SCRIPT,
        audio_result.word_timings,
        audio_result.duration,
        hook_text="Citation du Jour",
        cta_text="Abonne-toi et active la cloche",
        original_words=audio_result.original_words,
        word_start_times=audio_result.word_start_times,
    )
    ass_path = f"{config.YT_VIDEOS_DIR}/subs_{filename}.ass"
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass_content)

    graded_video = video_mod.finalize_video(
        raw_video, ass_path, f"{config.YT_VIDEOS_DIR}/graded_{filename}.mp4"
    )

    # 5. Musique
    logger.info("Step 5/5: Mixing music...")
    music_file = music_mod.select_music("dark_motivation", audio_result.duration)
    final_video = music_mod.mix_music(
        graded_video,
        music_file,
        f"{config.YT_VIDEOS_DIR}/final_{filename}.mp4",
        audio_result.duration,
    )

    # Cleanup
    Path(raw_video).unlink(missing_ok=True)
    Path(graded_video).unlink(missing_ok=True)
    Path(ass_path).unlink(missing_ok=True)

    elapsed = time.time() - start
    logger.info(f"Intro video complete in {elapsed:.0f}s")
    logger.info(f"Video: {final_video}")

    return {
        "video_path": final_video,
        "duration": audio_result.duration,
        "word_count": audio_result.word_count,
        "elapsed": elapsed,
    }


async def generate_and_upload_intro():
    """Genere et uploade la video d'introduction."""
    result = await generate_intro()

    content = {
        "yt_title": INTRO_TITLE,
        "yt_description": INTRO_DESCRIPTION,
        "yt_tags": INTRO_TAGS,
        "tags": INTRO_TAGS,
        "hook": "Citation du Jour",
    }

    try:
        upload_result = publish_mod.upload_youtube(
            result["video_path"], content
        )
        if upload_result:
            result["youtube_id"] = upload_result.get("video_id")
            logger.info(f"Intro uploaded: {result.get('youtube_id')}")
    except Exception as e:
        logger.warning(f"Intro upload failed: {e}")
        result["upload_error"] = str(e)

    return result


def run_sync():
    """Wrapper synchrone."""
    return asyncio.run(generate_and_upload_intro())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run_sync()
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))
