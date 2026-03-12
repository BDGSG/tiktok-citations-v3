"""Generation de contenu Shorts Sagesse via Kie.ai (DeepSeek)."""
import json
import re
import random
import logging
import httpx
from . import config

logger = logging.getLogger("shorts-sagesse")

KIE_CHAT_URL = "https://api.kie.ai/api/v1/chat/completions"


def _call_kie_llm(system: str, user_prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {config.KIE_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": "deepseek-chat",
        "max_tokens": 2048,
        "temperature": 0.9,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ],
    }

    with httpx.Client(timeout=120) as client:
        resp = client.post(KIE_CHAT_URL, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()

    if "choices" not in data:
        error_msg = data.get("msg", data.get("message", str(data)))
        raise RuntimeError(f"Kie.ai API error: {error_msg}")

    return data["choices"][0]["message"]["content"]


SYSTEM_PROMPTS = {
    "idee": """Tu es un sage moderne qui partage des reflexions profondes en francais.
Ecris UNE IDEE puissante et originale en 40-80 mots.
Style: direct, tutoiement, percutant, zero remplissage.
Accents francais obligatoires. Nombres en lettres.
PAS de citation d'auteur — c'est TA reflexion originale.
Format: texte brut, pas de guillemets, pas de JSON.""",

    "situation": """Tu es un coach de vie sage et bienveillant qui parle francais.
Decris UNE SITUATION DE VIE courante et difficile, puis donne LE CONSEIL cle pour en sortir.
Total: 50-100 mots maximum.
Style: direct, tutoiement, empathique puis percutant.
Accents francais obligatoires. Nombres en lettres.
Format de reponse (texte brut) :
SITUATION: [description en 1-2 phrases]
---
CONSEIL: [comment en sortir, 2-4 phrases]""",

    "conseil": """Tu es un philosophe intemporel qui partage sa sagesse en francais.
Ecris UN CONSEIL DE SAGESSE eprouve et universel en 40-80 mots.
Ce conseil doit etre applicable a toutes les epoques, toutes les cultures.
Style: grave, tutoiement, pas de cliche, pas de platitudes.
Accents francais obligatoires. Nombres en lettres.
PAS de citation — c'est un conseil original formule par toi.
Format: texte brut, pas de guillemets, pas de JSON.""",
}

USER_PROMPTS = {
    "idee": "Partage une idee profonde et originale sur la vie, le bonheur, la souffrance, le courage, ou le sens de l'existence. Sois surprenant.",
    "situation": "Decris une situation de vie difficile mais courante (perte de confiance, relation toxique, peur du changement, epuisement, echec, solitude, procrastination, etc.) et donne le conseil cle pour en sortir.",
    "conseil": "Donne un conseil de sagesse intemporel et eprouve. Quelque chose que les sages de toutes les epoques auraient approuve. Sois profond, pas cliche.",
}


def generate_content() -> dict:
    """Genere le contenu d'un Short Sagesse."""
    content_type = random.choice(config.CONTENT_TYPES)
    logger.info(f"Shorts: generating '{content_type}' content")

    raw = _call_kie_llm(SYSTEM_PROMPTS[content_type], USER_PROMPTS[content_type])

    # Parser selon le type
    if content_type == "situation" and "---" in raw:
        parts = raw.split("---", 1)
        situation = parts[0].strip()
        conseil = parts[1].strip()
        # Nettoyer prefixes
        situation = re.sub(r"^SITUATION\s*:\s*", "", situation, flags=re.I).strip()
        conseil = re.sub(r"^CONSEIL\s*:\s*", "", conseil, flags=re.I).strip()
        script = f"{situation} [Pause] {conseil}"
        hook_text = situation[:60].split(".")[0] + "..."
    else:
        script = raw.strip()
        # Supprimer guillemets eventuels
        script = script.strip('"').strip("«").strip("»").strip()
        hook_text = script[:50].split(".")[0]

    # Nettoyer
    script = re.sub(r"\[Pause[^\]]*\]", "", script, flags=re.I)
    script = re.sub(r"\s+", " ", script).strip()

    word_count = len(script.split())
    logger.info(f"Shorts: {content_type} | {word_count} mots")

    if word_count < 15:
        raise ValueError(f"Script trop court: {word_count} mots")
    if word_count > 150:
        # Tronquer a la derniere phrase complete
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

    return {
        "content_type": content_type,
        "script_complet": script,
        "hook_text": hook_text,
        "image_prompts": [image_prompt],
        "tags": ["sagesse", "shorts", "motivation"] + type_tags.get(content_type, []),
        "mood": random.choice(["contemplative", "dark_motivation", "resilience"]),
        "takeaway": script[:80],
    }


def _generate_image_prompt(script: str, content_type: str) -> str:
    """Genere un prompt d'image en anglais pour le Short."""
    try:
        system = "Generate a single cinematic image prompt in English for a vertical 9:16 video. Dark moody style. Return ONLY the prompt text, no quotes, no JSON."
        user = f"Script: {script[:200]}\nType: {content_type}\nGenerate one cinematic 9:16 image prompt."
        raw = _call_kie_llm(system, user)
        prompt = raw.strip().strip('"')
        if len(prompt) > 20:
            return prompt
    except Exception as e:
        logger.warning(f"Image prompt generation failed: {e}")

    # Fallback
    fallbacks = [
        "silhouette of person on mountain top at sunset, dramatic sky, dark moody cinematic, 9:16 vertical",
        "close-up of weathered hands in prayer position, dramatic lighting, cinematic shadows, 9:16 vertical",
        "lone tree on cliff edge in storm, dramatic atmosphere, teal orange grading, 9:16 vertical",
        "person walking through dark forest with light ahead, cinematic, moody, 9:16 vertical",
        "sunrise through storm clouds over ocean, dramatic golden light, cinematic, 9:16 vertical",
    ]
    return random.choice(fallbacks)
