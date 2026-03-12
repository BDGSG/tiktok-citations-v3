"""Point d'entree YouTube — FastAPI + APScheduler."""
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
from app.utils import setup_logging

logger = logging.getLogger("youtube-citations")
setup_logging()
scheduler = BackgroundScheduler(timezone=pytz.timezone(config.TZ))


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.init_directories()
    scheduler.add_job(
        pipeline.run_pipeline_sync,
        CronTrigger(hour=config.SCHEDULE_HOUR, minute=config.SCHEDULE_MINUTE),
        id="daily_youtube",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        f"YouTube Scheduler started: daily at "
        f"{config.SCHEDULE_HOUR:02d}:{config.SCHEDULE_MINUTE:02d} {config.TZ}"
    )
    yield
    scheduler.shutdown()
    logger.info("YouTube Scheduler stopped")


app = FastAPI(
    title="YouTube Citations",
    description="Pipeline de generation de videos YouTube motivationnelles (10-20 min)",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/")
@app.get("/health")
def health():
    job = scheduler.get_job("daily_youtube")
    next_run = str(job.next_run_time) if job else "not scheduled"
    return {
        "status": "ok",
        "platform": "youtube",
        "version": "1.0.0",
        "last_run_status": pipeline.last_run_status,
        "last_run_time": pipeline.last_run_time,
        "last_run_error": pipeline.last_run_error,
        "next_run": next_run,
        "schedule": f"{config.SCHEDULE_HOUR:02d}:{config.SCHEDULE_MINUTE:02d} {config.TZ}",
        "config": {
            "video_format": f"{config.VIDEO_WIDTH}x{config.VIDEO_HEIGHT} (16:9)",
            "script_words": f"{config.SCRIPT_MIN_WORDS}-{config.SCRIPT_MAX_WORDS}",
            "target_duration": "10-20 min",
            "image_prompts": f"{config.MIN_IMAGE_PROMPTS}+",
        },
    }


@app.post("/trigger")
async def trigger(background_tasks: BackgroundTasks):
    if pipeline.last_run_status == "running":
        return {"status": "already_running", "started_at": pipeline.last_run_time}
    background_tasks.add_task(pipeline.run_pipeline_sync)
    return {"status": "triggered", "message": "YouTube Pipeline started in background"}


@app.get("/history")
def history():
    history_dir = config.YT_HISTORY_DIR
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
    log_path = f"{config.YT_HISTORY_DIR}/{date}_youtube.json"
    if not os.path.isfile(log_path):
        return {"error": f"No YouTube execution found for {date}"}
    with open(log_path, "r", encoding="utf-8") as f:
        return json.load(f)
