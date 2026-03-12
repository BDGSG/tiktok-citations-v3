"""Configuration de la chaine YouTube via API — SEO, branding, parametres par defaut.

Usage:
    POST /setup/youtube-channel  (endpoint dans main.py)
    ou directement: python -m youtube.channel_setup
"""
import json
import logging
import httpx
from . import config
from . import publish as publish_mod

logger = logging.getLogger("youtube-citations")

# ============================================================
# Donnees SEO optimisees pour la chaine "Citation du Jour"
# ============================================================

CHANNEL_DESCRIPTION = (
    "Citations de philosophie, sagesse stoïcienne et pensées inspirantes "
    "pour transformer votre quotidien.\n\n"
    "Chaque jour, découvrez les enseignements des plus grands philosophes : "
    "Marc Aurèle, Sénèque, Épictète, Platon, Nietzsche, Confucius, Sartre, "
    "Camus, Montaigne, Lao Tseu...\n\n"
    "Du stoïcisme au développement personnel, nos vidéos vous guident "
    "vers une vie plus sereine, plus forte et plus épanouie. "
    "Visuels cinématiques, voix-off profonde, sagesse intemporelle.\n\n"
    "Nouveau contenu chaque jour.\n"
    "Abonnez-vous et activez la cloche 🔔 pour ne rien manquer.\n\n"
    "#Citations #Philosophie #Sagesse #Stoïcisme #DéveloppementPersonnel"
)

CHANNEL_KEYWORDS = (
    '"citations philosophiques" "citation du jour" philosophie sagesse stoicisme '
    '"marc aurele" seneque epictete "developpement personnel" motivation '
    '"citations inspirantes" "philosophie de vie" "sagesse antique" '
    '"pensees positives" "citations motivation" "lecons de vie" '
    '"philosophie stoicienne" "citations celebres" "sagesse stoicienne" '
    'meditation resilience "art de vivre" confiance psychologie '
    '"croissance personnelle" "citations francaises" "citation du jour"'
)

# Tags par defaut pour chaque video (inclus automatiquement)
DEFAULT_VIDEO_TAGS = [
    "citations", "philosophie", "sagesse", "stoicisme", "motivation",
    "developpement personnel", "citations inspirantes", "lecons de vie",
    "philosophie de vie", "pensees positives", "sagesse antique",
    "resilience", "confiance en soi", "art de vivre",
    "citations francaises", "bien-etre mental", "citation du jour",
    "marc aurele", "seneque", "epictete",
]

# Categorie Education = 27
VIDEO_CATEGORY_ID = "27"


def configure_channel() -> dict:
    """Configure la chaine YouTube : description, keywords, branding."""
    token = publish_mod._get_valid_token()
    if not token:
        raise RuntimeError("YouTube: no valid token for channel setup")

    access_token = token["access_token"]
    results = {}

    # 1. Recuperer le channel ID
    with httpx.Client(timeout=30) as client:
        resp = client.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={"part": "id,snippet,brandingSettings,status", "mine": "true"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        data = resp.json()

    if not data.get("items"):
        raise RuntimeError("YouTube: no channel found for this account")

    channel = data["items"][0]
    channel_id = channel["id"]
    results["channel_id"] = channel_id
    results["current_title"] = channel.get("snippet", {}).get("title", "")
    logger.info(f"YouTube channel: {results['current_title']} (ID: {channel_id})")

    # 2. Mettre a jour brandingSettings (description, keywords, pays)
    branding = channel.get("brandingSettings", {})
    branding_channel = branding.get("channel", {})

    branding_channel["description"] = CHANNEL_DESCRIPTION
    branding_channel["keywords"] = CHANNEL_KEYWORDS
    branding_channel["country"] = "FR"
    branding_channel["defaultLanguage"] = "fr"

    # Default tab = videos
    branding_channel["defaultTab"] = "videos"
    branding_channel["trackingAnalyticsAccountId"] = ""

    branding["channel"] = branding_channel

    with httpx.Client(timeout=30) as client:
        resp = client.put(
            "https://www.googleapis.com/youtube/v3/channels",
            params={"part": "brandingSettings"},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={
                "id": channel_id,
                "brandingSettings": branding,
            },
        )
        resp.raise_for_status()
        results["branding_updated"] = True
        logger.info("YouTube: channel branding updated (description, keywords, country)")

    # 3. Mettre a jour les localisations (snippet)
    with httpx.Client(timeout=30) as client:
        resp = client.put(
            "https://www.googleapis.com/youtube/v3/channels",
            params={"part": "localizations"},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={
                "id": channel_id,
                "localizations": {
                    "fr": {
                        "title": "Citation du Jour",
                        "description": CHANNEL_DESCRIPTION,
                    },
                },
            },
        )
        resp.raise_for_status()
        results["localizations_updated"] = True
        logger.info("YouTube: channel localizations updated (FR)")

    results["status"] = "ok"
    results["description_length"] = len(CHANNEL_DESCRIPTION)
    results["keywords_count"] = len(CHANNEL_KEYWORDS.split('"')) // 2
    results["default_tags_count"] = len(DEFAULT_VIDEO_TAGS)
    results["video_category"] = VIDEO_CATEGORY_ID

    logger.info(
        f"YouTube channel setup complete: "
        f"desc={results['description_length']}c, "
        f"keywords={results['keywords_count']}, "
        f"tags={results['default_tags_count']}"
    )
    return results


def get_channel_info() -> dict:
    """Retourne les infos actuelles de la chaine YouTube."""
    token = publish_mod._get_valid_token()
    if not token:
        return {"error": "no valid token"}

    access_token = token["access_token"]

    with httpx.Client(timeout=30) as client:
        resp = client.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={
                "part": "id,snippet,brandingSettings,statistics,status",
                "mine": "true",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        data = resp.json()

    if not data.get("items"):
        return {"error": "no channel found"}

    ch = data["items"][0]
    return {
        "channel_id": ch["id"],
        "title": ch.get("snippet", {}).get("title", ""),
        "description": ch.get("snippet", {}).get("description", ""),
        "custom_url": ch.get("snippet", {}).get("customUrl", ""),
        "country": ch.get("snippet", {}).get("country", ""),
        "subscribers": ch.get("statistics", {}).get("subscriberCount", "0"),
        "videos": ch.get("statistics", {}).get("videoCount", "0"),
        "views": ch.get("statistics", {}).get("viewCount", "0"),
        "keywords": ch.get("brandingSettings", {}).get("channel", {}).get("keywords", ""),
        "branding_description": ch.get("brandingSettings", {}).get("channel", {}).get("description", ""),
    }


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) > 1 and sys.argv[1] == "info":
        info = get_channel_info()
        print(json.dumps(info, indent=2, ensure_ascii=False))
    else:
        result = configure_channel()
        print(json.dumps(result, indent=2, ensure_ascii=False))
