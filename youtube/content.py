"""Generation de contenu YouTube via Kie.ai (DeepSeek) — 3 appels separes.

V2: Base de philosophes verifiee + tendances web + rotation ponderee.
"""
import json
import re
import logging
import httpx
from . import config
from .philosophers import pick_philosopher, pick_citation, get_philosopher_count, get_citation_count
from .trends import fetch_trending_topics, match_trend_to_philosopher, build_trend_context

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

def _generate_script_text(exclusion_text: str) -> tuple[str, str, str, str]:
    """Genere le script narration en texte brut.

    Utilise la base de philosophes verifiee + tendances web.
    Retourne (script, citation, auteur, epoque).
    """
    # -- Extraire les noms des philosophes deja utilises --
    exclusion_names = []
    for line in exclusion_text.split("\n"):
        if line.strip().startswith("- ") and "—" in line:
            author = line.split("—")[-1].strip()
            if author:
                exclusion_names.append(author)

    # -- Selectionner philosophe et citation depuis la base verifiee --
    philosopher = pick_philosopher(exclusion_names=exclusion_names)
    citation_text, citation_source = pick_citation(philosopher)

    logger.info(
        f"Selected: {philosopher['nom']} ({philosopher['courant']}) — "
        f"\"{citation_text[:50]}...\" [{citation_source}]"
    )

    # -- Chercher les tendances web --
    try:
        trends = fetch_trending_topics()
        trend = match_trend_to_philosopher(trends, philosopher["nom"], philosopher["courant"])
    except Exception as e:
        logger.warning(f"Trends fetch failed: {e}")
        trend = None

    trend_context = build_trend_context(trend)

    system = f"""Tu es un createur YouTube francais expert en storytelling philosophique.
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
Commence par une ligne CITATION: puis AUTEUR: puis le script.

PHILOSOPHE DU JOUR : {philosopher['nom']}
COURANT : {philosopher['courant']}
EPOQUE : {philosopher['epoque']}"""

    user_prompt = f"""Ecris le script YouTube du jour.

CITATION IMPOSEE (VERIFIEE, source : {citation_source}) :
"{citation_text}"

AUTEUR : {philosopher['nom']}
EPOQUE : {philosopher['epoque']}

{exclusion_text}
{trend_context}

FORMAT DE REPONSE (texte brut, PAS de JSON) :
CITATION: {citation_text}
AUTEUR: {philosopher['nom']}
EPOQUE: {philosopher['epoque']}
---
[Le script complet de 1500-2500 mots, ecrit comme un recit continu]

STRUCTURE NARRATIVE (enchaine naturellement, SANS ecrire les titres) :

- HOOK D'OUVERTURE : Commence par une affirmation CONTRARIANTE ou une question CHOC qui remet en cause une croyance populaire. Pas de presentation, pas de "aujourd'hui on va parler de". Frappe direct. Exemple de ton : "Tout ce que tu crois savoir sur le bonheur est faux." ou "L'homme le plus puissant de Rome ecrivait ceci a trois heures du matin."

- CONTEXTE + PROMESSE : Pose les enjeux. Dis au spectateur ce qu'il va comprendre et pourquoi ca change tout. "A la fin de cette video, tu sauras exactement comment..."

- L'HISTOIRE DU PENSEUR : Raconte la vie de {philosopher['nom']} comme une HISTOIRE, pas une biographie Wikipedia. Quels combats ? Quelles souffrances ? Pourquoi cette citation est nee de son vecu ?

- LA CITATION DECRYPTEE : Explique la citation mot par mot. Qu'est-ce qu'elle dit VRAIMENT sous la surface ?

- APPLICATION HISTORIQUE : Un exemple historique puissant qui prouve la verite de cette idee.

- APPLICATION MODERNE : Transpose a un probleme d'AUJOURD'HUI (scrolling infini, anxiete de performance, relations superficielles, burnout, peur de l'echec). Sois precis et concret.

- L'OBJECTION : Anticipe le "oui mais..." du spectateur. Detruis l'objection avec un argument imparable.

- REVELATION PROFONDE : Le moment "aha". L'insight que personne ne voit. Le lien inattendu.

- EXERCICE CONCRET : Un exercice praticable IMMEDIATEMENT. Pas vague. Precis, avec des etapes.

- CLIMAX EMOTIONNEL : Le moment le plus intense. La phrase qui reste gravee.

- CONCLUSION : Boucle avec le hook d'ouverture. Termine par une question ouverte qui pousse a la reflexion. CTA subtil : "Si cette idee t'a fait voir les choses autrement, tu sais quoi faire." Pas de "abonne-toi et like"."""

    raw = _call_kie_llm(system, user_prompt)

    # Utiliser les valeurs verifiees de la base (pas celles du LLM)
    citation = citation_text
    auteur = philosopher["nom"]
    epoque = philosopher["epoque"]
    script = raw

    # Parser le LLM output pour extraire juste le script
    for line in raw.split("\n"):
        line_stripped = line.strip()
        # On ignore les lignes metadata du LLM — on a deja les bonnes valeurs
        if line_stripped.upper().startswith("CITATION:"):
            pass  # On garde notre citation verifiee
        elif line_stripped.upper().startswith("AUTEUR:"):
            pass  # On garde notre auteur verifie
        elif line_stripped.upper().startswith("EPOQUE:") or line_stripped.upper().startswith("ÉPOQUE:"):
            pass  # On garde notre epoque verifiee

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
- Les 2 premieres lignes = resume percutant avec mots-cles naturels (CRUCIAL pour le SEO, visible avant "Afficher plus")
- Inclure naturellement ces mots-cles : citations philosophiques, sagesse stoicienne, philosophie, developpement personnel, lecons de vie, citations inspirantes
- Structure : citation + resume percutant > ce que tu vas decouvrir (liste a puces) > contexte philosophique > CTA subtil > liens reseaux > hashtags SEO
- Ajouter a la fin : #Citations #Philosophie #Sagesse #Stoicisme #DeveloppementPersonnel #CitationDuJour
- Mentionner TikTok : @cdjour

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
    """Genere le contenu YouTube en 3 appels LLM separes.

    V2: Utilise la base de philosophes verifiee ({get_philosopher_count()} philosophes,
    {get_citation_count()} citations) + tendances web.
    """
    logger.info(
        f"Content generation V2: {get_philosopher_count()} philosophes, "
        f"{get_citation_count()} citations verifiees"
    )

    # Etape 1: Script en texte brut (philosophe + citation from DB)
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
    auteur_tag = auteur.lower().replace(" ", "").replace("'", "")
    return (
        f'"{citation}" — {auteur}\n\n'
        f"Dans cette video, on plonge dans la pensee de {auteur} ({epoque}) "
        f"pour comprendre pourquoi cette citation philosophique est plus pertinente "
        f"que jamais dans notre monde moderne.\n\n"
        f"On explore son contexte historique, le sens profond de ses mots, "
        f"et surtout comment appliquer cette sagesse antique concretement "
        f"dans ta vie quotidienne.\n\n"
        f"📚 Ce que tu vas decouvrir :\n"
        f"• L'histoire fascinante de {auteur} et pourquoi cette citation est nee\n"
        f"• Le sens cache derriere chaque mot\n"
        f"• Comment appliquer cette lecon de vie aux problemes modernes "
        f"(anxiete, burnout, relations, reseaux sociaux)\n"
        f"• Un exercice pratique a faire des maintenant\n\n"
        f"Cette video aborde la philosophie, le stoicisme, le developpement personnel "
        f"et les citations inspirantes qui ont traverse les siecles. "
        f"Que tu sois passionne de sagesse stoicienne, d'existentialisme, "
        f"ou simplement en quete de sens et de motivation, "
        f"cette reflexion est pour toi.\n\n"
        f"Si cette video t'a fait voir les choses autrement, "
        f"laisse un commentaire avec ta propre interpretation de cette citation.\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔔 Abonne-toi pour une dose quotidienne de sagesse\n"
        f"📱 TikTok : @cdjour\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"#Citations #Philosophie #Sagesse #Stoicisme #DeveloppementPersonnel "
        f"#{auteur_tag} #CitationDuJour #Motivation #LeconsDeVie #PenseesPositives"
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
