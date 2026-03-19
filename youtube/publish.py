"""Publication YouTube — upload OAuth2, Telegram, Google Sheets, log local."""
import json
import os
import base64
import logging
from datetime import datetime, timezone
from pathlib import Path
import httpx
from . import config

logger = logging.getLogger("youtube-citations")


# ============================================================
# YouTube Upload via OAuth2
# ============================================================

def _read_youtube_token() -> dict | None:
    """Lit le token YouTube depuis le fichier ou l'env var YOUTUBE_TOKEN_JSON (base64)."""
    if not os.path.isfile(config.YT_TOKEN_PATH):
        # Essayer de restaurer depuis env var base64
        b64 = os.getenv("YOUTUBE_TOKEN_JSON", "")
        if b64:
            try:
                token_data = base64.b64decode(b64).decode("utf-8")
                Path(config.YT_TOKEN_PATH).parent.mkdir(parents=True, exist_ok=True)
                Path(config.YT_TOKEN_PATH).write_text(token_data)
                logger.info("YouTube: token restored from YOUTUBE_TOKEN_JSON env var")
            except Exception as e:
                logger.error(f"YouTube: failed to decode YOUTUBE_TOKEN_JSON: {e}")
                return None
        else:
            logger.warning(f"YouTube: token file not found: {config.YT_TOKEN_PATH}")
            return None
    with open(config.YT_TOKEN_PATH, "r") as f:
        return json.load(f)


def _refresh_youtube_token(token: dict) -> dict:
    """Rafraichit le token YouTube si expire."""
    with httpx.Client(timeout=30) as client:
        resp = client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": config.YT_CLIENT_ID,
                "client_secret": config.YT_CLIENT_SECRET,
                "refresh_token": token["refresh_token"],
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    if "access_token" not in data:
        raise RuntimeError(f"YouTube token refresh failed: {data}")

    new_token = {
        "access_token": data["access_token"],
        "refresh_token": token["refresh_token"],  # Google ne retourne pas toujours un nouveau refresh
        "expires_in": data.get("expires_in", 3600),
        "token_type": data.get("token_type", "Bearer"),
        "obtained_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": datetime.fromtimestamp(
            datetime.now(timezone.utc).timestamp() + data.get("expires_in", 3600),
            tz=timezone.utc,
        ).isoformat(),
    }

    with open(config.YT_TOKEN_PATH, "w") as f:
        json.dump(new_token, f, indent=2)

    logger.info("YouTube: token refreshed")
    return new_token


def _get_valid_token() -> dict | None:
    """Retourne un token YouTube valide."""
    token = _read_youtube_token()
    if not token:
        return None

    expires_at = token.get("expires_at", "")
    if expires_at:
        exp = datetime.fromisoformat(expires_at)
        if not exp.tzinfo:
            exp = exp.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if now.timestamp() > (exp.timestamp() - 300):
            logger.info("YouTube: token expired, refreshing...")
            try:
                token = _refresh_youtube_token(token)
            except Exception as e:
                logger.error(f"YouTube: token refresh failed: {e}")
                return None

    return token


def upload_youtube(
    video_path: str,
    content: dict,
    thumbnail_path: str | None = None,
    is_short: bool = False,
) -> dict | None:
    """Upload une video sur YouTube en mode prive.

    Args:
        video_path: Chemin vers la video finale
        content: Dictionnaire du contenu genere (yt_title, yt_description, yt_tags, etc.)
        thumbnail_path: Chemin vers la miniature (optionnel)
        is_short: True pour un YouTube Short (pas de merge DEFAULT_VIDEO_TAGS)

    Returns:
        Dictionnaire avec video_id et status, ou None si echec
    """
    token = _get_valid_token()
    if not token:
        logger.warning("YouTube: no valid token, skipping upload")
        return None

    access_token = token["access_token"]
    video_size = os.path.getsize(video_path)

    title = content.get("yt_title", content.get("hook", "Citation du jour"))
    description = content.get("yt_description", "")
    tags = content.get("yt_tags", content.get("tags", []))

    # Assurer que le titre fait max 100 chars
    if len(title) > 100:
        title = title[:97] + "..."

    if is_short:
        # Shorts : tags specifiques, pas de merge avec DEFAULT_VIDEO_TAGS
        # S'assurer que #Shorts est dans le titre pour la classification YouTube
        if "#Shorts" not in title and "#shorts" not in title:
            title = f"{title} #Shorts"
            if len(title) > 100:
                title = title[:97] + "..."
        merged_tags = list(dict.fromkeys(tags))[:15]
        category_id = "22"  # People & Blogs (standard pour Shorts)
    else:
        # Videos longues : merge avec tags SEO par defaut
        from .channel_setup import DEFAULT_VIDEO_TAGS
        merged_tags = list(dict.fromkeys(tags + DEFAULT_VIDEO_TAGS))[:30]
        category_id = "27"  # Education

    # Metadata
    metadata = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": merged_tags,
            "categoryId": category_id,
            "defaultLanguage": "fr",
            "defaultAudioLanguage": "fr",
        },
        "status": {
            "privacyStatus": "private",  # Toujours en prive d'abord
            "selfDeclaredMadeForKids": False,
            "embeddable": True,
            "publicStatsViewable": True,
        },
    }

    # 1. Init resumable upload
    with httpx.Client(timeout=30) as client:
        resp = client.post(
            "https://www.googleapis.com/upload/youtube/v3/videos"
            "?uploadType=resumable&part=snippet,status",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Length": str(video_size),
                "X-Upload-Content-Type": "video/mp4",
            },
            json=metadata,
        )
        resp.raise_for_status()
        upload_url = resp.headers.get("location")

    if not upload_url:
        raise RuntimeError("YouTube: no upload URL returned")

    logger.info(f"YouTube: uploading {video_size / 1024 / 1024:.0f} MB...")

    # 2. Upload video
    with httpx.Client(timeout=1800) as client:
        with open(video_path, "rb") as f:
            resp = client.put(
                upload_url,
                headers={"Content-Type": "video/mp4"},
                content=f.read(),
            )
            resp.raise_for_status()
            upload_data = resp.json()

    video_id = upload_data.get("id")
    logger.info(f"YouTube: video uploaded — ID: {video_id}")

    # 3. Upload thumbnail si disponible
    if thumbnail_path and video_id and os.path.isfile(thumbnail_path):
        try:
            with httpx.Client(timeout=60) as client:
                with open(thumbnail_path, "rb") as f:
                    resp = client.post(
                        f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set"
                        f"?videoId={video_id}",
                        headers={
                            "Authorization": f"Bearer {access_token}",
                            "Content-Type": "image/png",
                        },
                        content=f.read(),
                    )
                    resp.raise_for_status()
            logger.info("YouTube: thumbnail uploaded")
        except Exception as e:
            logger.warning(f"YouTube: thumbnail upload failed (non-blocking): {e}")

    return {"video_id": video_id, "status": "uploaded", "title": title}


# ============================================================
# Telegram
# ============================================================

def send_telegram_text(text: str) -> bool:
    if not config.TELEGRAM_BOT_TOKEN:
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


def send_telegram_notification(content: dict, duration: float, video_path: str, thumbnail_path: str = "") -> bool:
    """Envoie la notification YouTube recapitulative."""
    tags = " ".join(f"#{t}" for t in content.get("tags", []))
    duration_min = duration / 60
    text = (
        f"<b>Citation du Jour — YouTube</b>\n\n"
        f"<b>Titre:</b> {content.get('yt_title', '')}\n\n"
        f'"{content["citation"]}"\n'
        f"— {content['auteur']}\n\n"
        f"<b>Thumbnail:</b> {content.get('thumbnail_text', '')}\n"
        f"<b>Categorie:</b> {content.get('categorie', '')}\n"
        f"<b>Mood:</b> {content.get('mood', '')}\n"
        f"<b>Duree:</b> {duration_min:.1f} min ({duration:.0f}s)\n"
        f"<b>Mots:</b> {len(content['script_complet'].split())}\n"
        f"<b>Images:</b> {len(content.get('image_prompts', []))}\n\n"
        f"{tags}"
    )
    send_telegram_text(text)

    # Envoyer la miniature si disponible
    if thumbnail_path and os.path.isfile(thumbnail_path):
        try:
            url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendPhoto"
            with httpx.Client(timeout=60) as client:
                with open(thumbnail_path, "rb") as f:
                    client.post(url, data={
                        "chat_id": config.TELEGRAM_CHAT_ID,
                        "caption": f"Miniature YouTube : {content.get('yt_title', '')}",
                    }, files={"photo": (Path(thumbnail_path).name, f, "image/png")})
        except Exception as e:
            logger.warning(f"Telegram: thumbnail send failed: {e}")

    return True


def send_telegram_error(error_msg: str) -> bool:
    return send_telegram_text(f"<b>YouTube Citation — ERREUR</b>\n\n{error_msg[:500]}")


# ============================================================
# Google Sheets
# ============================================================

def load_sheet_history() -> list[dict]:
    if not config.GOOGLE_SERVICE_ACCOUNT_JSON:
        logger.warning("Google Sheets: no service account, returning empty history")
        return []
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        sa_info = json.loads(base64.b64decode(config.GOOGLE_SERVICE_ACCOUNT_JSON))
        creds = Credentials.from_service_account_info(
            sa_info, scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        gc = gspread.authorize(creds)
        sheet = gc.open_by_key(config.GOOGLE_SHEETS_ID).sheet1
        records = sheet.get_all_records()
        logger.info(f"Sheets: loaded {len(records)} history rows")
        return records
    except Exception as e:
        logger.error(f"Sheets: failed to load history: {e}")
        return []


def log_to_sheets(content: dict, duration: float) -> bool:
    if not config.GOOGLE_SERVICE_ACCOUNT_JSON:
        return False
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        sa_info = json.loads(base64.b64decode(config.GOOGLE_SERVICE_ACCOUNT_JSON))
        creds = Credentials.from_service_account_info(
            sa_info, scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        gc = gspread.authorize(creds)
        sheet = gc.open_by_key(config.GOOGLE_SHEETS_ID).sheet1

        sheet.append_row([
            config.get_date_str(),
            "youtube",  # plateforme
            content.get("auteur", ""),
            content.get("citation", ""),
            content.get("yt_title", ""),
            content.get("categorie", ""),
            len(content.get("script_complet", "").split()),
            round(duration / 60, 1),  # en minutes
            content.get("mood", ""),
            content.get("epoque", ""),
            content.get("thumbnail_text", ""),
        ])
        logger.info("Sheets: row appended (YouTube)")
        return True
    except Exception as e:
        logger.error(f"Sheets: failed to log: {e}")
        return False


# ============================================================
# Log local JSON
# ============================================================

def save_local_log(content: dict, duration: float, video_path: str, thumbnail_path: str = ""):
    log = {
        "date": config.get_date_str(),
        "datetime": config.get_datetime_str(),
        "platform": "youtube",
        "auteur": content.get("auteur", ""),
        "citation": content.get("citation", ""),
        "yt_title": content.get("yt_title", ""),
        "yt_description": content.get("yt_description", ""),
        "yt_tags": content.get("yt_tags", []),
        "thumbnail_text": content.get("thumbnail_text", ""),
        "categorie": content.get("categorie", ""),
        "mood": content.get("mood", ""),
        "hook": content.get("hook", ""),
        "word_count": len(content.get("script_complet", "").split()),
        "duration_seconds": round(duration, 1),
        "duration_minutes": round(duration / 60, 1),
        "video_path": video_path,
        "thumbnail_path": thumbnail_path,
        "tags": content.get("tags", []),
        "image_count": len(content.get("image_prompts", [])),
        "chapitres": content.get("chapitres", []),
    }

    log_path = f"{config.YT_HISTORY_DIR}/{config.get_date_str()}_youtube.json"
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    logger.info(f"Local log: {log_path}")
