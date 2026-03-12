"""Point d'entree — FastAPI + APScheduler (TikTok + YouTube)."""
import json
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from . import config
from . import pipeline
from .utils import setup_logging

logger = setup_logging()
scheduler = BackgroundScheduler(timezone=pytz.timezone(config.TZ))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown events."""
    config.init_directories()

    # Job TikTok
    scheduler.add_job(
        pipeline.run_pipeline_sync,
        CronTrigger(hour=config.SCHEDULE_HOUR, minute=config.SCHEDULE_MINUTE),
        id="daily_citation",
        replace_existing=True,
    )
    logger.info(
        f"TikTok scheduler: daily at {config.SCHEDULE_HOUR:02d}:{config.SCHEDULE_MINUTE:02d} {config.TZ}"
    )

    # Job YouTube
    from youtube import config as yt_config
    from youtube import pipeline as yt_pipeline
    yt_config.init_directories()
    scheduler.add_job(
        yt_pipeline.run_pipeline_sync,
        CronTrigger(hour=yt_config.SCHEDULE_HOUR, minute=yt_config.SCHEDULE_MINUTE),
        id="daily_youtube",
        replace_existing=True,
    )
    logger.info(
        f"YouTube scheduler: daily at {yt_config.SCHEDULE_HOUR:02d}:{yt_config.SCHEDULE_MINUTE:02d} {config.TZ}"
    )

    scheduler.start()
    yield
    scheduler.shutdown()
    logger.info("Schedulers stopped")


app = FastAPI(
    title="Citations Pipeline — TikTok & YouTube",
    description="Pipeline automatise de generation de videos TikTok (4-5min) et YouTube (10-20min)",
    version="3.1.0",
    lifespan=lifespan,
)


# ============================================================
# Health check global
# ============================================================

@app.get("/")
@app.get("/health")
def health():
    """Health check global."""
    from youtube import pipeline as yt_pipeline
    from youtube import config as yt_config

    tiktok_job = scheduler.get_job("daily_citation")
    youtube_job = scheduler.get_job("daily_youtube")
    return {
        "status": "ok",
        "version": "3.1.0",
        "tiktok": {
            "last_run_status": pipeline.last_run_status,
            "last_run_time": pipeline.last_run_time,
            "last_run_error": pipeline.last_run_error,
            "next_run": str(tiktok_job.next_run_time) if tiktok_job else "not scheduled",
            "schedule": f"{config.SCHEDULE_HOUR:02d}:{config.SCHEDULE_MINUTE:02d} {config.TZ}",
        },
        "youtube": {
            "last_run_status": yt_pipeline.last_run_status,
            "last_run_time": yt_pipeline.last_run_time,
            "last_run_error": yt_pipeline.last_run_error,
            "next_run": str(youtube_job.next_run_time) if youtube_job else "not scheduled",
            "schedule": f"{yt_config.SCHEDULE_HOUR:02d}:{yt_config.SCHEDULE_MINUTE:02d} {config.TZ}",
            "config": {
                "format": f"{yt_config.VIDEO_WIDTH}x{yt_config.VIDEO_HEIGHT}",
                "target_duration": "10-20 min",
                "script_words": f"{yt_config.SCRIPT_MIN_WORDS}-{yt_config.SCRIPT_MAX_WORDS}",
            },
        },
    }


# ============================================================
# TikTok endpoints
# ============================================================

@app.post("/trigger")
async def trigger(background_tasks: BackgroundTasks):
    """Declenche manuellement le pipeline TikTok."""
    if pipeline.last_run_status == "running":
        return {"status": "already_running", "started_at": pipeline.last_run_time}
    background_tasks.add_task(pipeline.run_pipeline_sync)
    return {"status": "triggered", "message": "TikTok Pipeline started in background"}


@app.get("/history")
def history():
    """Retourne les 30 dernieres executions TikTok."""
    history_dir = config.HISTORY_DIR
    if not os.path.isdir(history_dir):
        return {"executions": []}
    files = sorted(
        [f for f in os.listdir(history_dir) if f.endswith(".json")],
        reverse=True,
    )[:30]
    executions = []
    for f in files:
        try:
            with open(os.path.join(history_dir, f), "r", encoding="utf-8") as fh:
                executions.append(json.load(fh))
        except Exception:
            pass
    return {"executions": executions, "count": len(executions)}


@app.get("/history/{date}")
def history_by_date(date: str):
    """Retourne l'execution TikTok d'une date specifique."""
    log_path = f"{config.HISTORY_DIR}/{date}.json"
    if not os.path.isfile(log_path):
        return {"error": f"No execution found for {date}"}
    with open(log_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# YouTube endpoints
# ============================================================

@app.post("/trigger/youtube")
async def trigger_youtube(background_tasks: BackgroundTasks):
    """Declenche manuellement le pipeline YouTube."""
    from youtube import pipeline as yt_pipeline
    if yt_pipeline.last_run_status == "running":
        return {"status": "already_running", "started_at": yt_pipeline.last_run_time}
    background_tasks.add_task(yt_pipeline.run_pipeline_sync)
    return {"status": "triggered", "message": "YouTube Pipeline started in background"}


@app.get("/history/youtube")
def history_youtube():
    """Retourne les 30 dernieres executions YouTube."""
    from youtube import config as yt_config
    history_dir = yt_config.YT_HISTORY_DIR
    if not os.path.isdir(history_dir):
        return {"executions": []}
    files = sorted(
        [f for f in os.listdir(history_dir) if f.endswith(".json")],
        reverse=True,
    )[:30]
    executions = []
    for f in files:
        try:
            with open(os.path.join(history_dir, f), "r", encoding="utf-8") as fh:
                executions.append(json.load(fh))
        except Exception:
            pass
    return {"executions": executions, "count": len(executions)}


@app.get("/history/youtube/{date}")
def history_youtube_by_date(date: str):
    """Retourne l'execution YouTube d'une date specifique."""
    from youtube import config as yt_config
    log_path = f"{yt_config.YT_HISTORY_DIR}/{date}_youtube.json"
    if not os.path.isfile(log_path):
        return {"error": f"No YouTube execution found for {date}"}
    with open(log_path, "r", encoding="utf-8") as f:
        return json.load(f)
