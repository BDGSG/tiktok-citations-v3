"""Generation de contenu Shorts Sagesse via Claude (OpenRouter) avec exclusion Supabase."""
import json
import re
import random
import logging
import httpx
from . import config
from app import supabase_client

logger = logging.getLogger("shorts-sagesse")

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
        "max_tokens": 2048,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ],
    }

    with httpx.Client(timeout=120) as client:
        resp = client.post(OPENROUTER_URL, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()

    if "choices" not in data:
        error_msg = data.get("error", {}).get("message", str(data))
        raise RuntimeError(f"OpenRouter API error: {error_msg}")

    return data["choices"][0]["message"]["content"]


def _build_shorts_exclusion() -> str:
    """Charge l'historique des shorts depuis Supabase et construit le texte d'exclusion."""
    history = supabase_client.load_recent_history(days=14, platform="shorts")
    if not history:
        return ""
    lines = ["CONTENUS DEJA GENERES RECEMMENT (ne JAMAIS repeter les memes idees/themes) :"]
    for row in history:
        citation = row.get("citation", "")
        if citation:
            lines.append(f"- {citation[:100]}")
    return "\n".join(lines)


SYSTEM_PROMPTS = {
    "idee": """Tu es un penseur moderne au style percutant, comme un stoicien du XXIe siecle.
Ecris UNE IDEE puissante et CONTRARIANTE en 50-90 mots.
COMMENCE par une affirmation choc qui remet en cause une croyance populaire.
Puis developpe en 2-3 phrases pourquoi cette idee change tout.
Style: grave, tutoiement, phrases courtes, zero cliche, zero remplissage.
Accents francais obligatoires. Nombres en lettres.
Applique cette idee a un probleme MODERNE (anxiete, reseaux sociaux, burnout, relations).
PAS de citation d'auteur — c'est TA reflexion originale.
Format: texte brut uniquement.""",

    "situation": """Tu es un sage pragmatique qui comprend les galeres de la vie moderne.
Structure en 2 parties, 60-100 mots total :
PARTIE 1 — Decris une SITUATION DE VIE precise et douloureuse que tout le monde connait.
Sois concret : pas "tu souffres" mais "tu te reveilles a trois heures du matin avec la boule au ventre".
PARTIE 2 — Donne LE conseil qui change tout. Un seul. Precis. Actionnable immediatement.
Style: empathique puis ferme, tutoiement, accents francais obligatoires, nombres en lettres.
Format de reponse (texte brut) :
SITUATION: [2-3 phrases concretes et viscerales]
---
CONSEIL: [le conseil cle, 2-4 phrases, actionnable]""",

    "conseil": """Tu es un philosophe intemporel qui parle comme un mentor bienveillant mais direct.
Ecris UN CONSEIL DE SAGESSE en 50-90 mots.
Ce conseil doit satisfaire DEUX criteres :
1. Un sage de l'Antiquite l'aurait approuve
2. Il resout un probleme d'AUJOURD'HUI (procrastination, comparaison sociale, peur de l'echec, surmenage)
COMMENCE par une phrase courte et percutante (le hook).
Puis developpe avec un exemple concret.
Style: grave, tutoiement, zero platitude, zero cliche motivationnel.
Accents francais obligatoires. Nombres en lettres.
PAS de citation — c'est un conseil original.
Format: texte brut uniquement.""",
}

USER_PROMPTS = {
    "idee": "Partage une idee CONTRARIANTE sur un de ces sujets : pourquoi la discipline bat la motivation, pourquoi la souffrance est un outil, pourquoi le confort detruit, pourquoi la solitude rend fort, pourquoi les reseaux sociaux sont une prison doree. Surprends-moi avec un angle que personne n'utilise.",
    "situation": "Choisis UNE situation parmi : tu scrolles a trois heures du matin, tu restes dans une relation par peur de la solitude, tu repousses le projet qui te tient a coeur, tu dis oui a tout le monde sauf a toi, tu te compares aux autres sur les reseaux, tu te leves sans savoir pourquoi. Sois VISCERAL dans la description.",
    "conseil": "Donne un conseil que Marc Aurele, Seneque ou Epictete auraient donne a quelqu'un qui souffre de : anxiete de performance, burnout, syndrome de l'imposteur, peur du jugement, ou paralysie du choix. Formule-le avec tes propres mots, comme si tu parlais a un ami.",
}


def generate_content() -> dict:
    """Genere le contenu d'un Short Sagesse avec exclusion Supabase."""
    content_type = random.choice(config.CONTENT_TYPES)
    logger.info(f"Shorts: generating '{content_type}' content")

    # Build exclusion text from Supabase history
    exclusion = _build_shorts_exclusion()

    system = SYSTEM_PROMPTS[content_type]
    user_msg = USER_PROMPTS[content_type]
    if exclusion:
        user_msg = f"{exclusion}\n\n{user_msg}"

    raw = _call_claude(system, user_msg)

    # Parser selon le type
    if content_type == "situation" and "---" in raw:
        parts = raw.split("---", 1)
        situation = parts[0].strip()
        conseil = parts[1].strip()
        situation = re.sub(r"^SITUATION\s*:\s*", "", situation, flags=re.I).strip()
        conseil = re.sub(r"^CONSEIL\s*:\s*", "", conseil, flags=re.I).strip()
        script = f"{situation} [Pause] {conseil}"
        hook_text = situation[:60].split(".")[0] + "..."
    else:
        script = raw.strip()
        script = script.strip('"').strip("\u00ab").strip("\u00bb").strip()
        hook_text = script[:50].split(".")[0]

    # Nettoyer
    script = re.sub(r"\[Pause[^\]]*\]", "", script, flags=re.I)
    script = re.sub(r"\s+", " ", script).strip()

    word_count = len(script.split())
    logger.info(f"Shorts: {content_type} | {word_count} mots")

    if word_count < 15:
        raise ValueError(f"Script trop court: {word_count} mots")
    if word_count > 150:
        words = script.split()[:120]
        script = " ".join(words)
        last_punct = max(script.rfind("."), script.rfind("!"), script.rfind("?"))
        if last_punct > len(script) // 2:
            script = script[:last_punct + 1]

    # Generer image prompt
    image_prompt = _generate_image_prompt(script, content_type)

    # Tags
    type_tags = {
        "idee": ["reflexion", "pensee", "inspiration"],
        "situation": ["conseils", "coachdevie", "resilience"],
        "conseil": ["sagesse", "philosophie", "developpementpersonnel"],
    }

    mood = random.choice(["contemplative", "dark_motivation", "resilience"])

    result = {
        "content_type": content_type,
        "script_complet": script,
        "hook_text": hook_text,
        "image_prompts": [image_prompt],
        "tags": ["sagesse", "shorts", "motivation"] + type_tags.get(content_type, []),
        "mood": mood,
        "takeaway": script[:80],
        # Fields for Supabase logging
        "auteur": f"shorts_{content_type}",
        "citation": script[:200],
        "categorie": content_type,
    }

    # Save to Supabase
    supabase_client.save_to_history(result, platform="shorts")

    return result


def _generate_image_prompt(script: str, content_type: str) -> str:
    """Genere un prompt d'image en anglais pour le Short."""
    try:
        system = "Generate a single cinematic image prompt in English for a vertical 9:16 video. Dark moody style. Return ONLY the prompt text, no quotes, no JSON."
        user = f"Script: {script[:200]}\nType: {content_type}\nGenerate one cinematic 9:16 image prompt."
        raw = _call_claude(system, user)
        prompt = raw.strip().strip('"')
        if len(prompt) > 20:
            return prompt
    except Exception as e:
        logger.warning(f"Image prompt generation failed: {e}")

    fallbacks = [
        "silhouette of person on mountain top at sunset, dramatic sky, dark moody cinematic, 9:16 vertical",
        "close-up of weathered hands in prayer position, dramatic lighting, cinematic shadows, 9:16 vertical",
        "lone tree on cliff edge in storm, dramatic atmosphere, teal orange grading, 9:16 vertical",
        "person walking through dark forest with light ahead, cinematic, moody, 9:16 vertical",
        "sunrise through storm clouds over ocean, dramatic golden light, cinematic, 9:16 vertical",
    ]
    return random.choice(fallbacks)
