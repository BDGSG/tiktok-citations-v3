"""Publication — Telegram, TikTok, Supabase history, log local."""
import json
import os
import logging
from datetime import datetime, timezone
from pathlib import Path
import httpx
from . import config
from . import supabase_client

logger = logging.getLogger("citations-v3")


# ============================================================
# Telegram
# ============================================================

def send_telegram_text(text: str) -> bool:
    """Envoie un message texte via Telegram."""
    if not config.TELEGRAM_BOT_TOKEN:
        logger.warning("Telegram: no bot token, skipping")
        return False
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    with httpx.Client(timeout=30) as client:
        resp = client.post(url, json={
            "chat_id": config.TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
        })
        resp.raise_for_status()
    return True


def send_telegram_video(video_path: str, caption: str) -> bool:
    """Envoie une video via Telegram."""
    if not config.TELEGRAM_BOT_TOKEN:
        return False
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendVideo"
    if len(caption) > 1024:
        caption = caption[:1020] + "..."

    with httpx.Client(timeout=120) as client:
        with open(video_path, "rb") as f:
            resp = client.post(url, data={
                "chat_id": config.TELEGRAM_CHAT_ID,
                "caption": caption,
                "parse_mode": "HTML",
            }, files={"video": (Path(video_path).name, f, "video/mp4")})
            resp.raise_for_status()
    logger.info("Telegram: video sent")
    return True


def send_telegram_notification(content: dict, duration: float, video_path: str) -> bool:
    """Envoie la notification recapitulative + video."""
    tags = " ".join(f"#{t}" for t in content.get("tags", []))
    text = (
        f"<b>Citation du Jour V3 - TikTok</b>\n\n"
        f'"{content["citation"]}"\n'
        f"-- {content['auteur']}\n\n"
        f"Hook: {content.get('hook_text', '')}\n"
        f"Categorie: {content.get('categorie', '')}\n"
        f"Mood: {content.get('mood', '')}\n"
        f"Duree: {duration:.0f}s\n"
        f"Mots: {len(content['script_complet'].split())}\n\n"
        f"{tags}"
    )

    caption = (
        f'"{content["citation"]}"\n'
        f"-- {content['auteur']}\n\n"
        f"{content.get('takeaway', '')}\n\n"
        f"#citationdujour #motivation #philosophie {tags}"
    )

    send_telegram_text(text)
    return send_telegram_video(video_path, caption)


def send_telegram_error(error_msg: str) -> bool:
    """Envoie une notification d'erreur."""
    return send_telegram_text(f"<b>Citation V3 - ERREUR</b>\n\n{error_msg[:500]}")


# ============================================================
# TikTok Upload
# ============================================================

def _read_tiktok_token() -> dict | None:
    if not os.path.isfile(config.TOKEN_PATH):
        logger.warning(f"TikTok: token file not found: {config.TOKEN_PATH}")
        return None
    with open(config.TOKEN_PATH, "r") as f:
        return json.load(f)


def _refresh_tiktok_token(token: dict) -> dict:
    with httpx.Client(timeout=30) as client:
        resp = client.post(
            "https://open.tiktokapis.com/v2/oauth/token/",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "client_key": config.TIKTOK_CLIENT_KEY,
                "client_secret": config.TIKTOK_CLIENT_SECRET,
                "refresh_token": token["refresh_token"],
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    if data.get("error") or not data.get("access_token"):
        raise RuntimeError(f"TikTok token refresh failed: {data}")

    new_token = {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "expires_in": data["expires_in"],
        "refresh_expires_in": data.get("refresh_expires_in", 0),
        "open_id": data["open_id"],
        "scope": data.get("scope", ""),
        "token_type": data.get("token_type", "Bearer"),
        "obtained_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": datetime.fromtimestamp(
            datetime.now(timezone.utc).timestamp() + data["expires_in"],
            tz=timezone.utc,
        ).isoformat(),
    }

    with open(config.TOKEN_PATH, "w") as f:
        json.dump(new_token, f, indent=2)

    logger.info("TikTok: token refreshed")
    return new_token


def _get_valid_token() -> dict | None:
    token = _read_tiktok_token()
    if not token:
        return None

    expires_at = datetime.fromisoformat(token["expires_at"])
    if not expires_at.tzinfo:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)

    if now.timestamp() > (expires_at.timestamp() - 300):
        logger.info("TikTok: token expired, refreshing...")
        try:
            token = _refresh_tiktok_token(token)
        except Exception as e:
            logger.error(f"TikTok: token refresh failed: {e}")
            return None

    return token


def upload_tiktok(video_path: str, content: dict) -> dict | None:
    token = _get_valid_token()
    if not token:
        logger.warning("TikTok: no valid token, skipping upload")
        return None

    access_token = token["access_token"]
    video_size = os.path.getsize(video_path)

    tags_str = " ".join(f"#{t}" for t in content.get("tags", [])[:5])
    title = f"{content.get('hook', '')} {tags_str}"
    if len(title) > 150:
        title = title[:147] + "..."

    with httpx.Client(timeout=30) as client:
        resp = client.post(
            "https://open.tiktokapis.com/v2/post/publish/video/init/",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
            },
            json={
                "post_info": {
                    "title": title,
                    "privacy_level": "PUBLIC_TO_EVERYONE",
                    "disable_duet": False,
                    "disable_comment": False,
                    "disable_stitch": False,
                    "video_cover_timestamp_ms": 3000,
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": video_size,
                    "chunk_size": video_size,
                    "total_chunk_count": 1,
                },
            },
        )
        resp.raise_for_status()
        init_data = resp.json()

    upload_url = init_data.get("data", {}).get("upload_url")
    if not upload_url:
        raise RuntimeError(f"TikTok: no upload_url: {init_data}")

    with httpx.Client(timeout=300) as client:
        with open(video_path, "rb") as f:
            resp = client.put(
                upload_url,
                headers={
                    "Content-Range": f"bytes 0-{video_size - 1}/{video_size}",
                    "Content-Type": "video/mp4",
                },
                content=f.read(),
            )
            resp.raise_for_status()

    logger.info("TikTok: video uploaded successfully")
    return {"status": "uploaded", "title": title}


# ============================================================
# Supabase History (replaces Google Sheets)
# ============================================================

def load_history() -> list[dict]:
    """Charge l'historique depuis Supabase (remplace Google Sheets)."""
    return supabase_client.load_recent_history(days=30, platform="tiktok")


def log_to_history(content: dict, duration: float) -> bool:
    """Sauvegarde dans Supabase (remplace Google Sheets)."""
    return supabase_client.save_to_history(content, platform="tiktok")


# Keep old names for backward compat
load_sheet_history = load_history
log_to_sheets = lambda content, duration: log_to_history(content, duration)


# ============================================================
# Log local JSON
# ============================================================

def save_local_log(content: dict, duration: float, video_path: str):
    log = {
        "date": config.get_date_str(),
        "datetime": config.get_datetime_str(),
        "auteur": content.get("auteur", ""),
        "citation": content.get("citation", ""),
        "categorie": content.get("categorie", ""),
        "mood": content.get("mood", ""),
        "hook": content.get("hook", ""),
        "word_count": len(content.get("script_complet", "").split()),
        "duration": round(duration, 1),
        "video_path": video_path,
        "tags": content.get("tags", []),
        "image_count": len(content.get("image_prompts", [])),
    }

    log_path = f"{config.HISTORY_DIR}/{config.get_date_str()}.json"
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    logger.info(f"Local log: {log_path}")
