"""Client Supabase REST API pour l'historique des citations."""
import logging
from datetime import datetime, timedelta
import httpx
from . import config

logger = logging.getLogger("citations-v3")

SUPABASE_URL = "https://supabasekong-q0cooggogcogwo4kg00cc8wo.coolify.inkora.art"
SUPABASE_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJzdXBhYmFzZSIsImlhdCI6MTc3MDkwMTIwMCwiZXhwIjo0OTI2NTc0ODAwLCJyb2xlIjoic2VydmljZV9yb2xlIn0.ylYnPRRPPOUEpzK29ioBy4invpuB6SODaCtsD0HP58o"
TABLE = "citations_history"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}


def load_recent_history(days: int = 30, platform: str | None = None) -> list[dict]:
    """Charge l'historique des N derniers jours depuis Supabase."""
    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    url = f"{SUPABASE_URL}/rest/v1/{TABLE}?date=gte.{since}&order=created_at.desc"
    if platform:
        url += f"&platform=eq.{platform}"
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(url, headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
            })
            resp.raise_for_status()
            rows = resp.json()
            logger.info(f"Supabase: loaded {len(rows)} history rows (last {days} days)")
            return rows
    except Exception as e:
        logger.error(f"Supabase: failed to load history: {e}")
        return []


def get_recent_authors(days: int = 10, platform: str | None = None) -> list[str]:
    """Retourne la liste des auteurs utilises dans les N derniers jours."""
    rows = load_recent_history(days=days, platform=platform)
    authors = []
    seen = set()
    for row in rows:
        a = row.get("auteur", "")
        if a and a not in seen:
            authors.append(a)
            seen.add(a)
    return authors


def save_to_history(content: dict, platform: str = "tiktok", narrative_structure: str = "classic") -> bool:
    """Sauvegarde une generation dans l'historique Supabase."""
    row = {
        "date": config.get_date_str(),
        "platform": platform,
        "auteur": content.get("auteur", ""),
        "citation": content.get("citation", ""),
        "categorie": content.get("categorie", ""),
        "mood": content.get("mood", ""),
        "hook_pattern": content.get("hook", "")[:100] if content.get("hook") else "",
        "narrative_structure": narrative_structure,
    }
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.post(
                f"{SUPABASE_URL}/rest/v1/{TABLE}",
                headers=HEADERS,
                json=row,
            )
            resp.raise_for_status()
            logger.info(f"Supabase: saved {row['auteur']} / {row['platform']}")
            return True
    except Exception as e:
        logger.error(f"Supabase: failed to save: {e}")
        return False


def get_recent_structures(days: int = 10, platform: str = "tiktok") -> list[str]:
    """Retourne les structures narratives utilisees recemment."""
    rows = load_recent_history(days=days, platform=platform)
    return [r.get("narrative_structure", "classic") for r in rows if r.get("narrative_structure")]
