"""Generation de contenu YouTube via Kie.ai (DeepSeek) — 3 appels separes."""
import json
import re
import logging
import httpx
from . import config

logger = logging.getLogger("youtube-citations")

KIE_CHAT_URL = "https://api.kie.ai/api/v1/chat/completions"


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


def _call_kie_llm(system: str, user_prompt: str) -> str:
    """Appelle Kie.ai LLM (DeepSeek) via endpoint OpenAI-compatible."""
    headers = {
        "Authorization": f"Bearer {config.KIE_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": "deepseek-chat",
        "max_tokens": 16384,
        "temperature": 0.85,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ],
    }

    logger.info(f"Kie.ai call: system={len(system)}c, user={len(user_prompt)}c")
    with httpx.Client(timeout=300) as client:
        resp = client.post(KIE_CHAT_URL, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()

    content = data["choices"][0]["message"]["content"]
    finish = data["choices"][0].get("finish_reason", "?")
    usage = data.get("usage", {})
    logger.info(
        f"Kie.ai resp: {len(content)}c, finish={finish}, "
        f"tokens={usage.get('completion_tokens', '?')}/{usage.get('total_tokens', '?')}"
    )
    if finish == "length":
        logger.warning("Kie.ai: response truncated (finish_reason=length)!")
    return content


# ============================================================
# ETAPE 1 : Script en texte brut (pas JSON)
# ============================================================

def _generate_script_text(exclusion_text: str) -> tuple[str, str, str]:
    """Genere le script narration en texte brut. Retourne (script, citation_line, auteur_line)."""
    system = """Tu es un createur YouTube francais specialise en motivation et philosophie.
Ecris un ESSAI PHILOSOPHIQUE de 1500-2500 mots pour une video YouTube de 10-15 minutes.
Le script sera lu a voix haute (vitesse 0.88x, voix masculine grave).

REGLES STRICTES :
- Accents francais OBLIGATOIRES partout
- Nombres en LETTRES
- Tutoiement
- [Pause] pour marquer les silences (10-15 par script)
- Mots anglais en phonetique francaise
- ZERO remplissage, chaque mot doit compter

Ecris le script DIRECTEMENT en texte brut, PAS de JSON.
Commence par une ligne CITATION: puis AUTEUR: puis le script."""

    user_prompt = f"""Ecris le script YouTube du jour.

{exclusion_text}

FORMAT DE REPONSE (texte brut, PAS de JSON) :
CITATION: [la citation complete]
AUTEUR: [nom de l'auteur]
EPOQUE: [contexte historique court]
---
[Le script complet de 1500-2500 mots, structure en 12 parties]

Les 12 parties du script :
1. INTRO HOOK (50-80 mots)
2. CONTEXTE & PROMESSE (80-120 mots)
3. L'AUTEUR & SON EPOQUE (150-200 mots)
4. GENESE DE LA PENSEE (200-250 mots)
5. CITATION EXPLIQUEE (200-300 mots)
6. APPLICATION HISTORIQUE (150-200 mots)
7. APPLICATION MODERNE (150-200 mots)
8. L'OBJECTION (150-200 mots)
9. REVELATION PROFONDE (150-200 mots)
10. EXERCICE PRATIQUE (150-200 mots)
11. CLIMAX EMOTIONNEL (100-150 mots)
12. CONCLUSION & CTA (80-120 mots)"""

    raw = _call_kie_llm(system, user_prompt)

    # Parser le texte brut
    citation = ""
    auteur = ""
    epoque = ""
    script = raw

    for line in raw.split("\n"):
        line_stripped = line.strip()
        if line_stripped.upper().startswith("CITATION:"):
            citation = line_stripped[9:].strip().strip('"')
        elif line_stripped.upper().startswith("AUTEUR:"):
            auteur = line_stripped[7:].strip()
        elif line_stripped.upper().startswith("EPOQUE:") or line_stripped.upper().startswith("ÉPOQUE:"):
            epoque = line_stripped.split(":", 1)[1].strip()

    # Extraire le script apres le separateur ---
    if "---" in raw:
        script = raw.split("---", 1)[1].strip()
    else:
        # Essayer de couper apres les metadata
        lines = raw.split("\n")
        start = 0
        for i, line in enumerate(lines):
            if any(line.strip().upper().startswith(p) for p in ["CITATION:", "AUTEUR:", "EPOQUE:", "ÉPOQUE:"]):
                start = i + 1
        if start > 0:
            script = "\n".join(lines[start:]).strip()

    word_count = len(script.split())
    logger.info(f"Script brut genere: {auteur} | {word_count} mots | citation: {citation[:50]}...")

    if word_count < 500:
        raise ValueError(f"Script trop court: {word_count} mots")

    return script, citation, auteur, epoque


# ============================================================
# ETAPE 2 : Metadata en petit JSON
# ============================================================

def _generate_metadata(citation: str, auteur: str, epoque: str, script_excerpt: str) -> dict:
    """Genere les metadata YouTube en petit JSON."""
    system = "Tu generes des metadata YouTube. Retourne UNIQUEMENT un JSON valide, sans backticks."

    user_prompt = f"""Genere les metadata YouTube pour cette video :

CITATION: "{citation}"
AUTEUR: {auteur}
EPOQUE: {epoque}
DEBUT DU SCRIPT: {script_excerpt}

Retourne ce JSON (SANS backticks, SANS texte avant/apres) :
{{
  "hook": "Question choc 8-15 mots",
  "hook_text": "5-10 mots pour les 5 premieres secondes",
  "yt_title": "Titre YouTube max 70 chars avec le nom de l'auteur",
  "yt_tags": ["tag1", "tag2", "tag3"],
  "categorie": "stoicisme ou philosophie ou business ou spiritualite ou psychologie",
  "tags": ["hashtag1", "hashtag2"],
  "cta_text": "Phrase d'appel a l'action",
  "mood": "dark_motivation ou contemplative ou warrior ou rebirth ou resilience",
  "thumbnail_text": "3-5 MOTS CHOC EN MAJUSCULES",
  "takeaway": "Lecon percutante en 15-25 mots"
}}"""

    raw = _call_kie_llm(system, user_prompt)
    cleaned = re.sub(r"```(?:json)?\s*", "", raw)
    cleaned = re.sub(r"```\s*$", "", cleaned).strip()
    return json.loads(cleaned)


# ============================================================
# ETAPE 3 : Image prompts
# ============================================================

def _generate_image_prompts(script_excerpt: str, mood: str, auteur: str) -> list[str]:
    """Genere les image prompts en JSON array."""
    system = """Genere des prompts d'images cinematiques en anglais pour YouTube.
Format 16:9. Style: dark moody cinematic, dramatic shadows, teal/orange grading, 4k, no text.
Retourne UNIQUEMENT un JSON array de strings, sans backticks."""

    user_prompt = f"""25 prompts d'images pour cette video YouTube :
AUTEUR: {auteur}, MOOD: {mood}
SCRIPT: {script_excerpt}

Retourne ["prompt1", "prompt2", ...] (25 prompts, en anglais)"""

    raw = _call_kie_llm(system, user_prompt)
    cleaned = re.sub(r"```(?:json)?\s*", "", raw)
    cleaned = re.sub(r"```\s*$", "", cleaned).strip()

    try:
        prompts = json.loads(cleaned)
    except json.JSONDecodeError:
        # Reparer array tronque
        if cleaned.count('"') % 2 == 1:
            cleaned += '"'
        open_brackets = cleaned.count('[') - cleaned.count(']')
        cleaned += ']' * max(0, open_brackets)
        prompts = json.loads(cleaned)

    if isinstance(prompts, list):
        return [p for p in prompts if isinstance(p, str) and len(p) > 10]
    return []


def _fallback_image_prompts(auteur: str) -> list[str]:
    """Prompts generiques de secours."""
    return [
        f"dark moody cinematic portrait of ancient {auteur}, dramatic lighting, 16:9, no text",
        "vast mountain landscape at dawn, cinematic lighting, teal orange grading, 16:9, no text",
        "silhouette of person standing on cliff edge, dramatic sunset, widescreen, no text",
        "ancient library with dust particles in light beams, cinematic, 16:9, no text",
        "close-up of weathered hands holding old book, moody lighting, 16:9, no text",
        "stormy ocean waves crashing on rocks, dramatic sky, cinematic, 16:9, no text",
        "lone tree in vast desert landscape, golden hour, cinematic, 16:9, no text",
        "dark corridor with light at the end, dramatic shadows, 16:9, no text",
        "person meditating on mountain top, misty sunrise, cinematic, 16:9, no text",
        "ancient ruins with dramatic sky, teal and orange grading, 16:9, no text",
        "close-up of eyes reflecting fire, moody cinematic, 16:9, no text",
        "city skyline at night with fog, cinematic lighting, 16:9, no text",
        "person walking alone on empty road, dramatic perspective, 16:9, no text",
        "sunrise breaking through storm clouds, golden light rays, 16:9, no text",
        "ancient statue face in dramatic shadow, cinematic, 16:9, no text",
        "forest path with light filtering through trees, moody atmosphere, 16:9, no text",
        "person standing before vast ocean, back to camera, cinematic, 16:9, no text",
        "clock gears in macro, golden tones, cinematic lighting, 16:9, no text",
        "mountain peak above clouds at sunset, epic cinematic, 16:9, no text",
        "person reaching toward light, dramatic silhouette, 16:9, no text",
    ]


# ============================================================
# ORCHESTRATEUR PRINCIPAL
# ============================================================

def generate_content(exclusion_text: str = "") -> dict:
    """Genere le contenu YouTube en 3 appels LLM separes."""
    # Etape 1: Script en texte brut
    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            script, citation, auteur, epoque = _generate_script_text(exclusion_text)
            break
        except Exception as e:
            logger.warning(f"Script attempt {attempt + 1} failed: {e}")
            if attempt >= max_retries:
                raise

    script_excerpt = " ".join(script.split()[:300])

    # Etape 2: Metadata
    try:
        meta = _generate_metadata(citation, auteur, epoque, script_excerpt[:500])
    except Exception as e:
        logger.warning(f"Metadata generation failed: {e}, using defaults")
        meta = {}

    # Etape 3: Image prompts
    try:
        image_prompts = _generate_image_prompts(
            script_excerpt, meta.get("mood", "dark_motivation"), auteur
        )
        if len(image_prompts) < 10:
            raise ValueError(f"Seulement {len(image_prompts)} prompts")
    except Exception as e:
        logger.warning(f"Image prompts failed: {e}, using fallback")
        image_prompts = _fallback_image_prompts(auteur)

    # Assembler le contenu final
    content = {
        "citation": citation,
        "auteur": auteur,
        "epoque": epoque,
        "script_complet": script,
        "image_prompts": image_prompts,
        "hook": meta.get("hook", citation[:60]),
        "hook_text": meta.get("hook_text", ""),
        "takeaway": meta.get("takeaway", ""),
        "yt_title": meta.get("yt_title", f"{citation[:40]} — {auteur}"),
        "yt_description": meta.get("yt_description", ""),
        "yt_tags": meta.get("yt_tags", []),
        "categorie": meta.get("categorie", "philosophie"),
        "tags": meta.get("tags", []),
        "cta_text": meta.get("cta_text", "Abonne-toi et active la cloche"),
        "mood": meta.get("mood", "dark_motivation"),
        "thumbnail_text": meta.get("thumbnail_text", auteur.upper()),
        "chapitres": [],
    }

    content = _validate(content)
    logger.info(
        f"YouTube content complete: {content['auteur']} | "
        f"{len(content['script_complet'].split())} words | "
        f"{len(content['image_prompts'])} images | "
        f"Title: {content.get('yt_title', 'N/A')}"
    )
    return content


def _validate(content: dict) -> dict:
    """Valide et enrichit le contenu YouTube."""
    required = ["citation", "auteur", "script_complet", "image_prompts"]
    for field in required:
        if field not in content:
            raise ValueError(f"Champ manquant: {field}")

    word_count = len(content["script_complet"].split())
    if word_count < 500:
        raise ValueError(f"Script trop court: {word_count} mots")
    if word_count > config.SCRIPT_MAX_WORDS + 500:
        logger.warning(f"Script long: {word_count} mots")

    if len(content["image_prompts"]) < 10:
        raise ValueError(f"Pas assez d'images: {len(content['image_prompts'])}")

    # Tronquer titre YouTube
    if len(content.get("yt_title", "")) > 100:
        content["yt_title"] = content["yt_title"][:97] + "..."

    return content
