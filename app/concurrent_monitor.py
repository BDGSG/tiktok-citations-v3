"""Daily concurrent monitoring — Apify TikTok scraper + Firecrawl blog scraper.

Scrapes top FR accounts in the citations / philosophy niche, ranks recent
videos by engagement, identifies hooks that perform, and pushes a Telegram
report. Runs every morning before content generation, so today's content
can be steered by what's working right now.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass

import httpx

logger = logging.getLogger("citations-v3")

APIFY_TOKEN = os.getenv("APIFY_TOKEN", "")
FIRECRAWL_KEY = os.getenv("FIRECRAWL_API_KEY", "")

APIFY_TIKTOK_ACTOR = "clockworks~tiktok-scraper"  # popular maintained scraper
APIFY_BASE = "https://api.apify.com/v2"

# Top accounts by editorial angle. Tunable.
TARGETS = {
    "A": [  # Stoïcisme féminin
        "laforcestoicienne",
        "essencedeslivres",
        "_un_jour_une_citation_",
        "mood.._citations",
        "ley___citations",
    ],
    "B": [  # Sagesse africaine
        "kalosfrance",
        # Add more as we discover
    ],
    "D": [  # Philosophes femmes
        "essencedeslivres",
        # We'll seed manually as the niche grows
    ],
    "general": [
        "meilleures_citations00",
        "latia_citations",
        "conseildelavie12",
        "optilisme",
    ],
}


@dataclass
class VideoSignal:
    angle: str
    handle: str
    url: str
    text: str  # caption / hook visible
    play_count: int
    like_count: int
    comment_count: int
    engagement_rate: float
    posted_at: str
    music: str

    def to_dict(self) -> dict:
        return self.__dict__


def _start_actor(actor: str, payload: dict) -> str:
    if not APIFY_TOKEN:
        raise RuntimeError("APIFY_TOKEN missing")
    url = f"{APIFY_BASE}/acts/{actor}/runs?token={APIFY_TOKEN}"
    with httpx.Client(timeout=30) as client:
        r = client.post(url, json=payload)
        r.raise_for_status()
    data = r.json()["data"]
    return data["id"]


def _wait_run(run_id: str, max_wait_s: int = 600) -> str:
    url = f"{APIFY_BASE}/actor-runs/{run_id}?token={APIFY_TOKEN}"
    start = time.time()
    while time.time() - start < max_wait_s:
        with httpx.Client(timeout=30) as client:
            r = client.get(url)
            r.raise_for_status()
        d = r.json()["data"]
        status = d.get("status")
        if status == "SUCCEEDED":
            return d["defaultDatasetId"]
        if status in ("FAILED", "ABORTED", "TIMED-OUT"):
            raise RuntimeError(f"Apify run {status}: {d}")
        time.sleep(5)
    raise TimeoutError("Apify run timed out")


def _fetch_dataset(dataset_id: str, limit: int = 200) -> list[dict]:
    url = f"{APIFY_BASE}/datasets/{dataset_id}/items?token={APIFY_TOKEN}&limit={limit}"
    with httpx.Client(timeout=60) as client:
        r = client.get(url)
        r.raise_for_status()
    return r.json()


def _scrape_tiktok(handles: list[str], per_handle: int = 12) -> list[dict]:
    if not APIFY_TOKEN or not handles:
        return []
    payload = {
        "profiles": handles,
        "resultsPerPage": per_handle,
        "shouldDownloadVideos": False,
        "shouldDownloadCovers": False,
        "shouldDownloadSlideshowImages": False,
    }
    try:
        run_id = _start_actor(APIFY_TIKTOK_ACTOR, payload)
        dataset = _wait_run(run_id)
        return _fetch_dataset(dataset)
    except Exception as e:
        logger.error(f"Apify scrape failed: {e}")
        return []


def _to_signal(item: dict, angle: str) -> VideoSignal | None:
    try:
        plays = int(item.get("playCount") or item.get("plays") or 0)
        likes = int(item.get("diggCount") or item.get("likes") or 0)
        comments = int(item.get("commentCount") or item.get("comments") or 0)
        if plays < 100:
            return None
        er = (likes + comments * 2) / plays if plays else 0.0
        author = (item.get("authorMeta") or {}).get("name") or item.get("author") or ""
        music = (item.get("musicMeta") or {}).get("musicName", "") or ""
        return VideoSignal(
            angle=angle,
            handle=author,
            url=item.get("webVideoUrl") or item.get("url") or "",
            text=(item.get("text") or item.get("caption") or "")[:280],
            play_count=plays,
            like_count=likes,
            comment_count=comments,
            engagement_rate=round(er * 100, 2),
            posted_at=item.get("createTimeISO", "") or item.get("createTime", ""),
            music=music[:80],
        )
    except Exception:
        return None


def daily_report() -> dict:
    """Run scrape, return ranked report. Idempotent if Apify is unavailable."""
    all_signals: list[VideoSignal] = []
    for angle, handles in TARGETS.items():
        if angle == "general":
            angle_label = "X"
        else:
            angle_label = angle
        items = _scrape_tiktok(handles)
        logger.info(f"Apify: angle={angle_label} fetched {len(items)} items")
        for item in items:
            sig = _to_signal(item, angle_label)
            if sig:
                all_signals.append(sig)

    # Rank by engagement rate, dedupe url
    seen = set()
    ranked: list[VideoSignal] = []
    for sig in sorted(all_signals, key=lambda s: s.engagement_rate, reverse=True):
        if sig.url in seen:
            continue
        seen.add(sig.url)
        ranked.append(sig)

    top = ranked[:10]
    by_angle: dict[str, list[VideoSignal]] = {}
    for sig in ranked:
        by_angle.setdefault(sig.angle, []).append(sig)

    return {
        "total_signals": len(all_signals),
        "top10": [s.to_dict() for s in top],
        "by_angle_top3": {
            angle: [s.to_dict() for s in sigs[:3]]
            for angle, sigs in by_angle.items()
        },
    }


def format_telegram_message(report: dict) -> str:
    lines = [f"📊 *Citations daily intel — {report['total_signals']} videos analysed*\n"]
    lines.append("*Top engagement (toutes niches)* :")
    for sig in report["top10"][:5]:
        lines.append(
            f"• @{sig['handle']} — {sig['engagement_rate']}% ER · "
            f"{sig['play_count']:,} plays · {sig['text'][:80]}"
        )
    lines.append("")
    for angle, top in report["by_angle_top3"].items():
        if not top:
            continue
        lines.append(f"*Top angle {angle}* :")
        for sig in top:
            lines.append(
                f"• @{sig['handle']} — {sig['engagement_rate']}% · "
                f"{sig['play_count']:,} plays — {sig['music'][:30] if sig['music'] else 'no audio info'}"
            )
        lines.append("")
    return "\n".join(lines)
