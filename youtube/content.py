"""Generation de contenu YouTube via Kie.ai (DeepSeek) — 3 appels separes."""
import json
import re
import logging
import httpx
from . import config

logger = logging.getLogger("youtube-citations")

KIE_CHAT_URL = "https://api.kie.ai/api/v1/chat/completions"


def _fix_encoding(text: str) -> str:
    """Corrige le double-encodage UTF-8 (bytes UTF-8 interpretes comme CP1252/Latin-1).

    Detecte le pattern classique: e.g. 'Ã©' au lieu de 'é', 'â€™' au lieu de '''.
    """
    # Patterns typiques de double-encodage UTF-8 -> CP1252
    if not any(marker in text for marker in ("Ã", "â€", "Ã©", "Ã¨", "Ã ", "Ãª", "Ã®", "Ã´", "Ã¹")):
        return text
    try:
        return text.encode("cp1252").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        try:
            return text.encode("latin-1").decode("utf-8")
        except (UnicodeDecodeError, UnicodeEncodeError):
            logger.warning("Encoding fix failed, returning original text")
            return text


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
        "max_tokens": 8192,
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

    # Verifier que la reponse contient choices (Kie.ai retourne 200 meme pour les erreurs)
    if "choices" not in data:
        error_msg = data.get("msg", data.get("message", str(data)))
        raise RuntimeError(f"Kie.ai API error: {error_msg}")

    content = data["choices"][0]["message"]["content"]
    finish = data["choices"][0].get("finish_reason", "?")
    usage = data.get("usage", {})
    logger.info(
        f"Kie.ai resp: {len(content)}c, finish={finish}, "
        f"tokens={usage.get('completion_tokens', '?')}/{usage.get('total_tokens', '?')}"
    )
    # Fix double-encodage UTF-8 courant avec Kie.ai
    content = _fix_encoding(content)
    return content


# ============================================================
# ETAPE 1 : Script en texte brut (pas JSON)
# ============================================================

def _generate_script_text(exclusion_text: str) -> tuple[str, str, str]:
    """Genere le script narration en texte brut. Retourne (script, citation_line, auteur_line)."""
    system = """Tu es un createur YouTube francais expert en storytelling philosophique.
Tu fais des videos profondes qui appliquent la sagesse ancienne aux problemes modernes.
Ton style : grave, direct, tutoiement, zero remplissage. Chaque phrase doit frapper.

REGLES ABSOLUES :
- Accents francais OBLIGATOIRES partout
- Nombres en LETTRES
- Tutoiement exclusif
- [Pause] pour les silences dramatiques (10-15 par script)
- Mots anglais en phonetique francaise
- NE JAMAIS ecrire de titres de sections, numeros de parties, ou indications de structure
- Le script est UNIQUEMENT le texte narre a voix haute, rien d'autre
- Pas de "Salut", "Hey", "Bienvenue" — commence direct par le hook

STYLE NARRATIF :
- Raconte des HISTOIRES, pas des cours. Utilise des anecdotes, des scenes vivantes.
- Chaque concept doit etre illustre par un exemple concret et moderne
- Alterne entre moments calmes (reflexion) et moments intenses (revelation)
- Tous les 2-3 minutes, introduis un micro-hook (fait surprenant, question, retournement)
- Applique la sagesse ancienne a des problemes d'aujourd'hui (anxiete, reseaux sociaux, burnout, relations)

Ecris le script DIRECTEMENT en texte brut, PAS de JSON.
Commence par une ligne CITATION: puis AUTEUR: puis le script."""

    user_prompt = f"""Ecris le script YouTube du jour.

{exclusion_text}

FORMAT DE REPONSE (texte brut, PAS de JSON) :
CITATION: [la citation complete]
AUTEUR: [nom de l'auteur]
EPOQUE: [contexte historique court]
---
[Le script complet de 1500-2500 mots, ecrit comme un recit continu]

STRUCTURE NARRATIVE (enchaine naturellement, SANS ecrire les titres) :

- HOOK D'OUVERTURE : Commence par une affirmation CONTRARIANTE ou une question CHOC qui remet en cause une croyance populaire. Pas de presentation, pas de "aujourd'hui on va parler de". Frappe direct. Exemple de ton : "Tout ce que tu crois savoir sur le bonheur est faux." ou "L'homme le plus puissant de Rome ecrivait ceci a trois heures du matin."

- CONTEXTE + PROMESSE : Pose les enjeux. Dis au spectateur ce qu'il va comprendre et pourquoi ca change tout. "A la fin de cette video, tu sauras exactement comment..."

- L'HISTOIRE DU PENSEUR : Raconte la vie du philosophe comme une HISTOIRE, pas une biographie Wikipedia. Quels combats ? Quelles souffrances ? Pourquoi cette citation est nee de son vecu ?

- LA CITATION DECRYPTEE : Explique la citation mot par mot. Qu'est-ce qu'elle dit VRAIMENT sous la surface ?

- APPLICATION HISTORIQUE : Un exemple historique puissant qui prouve la verite de cette idee.

- APPLICATION MODERNE : Transpose a un probleme d'AUJOURD'HUI (scrolling infini, anxiete de performance, relations superficielles, burnout, peur de l'echec). Sois precis et concret.

- L'OBJECTION : Anticipe le "oui mais..." du spectateur. Detruis l'objection avec un argument imparable.

- REVELATION PROFONDE : Le moment "aha". L'insight que personne ne voit. Le lien inattendu.

- EXERCICE CONCRET : Un exercice praticable IMMEDIATEMENT. Pas vague. Precis, avec des etapes.

- CLIMAX EMOTIONNEL : Le moment le plus intense. La phrase qui reste gravee.

- CONCLUSION : Boucle avec le hook d'ouverture. Termine par une question ouverte qui pousse a la reflexion. CTA subtil : "Si cette idee t'a fait voir les choses autrement, tu sais quoi faire." Pas de "abonne-toi et like"."""

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

    # Nettoyer les en-tetes de sections que le LLM inclut parfois
    script = re.sub(
        r"^\s*\d{1,2}\.\s*[A-ZÉÈÊÀÂÔÙÛÎ][A-ZÉÈÊÀÂÔÙÛÎ\s&']+(?:\([^)]*\))?\s*$",
        "", script, flags=re.MULTILINE,
    )
    script = re.sub(r"\(\d+-\d+\s*mots?\)", "", script, flags=re.I)
    script = re.sub(
        r"^\s*(?:INTRO(?:\s+HOOK)?|HOOK\s+D.OUVERTURE|CONTEXTE(?:\s+\+\s*PROMESSE)?|CONCLUSION|CTA|CLIMAX(?:\s+EMOTIONNEL)?|EXERCICE(?:\s+CONCRET)?|OBJECTION|REVELATION(?:\s+PROFONDE)?|APPLICATION(?:\s+MODERNE|\s+HISTORIQUE)?|GENESE|CITATION\s+(?:EXPLIQUEE|DECRYPTEE)|L.HISTOIRE\s+DU\s+PENSEUR)[^\n]*$",
        "", script, flags=re.MULTILINE | re.I,
    )
    script = re.sub(r"^-{2,}\s*$", "", script, flags=re.MULTILINE)
    script = re.sub(r"\n{3,}", "\n\n", script).strip()

    word_count = len(script.split())
    logger.info(f"Script brut genere: {auteur} | {word_count} mots | citation: {citation[:50]}...")

    if word_count < 500:
        raise ValueError(f"Script trop court: {word_count} mots")

    return script, citation, auteur, epoque


# ============================================================
# ETAPE 2 : Metadata en petit JSON
# ============================================================

def _generate_metadata(citation: str, auteur: str, epoque: str, script_excerpt: str) -> dict:
    """Genere les metadata YouTube optimisees CTR en petit JSON."""
    system = """Tu es un expert SEO YouTube specialise dans les videos philosophie/motivation francaises.
Tu connais les formules de titres qui maximisent le CTR et les patterns de thumbnails qui attirent le clic.
Retourne UNIQUEMENT un JSON valide, sans backticks, sans texte avant/apres."""

    user_prompt = f"""Genere les metadata YouTube pour cette video :

CITATION: "{citation}"
AUTEUR: {auteur}
EPOQUE: {epoque}
DEBUT DU SCRIPT: {script_excerpt}

REGLES POUR LE TITRE (yt_title) :
- Max 60 caracteres (visible sur mobile)
- Utilise une de ces formules prouvees :
  * "[Auteur] a revele le secret de [desir]"
  * "Cette sagesse de [X] ans va changer ta vision de [sujet]"
  * "Pourquoi [Auteur] a dit [chose provocante]"
  * "[Nombre] lecons de [Auteur] pour [probleme moderne]"
- Cree un GAP DE CURIOSITE mais sans clickbait
- Mets les mots les plus percutants EN PREMIER

REGLES POUR LE THUMBNAIL (thumbnail_text) :
- 2-4 MOTS MAXIMUM en majuscules
- Emotionnel et impactant (pas descriptif)
- Ne JAMAIS repeter le titre — le thumbnail COMPLETE le titre
- Exemples : "TOUT EST FAUX", "IL SAVAIT", "ARRETE MAINTENANT", "LA VERITE"

REGLES POUR LA DESCRIPTION (yt_description) :
- 200+ mots minimum
- Les 2 premieres lignes = resume percutant avec mots-cles naturels
- Inclure : sagesse stoicienne, philosophie, developpement personnel, citations
- Structure : resume > ce que tu vas apprendre > contexte > hashtags

Retourne ce JSON :
{{
  "hook": "Phrase d'ouverture contrariante ou question choc, 8-15 mots",
  "hook_text": "3-7 mots percutants pour affichage texte dans les 5 premieres secondes",
  "yt_title": "Titre YouTube max 60 chars, formule prouvee CTR",
  "yt_description": "Description SEO 200+ mots avec mots-cles naturels",
  "yt_tags": ["8-12 tags mix large et specifique", "inclure francais ET anglais"],
  "categorie": "stoicisme ou philosophie ou business ou spiritualite ou psychologie",
  "tags": ["hashtag1", "hashtag2", "hashtag3"],
  "cta_text": "CTA subtil et lie a la valeur, pas 'abonne-toi'",
  "mood": "dark_motivation ou contemplative ou warrior ou rebirth ou resilience",
  "thumbnail_text": "2-4 MOTS CHOC MAXIMUM",
  "takeaway": "La lecon percutante en 15-25 mots qui reste gravee"
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

    # Fallback description si vide
    yt_description = meta.get("yt_description", "")
    if not yt_description or len(yt_description) < 50:
        yt_description = _build_fallback_description(citation, auteur, epoque, script[:300])

    # Generer les chapitres automatiques depuis le script
    chapitres = _extract_chapters(script)

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
        "yt_description": yt_description,
        "yt_tags": meta.get("yt_tags", []),
        "categorie": meta.get("categorie", "philosophie"),
        "tags": meta.get("tags", []),
        "cta_text": meta.get("cta_text", "Si cette idée t'a fait voir les choses autrement, tu sais quoi faire."),
        "mood": meta.get("mood", "dark_motivation"),
        "thumbnail_text": meta.get("thumbnail_text", auteur.upper()),
        "chapitres": chapitres,
    }

    content = _validate(content)
    logger.info(
        f"YouTube content complete: {content['auteur']} | "
        f"{len(content['script_complet'].split())} words | "
        f"{len(content['image_prompts'])} images | "
        f"Title: {content.get('yt_title', 'N/A')}"
    )
    return content


def _build_fallback_description(citation: str, auteur: str, epoque: str, script_excerpt: str) -> str:
    """Genere une description YouTube SEO de secours si le LLM n'en a pas fourni."""
    return (
        f'"{citation}" — {auteur}\n\n'
        f"Dans cette video, on plonge dans la pensee de {auteur} ({epoque}) "
        f"pour comprendre pourquoi cette citation est plus pertinente que jamais. "
        f"On explore son contexte historique, son sens profond, et surtout comment "
        f"l'appliquer concretement dans ta vie quotidienne.\n\n"
        f"Cette video aborde des themes comme la philosophie, le developpement personnel, "
        f"la sagesse antique appliquee aux problemes modernes (anxiete, burnout, "
        f"relations, reseaux sociaux). Que tu sois passionné de stoicisme, "
        f"d'existentialisme ou simplement en quete de sens, cette reflexion est pour toi.\n\n"
        f"Si cette video t'a fait voir les choses autrement, laisse un commentaire "
        f"avec ta propre interpretation.\n\n"
        f"#philosophie #citationdujour #{auteur.lower().replace(' ', '')} "
        f"#sagesse #developpementpersonnel #motivation #reflexion"
    )


def _extract_chapters(script: str) -> list[dict]:
    """Extrait des chapitres automatiques du script base sur la structure narrative.

    Decoupe le script en segments reguliers et genere des titres descriptifs.
    """
    words = script.split()
    total_words = len(words)
    if total_words < 500:
        return []

    # Decouper en ~8 chapitres pour une video 10-20 min
    nb_chapters = min(10, max(6, total_words // 250))
    words_per_chapter = total_words // nb_chapters

    chapter_titles = [
        "Introduction",
        "Le contexte",
        "L'histoire du penseur",
        "La citation décryptée",
        "L'exemple historique",
        "Application moderne",
        "L'objection",
        "La révélation",
        "L'exercice pratique",
        "Conclusion",
    ]

    chapitres = []
    for i in range(nb_chapters):
        mot_idx = i * words_per_chapter
        titre = chapter_titles[i] if i < len(chapter_titles) else f"Partie {i + 1}"
        chapitres.append({"titre": titre, "mot_index_approx": mot_idx})

    return chapitres


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
