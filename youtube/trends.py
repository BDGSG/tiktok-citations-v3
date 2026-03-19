"""Recherche de tendances web pour enrichir le contenu avec l'actualite."""
import logging
import re
import httpx
from typing import Optional

logger = logging.getLogger("youtube-citations")

# ============================================================
# SOURCES DE TENDANCES
# ============================================================

# Themes perpetuels qui resonnent toujours (fallback si pas de tendance)
EVERGREEN_THEMES = [
    "anxiete et sante mentale",
    "burnout et equilibre vie pro",
    "relations toxiques et solitude",
    "reseaux sociaux et addiction au telephone",
    "peur de l'echec et syndrome de l'imposteur",
    "quete de sens et crise existentielle",
    "procrastination et discipline",
    "deuil et perte d'un proche",
    "confiance en soi et estime de soi",
    "argent et materialisme vs bonheur",
    "comparaison sociale et jalousie",
    "colere et gestion des emotions",
    "lacher prise et acceptation",
    "solitude choisie vs solitude subie",
    "intelligence artificielle et sens du travail",
    "pression sociale et conformisme",
    "gratitude et minimalisme",
    "resilience face a l'adversite",
]


def fetch_trending_topics() -> list[str]:
    """Recupere les sujets tendance actuels via Google Trends RSS.

    Retourne une liste de sujets populaires en France.
    Fallback sur les themes evergreen si echec.
    """
    topics = []

    # Source 1: Google Trends RSS (France)
    try:
        topics.extend(_fetch_google_trends_fr())
    except Exception as e:
        logger.warning(f"Google Trends fetch failed: {e}")

    # Source 2: Tendances Twitter/X France (via RSS bridge ou direct)
    try:
        topics.extend(_fetch_twitter_trends())
    except Exception as e:
        logger.debug(f"Twitter trends fetch failed: {e}")

    if topics:
        logger.info(f"Trending topics found: {len(topics)} — {topics[:5]}")
        return topics[:10]

    # Fallback: themes evergreen
    logger.info("No live trends, using evergreen themes")
    import random
    return random.sample(EVERGREEN_THEMES, min(5, len(EVERGREEN_THEMES)))


def _fetch_google_trends_fr() -> list[str]:
    """Fetch Google Trends daily trends pour la France via RSS."""
    url = "https://trends.google.fr/trending/rss?geo=FR"
    with httpx.Client(timeout=15) as client:
        resp = client.get(url)
        resp.raise_for_status()
        xml = resp.text

    # Parser les titres des tendances
    titles = re.findall(r"<title>([^<]+)</title>", xml)
    # Ignorer le premier titre (titre du feed RSS)
    trends = [t.strip() for t in titles[1:] if t.strip() and "Daily" not in t]
    return trends[:15]


def _fetch_twitter_trends() -> list[str]:
    """Fetch Twitter/X trending topics France (simplified)."""
    # Twitter API requiert auth — on utilise un scraper leger
    # Fallback: retourner vide, les Google Trends suffisent
    return []


def match_trend_to_philosopher(
    trends: list[str],
    philosopher_name: str,
    philosopher_courant: str,
) -> Optional[str]:
    """Trouve la tendance la plus pertinente pour un philosophe donne.

    Retourne le sujet tendance ou None.
    """
    # Mapping themes <-> philosophes
    THEME_AFFINITY = {
        "anxiete": ["Seneque", "Epictete", "Marc Aurele", "Bouddha", "Alan Watts"],
        "mental": ["Marc Aurele", "Viktor Frankl", "Carl Gustav Jung", "Bouddha"],
        "peur": ["Seneque", "Neville Goddard", "Friedrich Nietzsche", "Miyamoto Musashi"],
        "echec": ["Marc Aurele", "Seneque", "Nelson Mandela", "Confucius"],
        "succes": ["Neville Goddard", "Sun Tzu", "Aristote", "Confucius"],
        "amour": ["Rumi", "Khalil Gibran", "Platon", "Lao Tseu"],
        "mort": ["Seneque", "Marc Aurele", "Albert Camus", "Blaise Pascal", "Montaigne"],
        "liberte": ["Jean-Paul Sartre", "Epictete", "Nelson Mandela", "Gandhi"],
        "argent": ["Seneque", "Epictete", "Bouddha", "Voltaire"],
        "travail": ["Confucius", "Aristote", "Friedrich Nietzsche", "Marc Aurele"],
        "guerre": ["Sun Tzu", "Miyamoto Musashi", "Marc Aurele", "Gandhi"],
        "imagination": ["Neville Goddard", "Albert Camus", "Ralph Waldo Emerson"],
        "manifesta": ["Neville Goddard", "Carl Gustav Jung", "Ralph Waldo Emerson"],
        "conscience": ["Neville Goddard", "Carl Gustav Jung", "Bouddha", "Alan Watts"],
        "technolog": ["Seneque", "Blaise Pascal", "Alan Watts", "Albert Camus"],
        "politique": ["Platon", "Aristote", "Voltaire", "Gandhi", "Mandela"],
        "education": ["Socrate", "Platon", "Confucius", "Aristote", "Mandela"],
        "climat": ["Lao Tseu", "Marc Aurele", "Gandhi"],
        "ia": ["Blaise Pascal", "Alan Watts", "Friedrich Nietzsche"],
        "solitude": ["Schopenhauer", "Blaise Pascal", "Friedrich Nietzsche", "Rumi"],
        "resilience": ["Viktor Frankl", "Marc Aurele", "Nelson Mandela", "Epictete"],
        "discipline": ["Miyamoto Musashi", "Epictete", "Bruce Lee", "Sun Tzu"],
        "creativite": ["Neville Goddard", "Friedrich Nietzsche", "Rumi", "Alan Watts"],
        "sport": ["Bruce Lee", "Miyamoto Musashi", "Sun Tzu", "Marc Aurele"],
    }

    best_trend = None
    for trend in trends:
        trend_lower = trend.lower()
        for theme_key, affine_philos in THEME_AFFINITY.items():
            if theme_key in trend_lower:
                if philosopher_name in affine_philos:
                    best_trend = trend
                    break
        if best_trend:
            break

    # Si pas de match par affinite, prendre la premiere tendance pertinente
    if not best_trend and trends:
        best_trend = trends[0]

    return best_trend


def build_trend_context(trend: Optional[str]) -> str:
    """Construit le contexte tendance a injecter dans le prompt LLM.

    Retourne une string a ajouter au prompt, ou string vide.
    """
    if not trend:
        return ""

    return (
        f"\n\nSUJET D'ACTUALITE A INTEGRER :\n"
        f"Le sujet \"{trend}\" est actuellement tendance en France. "
        f"Integre naturellement ce sujet dans l'APPLICATION MODERNE de ton script. "
        f"Fais le lien entre la sagesse du philosophe et ce sujet d'actualite. "
        f"Ne force pas — si le lien est trop artificiel, mentionne-le brievement "
        f"ou utilise-le comme contexte pour illustrer pourquoi cette sagesse est pertinente maintenant."
    )
