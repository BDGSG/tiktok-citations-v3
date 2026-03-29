"""Generation de contenu via Claude (OpenRouter) — prompt 7 parties, 400-700 mots, rotation auteurs + structures."""
import json
import re
import random
import logging
from pathlib import Path
import httpx
from . import config
from . import supabase_client

logger = logging.getLogger("citations-v3")

# --- Philosopher database ---
_PHILOSOPHERS_PATH = Path(__file__).parent / "data" / "philosophers.json"
_philosophers_cache: list[dict] | None = None


def _load_philosophers() -> list[dict]:
    global _philosophers_cache
    if _philosophers_cache is None:
        with open(_PHILOSOPHERS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        _philosophers_cache = data["thinkers"]
        logger.info(f"Philosophers: loaded {len(_philosophers_cache)} thinkers")
    return _philosophers_cache


# --- Narrative structures ---
NARRATIVE_STRUCTURES = {
    "classic": {
        "label": "Classique (7 parties)",
        "description": """## STRUCTURE NARRATIVE — CLASSIQUE (7 parties)
1. LE CROCHET (0-3s, 10-20 mots) — Phrase CHOC qui arrete le scroll
2. LA PROMESSE (3-15s, 30-50 mots) — Ce que le spectateur va gagner
3. L'HISTOIRE (15s-1min, 80-120 mots) — Contexte historique, personnage, epoque
4. LE MESSAGE CENTRAL (1-2min, 100-150 mots) — La citation expliquee, decortiquee
5. L'APPROFONDISSEMENT (2-3min, 100-150 mots) — Applications vie moderne
6. LE CLIMAX EMOTIONNEL (3-4min, 60-80 mots) — Revelation finale, phrases courtes
7. CONCLUSION + CTA (4-5min, 40-60 mots) — Boucle avec le hook, question ouverte""",
    },
    "debate": {
        "label": "Débat",
        "description": """## STRUCTURE NARRATIVE — DEBAT
1. LA QUESTION (0-5s, 15-25 mots) — Pose une question existentielle que tout le monde se pose
2. ARGUMENTS POUR (5-45s, 80-120 mots) — Developpe le point de vue populaire/accepte
3. ARGUMENTS CONTRE (45s-1m30, 80-120 mots) — Demonte avec des faits, des exemples
4. LA CITATION COMME REPONSE (1m30-3min, 100-150 mots) — L'auteur tranche le debat
5. RESOLUTION (3-4min, 60-80 mots) — Synthese + ce que ca change concretement + CTA""",
    },
    "what_if": {
        "label": "Et si...?",
        "description": """## STRUCTURE NARRATIVE — ET SI...?
1. LE SCENARIO (0-10s, 20-30 mots) — "Imagine que..." scenario hypothetique puissant
2. L'EXPLORATION (10s-1min, 100-130 mots) — Developpe le scenario, consequences
3. LA REVELATION (1-2min, 100-150 mots) — La citation comme verite cachee derriere le scenario
4. L'IMPACT REEL (2-3min, 80-120 mots) — Comment cette verite s'applique a ta vie MAINTENANT
5. LE RETOUR (3-4min, 50-70 mots) — Reviens au scenario initial, tout a change + CTA""",
    },
    "letter": {
        "label": "Lettre",
        "description": """## STRUCTURE NARRATIVE — LETTRE (format epistolaire)
1. L'ADRESSE (0-5s, 15-20 mots) — "Cher spectateur..." ou "A toi qui..." accroche intime
2. LE CONSTAT (5-45s, 80-100 mots) — Decris ce que tu observes chez le spectateur (ses doutes, ses peurs)
3. LA SAGESSE (45s-2min, 100-150 mots) — La citation + son explication, comme un conseil personnel
4. LA REFLEXION (2-3min, 80-120 mots) — Partage ta propre interpretation, ton vecu
5. LA SIGNATURE (3-4min, 40-60 mots) — Conclus la lettre avec une derniere pensee + CTA""",
    },
    "countdown": {
        "label": "Countdown",
        "description": """## STRUCTURE NARRATIVE — COUNTDOWN
1. L'ANNONCE (0-5s, 15-25 mots) — "Trois verites que..." ou "Cinq raisons pour lesquelles..." accroche numerotee
2. POINT 1 (5-30s, 60-80 mots) — Premier element, le plus accessible
3. POINT 2 (30s-1min, 60-80 mots) — Deuxieme element, plus profond
4. POINT 3 + CITATION (1-2min, 100-150 mots) — Troisieme element = la citation, le plus puissant
5. SYNTHESE (2-3min, 60-80 mots) — Relie les 3 points, vision globale + CTA""",
    },
}


def _pick_narrative_structure() -> str:
    """Choisit une structure narrative non utilisee recemment."""
    recent = supabase_client.get_recent_structures(days=10, platform="tiktok")
    all_keys = list(NARRATIVE_STRUCTURES.keys())

    # Filtrer les structures utilisees recemment
    unused = [k for k in all_keys if k not in recent]
    if not unused:
        # Toutes utilisees — prendre la moins recente
        counts = {k: recent.count(k) for k in all_keys}
        unused = [k for k in all_keys if counts.get(k, 0) == min(counts.values())]

    return random.choice(unused)


def _pick_candidate_authors(count: int = 5) -> list[dict]:
    """Selectionne des auteurs candidats NON utilises recemment."""
    philosophers = _load_philosophers()
    recent_authors = supabase_client.get_recent_authors(days=10, platform="tiktok")
    recent_set = set(a.lower() for a in recent_authors)

    # Filtrer les philosophes non utilises recemment
    available = [p for p in philosophers if p["name"].lower() not in recent_set]

    if len(available) < count:
        # Pas assez — prendre tous les disponibles + random des recents
        available = philosophers.copy()

    # Diversifier les categories
    by_cat = {}
    for p in available:
        by_cat.setdefault(p["category"], []).append(p)

    candidates = []
    cats = list(by_cat.keys())
    random.shuffle(cats)
    for cat in cats:
        if len(candidates) >= count:
            break
        pick = random.choice(by_cat[cat])
        candidates.append(pick)

    # Completer si necessaire
    while len(candidates) < count and available:
        pick = random.choice(available)
        if pick not in candidates:
            candidates.append(pick)

    return candidates[:count]


SYSTEM_PROMPT_TEMPLATE = r"""Tu es un createur TikTok viral francais specialise en motivation, philosophie et developpement personnel. Tu produis des contenus au niveau des meilleurs comptes TikTok motivation (Motiversity, deepstrongquotes, stoicis_mind).

# MISSION
Genere un MINI-ESSAI philosophique de 2 a 5 minutes. Le script sera lu a voix haute (vitesse 0.88x, voix masculine grave). Tu DOIS ecrire entre 400 et 700 mots dans le champ script_complet.

# AUTEUR OBLIGATOIRE
Tu DOIS choisir UN de ces auteurs pour la citation :
{author_choices}
NE CHOISIS PAS un autre auteur. C'est OBLIGATOIRE.

# {structure_description}

# PATTERNS DE HOOK (utilise un de ceux-ci) :
- AFFIRMATION CONTRARIANTE : "Tout ce que tu crois savoir sur le bonheur est faux."
- QUESTION DIRECTE : "Pourquoi l'homme le plus puissant de Rome ecrivait ceci a trois heures du matin ?"
- PATTERN 'MOST PEOPLE' : "La plupart des gens ne comprendront jamais cette phrase."
- CHOC ATTRIBUE : "Un mot. Un seul mot de Seneque a detruit ma peur de l'echec."
JAMAIS de "Salut", "Hey", "Bienvenue". Frappe DIRECT.

# FORMAT JSON STRICT
Retourne UNIQUEMENT un objet JSON valide. Pas de markdown, pas de backticks, pas de texte avant ou apres.

{{
  "hook": "Question choc (8-15 mots)",
  "citation": "La citation complete",
  "auteur": "Nom de l'auteur (DOIT etre un des auteurs proposes ci-dessus)",
  "epoque": "Epoque/contexte (ex: Rome, 65 apr. J-C)",
  "takeaway": "Lecon percutante en 15-25 mots",
  "script_complet": "Le script narration complet (400-700 mots). Utilise [Pause] pour marquer les silences strategiques (5-8 par script).",
  "hook_text": "Texte court affiche 3 premieres secondes (5-8 mots max)",
  "image_prompts": ["prompt 1 en anglais", "prompt 2", "... (exactement 10 prompts ultra-detailles)"],
  "categorie": "stoicisme | philosophie | business | spiritualite | psychologie",
  "tags": ["mot1", "mot2", "mot3", "mot4", "mot5", "mot6", "mot7", "mot8"],
  "cta_text": "Phrase d'appel a l'action finale",
  "mood": "dark_motivation | contemplative | warrior | rebirth | resilience"
}}

# REGLES IMAGE PROMPTS (exactement 10, en anglais)
IMPORTANT : Exactement 10 images, pas plus, pas moins.
Chaque prompt doit etre ULTRA-DETAILLE (40-80 mots minimum par prompt). Decris precisement :
- Le SUJET principal (personnage, objet, scene)
- La COMPOSITION (angle de camera, plan large/serre, profondeur de champ)
- L'ECLAIRAGE precis (direction, couleur, intensite, ombres)
- L'AMBIANCE et les DETAILS d'environnement (textures, materiaux, meteo, particules)
- Le STYLE visuel (reference cinematographique, photographe, epoque)

Style de base a integrer dans chaque prompt :
"dark moody cinematic lighting, dramatic shadows, teal and orange color grading, 4k ultrarealistic photography, shot on ARRI Alexa, anamorphic lens flare, shallow depth of field, no text no words no writing no watermark"

Correspondance obligatoire narration/images :
- Image 1 : CROCHET — scene d'ouverture iconique
- Image 2 : PROMESSE — tension, anticipation
- Image 3-4 : HISTOIRE — reconstitution epoque, personnage
- Image 5-6 : MESSAGE CENTRAL — metaphores visuelles puissantes
- Image 7-8 : APPROFONDISSEMENT — connexion vie moderne
- Image 9 : CLIMAX — intensite maximale
- Image 10 : CONCLUSION — lumiere, espoir

# REGLE ABSOLUE SUR LES ACCENTS
Tu DOIS OBLIGATOIREMENT utiliser TOUS les accents francais.
JAMAIS ecrire sans accents.

# REGLE ABSOLUE SUR LES NOMBRES
Tu DOIS ecrire TOUS les nombres en LETTRES dans le script_complet.

# REGLE SUR LES MOTS ANGLAIS
Dans script_complet, ecris les mots anglais en phonetique francaise :
- "mindset" -> "maindsete" | "burnout" -> "beurnaoute"

# STYLE
- Phrases COURTES pour la tension (5-10 mots)
- Phrases LONGUES pour la reflexion (15-25 mots)
- Tutoiement OBLIGATOIRE
- Ton : mentor dur mais bienveillant
- [Pause] = silence avant les phrases puissantes (5-8 par script)
- ZERO remplissage, CHAQUE mot doit compter

VERIFIE : script_complet fait-il 400-700 mots ? TOUS les accents ? AUCUN chiffre arabe ? Mots anglais en phonetique ? Exactement 10 image_prompts ultra-detailles ?"""


# --- OpenRouter (Claude) ---
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_KEY = "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"
OPENROUTER_MODEL = "anthropic/claude-3.5-haiku"


def _call_claude(system: str, user_prompt: str) -> str:
    """Appelle Claude via OpenRouter."""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://citations-v3.coolify.inkora.art",
    }
    body = {
        "model": OPENROUTER_MODEL,
        "max_tokens": 8192,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ],
    }

    logger.info(f"Calling Claude via OpenRouter ({OPENROUTER_MODEL})...")
    with httpx.Client(timeout=180) as client:
        resp = client.post(OPENROUTER_URL, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()

    if "choices" not in data:
        error_msg = data.get("error", {}).get("message", str(data))
        raise RuntimeError(f"OpenRouter API error: {error_msg}")

    return data["choices"][0]["message"]["content"]


def build_exclusion_text(history: list[dict]) -> str:
    """Construit le texte d'exclusion a partir de l'historique."""
    if not history:
        return ""
    lines = ["CITATIONS DEJA UTILISEES (ne JAMAIS les repeter) :"]
    authors_seen = set()
    for row in history:
        author = row.get("auteur", "")
        citation = row.get("citation", "")
        if citation:
            lines.append(f"- \"{citation}\" — {author}")
        if author:
            authors_seen.add(author)
    if authors_seen:
        lines.append(f"\nAuteurs deja cites recemment : {', '.join(authors_seen)}")
        lines.append("Privilegie des auteurs DIFFERENTS si possible.")
    return "\n".join(lines)


def generate_content(exclusion_text: str = "") -> dict:
    """Genere le contenu avec rotation auteurs et structures narratives."""
    # Pick narrative structure
    structure_key = _pick_narrative_structure()
    structure = NARRATIVE_STRUCTURES[structure_key]
    logger.info(f"Content: using narrative structure '{structure_key}' ({structure['label']})")

    # Pick candidate authors
    candidates = _pick_candidate_authors(5)
    author_choices = "\n".join(
        f"- {c['name']} ({c['category']}, {c['era']}) — connu pour : {c['famous_for']}. Themes : {', '.join(c['key_themes'])}"
        for c in candidates
    )
    logger.info(f"Content: candidate authors: {[c['name'] for c in candidates]}")

    # Build system prompt
    system = SYSTEM_PROMPT_TEMPLATE.format(
        author_choices=author_choices,
        structure_description=structure["description"],
    )

    user_prompt = f"""Cree le contenu TikTok motivationnel/philosophique du jour.

{exclusion_text}

INSTRUCTIONS :
1. script_complet entre 400 et 700 mots
2. Exactement 10 image_prompts ULTRA-DETAILLES (40-80 mots chacun) en anglais
3. Suis la structure narrative indiquee dans le system prompt
4. Hook qui arrete le scroll
5. JAMAIS la meme citation que celles listees ci-dessus
6. Tags = mots-cles SANS espaces, minuscules, pour hashtags TikTok
7. TOUS les accents francais OBLIGATOIRES
8. TOUS les nombres en LETTRES
9. Mots anglais en phonetique francaise dans script_complet
10. mood = l'ambiance globale de la video
11. Chaque image_prompt doit decrire composition, eclairage, ambiance, sujet, style en detail
12. CHOISIS un des auteurs proposes dans le system prompt

Retourne UNIQUEMENT le JSON, sans backticks, sans texte avant ou apres."""

    # Try up to 2 times to ensure author compliance
    candidate_names = {c["name"].lower() for c in candidates}
    for attempt in range(2):
        raw_text = _call_claude(system, user_prompt)
        content = _parse_json(raw_text)
        content = _validate(content)

        # Check author is in candidates
        chosen_author = content.get("auteur", "").lower()
        if any(chosen_author in name or name in chosen_author for name in candidate_names):
            logger.info(f"Content: author '{content['auteur']}' matches candidates (attempt {attempt+1})")
            break
        else:
            if attempt == 0:
                logger.warning(f"Content: author '{content['auteur']}' not in candidates, retrying...")
            else:
                logger.warning(f"Content: author '{content['auteur']}' still not in candidates, accepting anyway")

    # Save to Supabase
    supabase_client.save_to_history(content, platform="tiktok", narrative_structure=structure_key)

    logger.info(
        f"Content generated: {content['auteur']} | "
        f"{len(content['script_complet'].split())} words | "
        f"{len(content['image_prompts'])} images | "
        f"structure={structure_key}"
    )
    return content


def _parse_json(text: str) -> dict:
    """Extrait le JSON de la reponse Claude (avec ou sans backticks)."""
    cleaned = re.sub(r"```(?:json)?\s*", "", text)
    cleaned = re.sub(r"```\s*$", "", cleaned)
    cleaned = cleaned.strip()
    return json.loads(cleaned)


def _validate(content: dict) -> dict:
    """Valide et enrichit le contenu genere."""
    required = ["hook", "citation", "auteur", "script_complet", "image_prompts"]
    for field in required:
        if field not in content:
            raise ValueError(f"Champ manquant: {field}")

    words = content["script_complet"].split()
    word_count = len(words)
    if word_count < config.SCRIPT_MIN_WORDS:
        raise ValueError(f"Script trop court: {word_count} mots (min {config.SCRIPT_MIN_WORDS})")
    if word_count > config.SCRIPT_MAX_WORDS + 50:
        logger.warning(f"Script un peu long: {word_count} mots (max {config.SCRIPT_MAX_WORDS})")

    if len(content["image_prompts"]) < config.MIN_IMAGE_PROMPTS:
        raise ValueError(
            f"Pas assez d'image prompts: {len(content['image_prompts'])} "
            f"(min {config.MIN_IMAGE_PROMPTS})"
        )

    accent_words = ["verite", "echec", "reussite", "lecon", "difference", "strategie"]
    script = content["script_complet"].lower()
    missing = [w for w in accent_words if w in script]
    if len(missing) > 2:
        logger.warning(f"Accents potentiellement manquants: {missing}")

    content.setdefault("hook_text", "")
    content.setdefault("cta_text", "Save cette video")
    content.setdefault("categorie", "philosophie")
    content.setdefault("tags", [])
    content.setdefault("mood", "dark_motivation")
    content.setdefault("epoque", "")

    return content
