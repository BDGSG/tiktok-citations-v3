"""Generation de contenu YouTube via Claude — essai long 10-20 minutes."""
import json
import re
import logging
import httpx
from . import config

logger = logging.getLogger("youtube-citations")

SYSTEM_PROMPT = r"""Tu es un createur YouTube francais specialise en motivation, philosophie et developpement personnel. Tu produis des videos long format (10-20 minutes) de niveau professionnel, comme Motiversity, After Skool ou Einzelganger.

# MISSION
Genere un ESSAI PHILOSOPHIQUE APPROFONDI de 10 a 20 minutes. Le script sera lu a voix haute (vitesse 0.88x, voix masculine grave). Tu DOIS ecrire entre 1500 et 3000 mots dans le champ script_complet.

# STRUCTURE NARRATIVE OBLIGATOIRE (12 parties avec chapitres)

## 1. INTRO HOOK (0-30s, 50-80 mots)
Ouverture cinematique. Scene visuelle saisissante ou question existentielle profonde. Doit capturer l'attention en 10 secondes.
"Imagine-toi debout, seul, au sommet d'une montagne. Le vent souffle. Tu regardes en bas et tu realises..."

## 2. CONTEXTE & PROMESSE (30s-1min30, 80-120 mots)
Pourquoi cette video existe. Quel probleme universel elle adresse. La promesse de ce que le spectateur va apprendre.
"Dans les prochaines minutes, on va explorer ensemble une idee qui a change la vie de millions de personnes..."

## 3. L'AUTEUR & SON EPOQUE (1min30-3min, 150-200 mots)
Biographie detaillee de l'auteur. Son epoque, son contexte, ses epreuves. Faire vivre le personnage.
Dates, lieux, anecdotes historiques. Le spectateur doit SENTIR l'epoque.

## 4. LA GENESE DE LA PENSEE (3-5min, 200-250 mots)
Comment l'auteur en est arrive a cette citation/idee. Quel evenement l'a declenche.
Le parcours intellectuel, les influences, les echecs qui ont forge cette sagesse.

## 5. LA CITATION EXPLIQUEE (5-7min, 200-300 mots)
La citation elle-meme, mot par mot, decortiquee en profondeur.
Chaque concept analyse, chaque nuance exploree. Plusieurs niveaux de lecture.

## 6. PREMIERE APPLICATION HISTORIQUE (7-8min30, 150-200 mots)
Un exemple historique concret ou cette sagesse s'est verifiee.
Autre personnage, autre epoque, meme verite universelle.

## 7. DEUXIEME APPLICATION MODERNE (8min30-10min, 150-200 mots)
Application dans la vie moderne, entrepreneuriat, relations, sante mentale.
Exemples concrets et reconnaissables du quotidien.

## 8. L'OBJECTION (10-11min30, 150-200 mots)
Anticipe les doutes du spectateur. "Mais tu vas me dire..."
Adresse l'objection avec honnetete, puis la depasse avec un argument plus profond.

## 9. LA REVELATION PROFONDE (11min30-13min, 150-200 mots)
Le niveau de comprehension superieur. Ce que la plupart des gens ratent.
Le message cache, la couche la plus profonde de la sagesse.

## 10. EXERCICE PRATIQUE (13-15min, 150-200 mots)
Donne au spectateur quelque chose de concret a faire DES AUJOURD'HUI.
Un exercice simple mais transformateur. Pas de theorie vague.

## 11. CLIMAX EMOTIONNEL (15-17min, 100-150 mots)
Phrases COURTES. Rythme LENT. Chaque mot est une bombe.
Le moment ou tout se connecte. [Pause] entre les phrases puissantes.

## 12. CONCLUSION & CTA (17-20min, 80-120 mots)
Referme l'arc narratif. Rappelle l'intro. Vision inspirante du futur.
CTA YouTube : like, abonnement, commentaire, cloche de notification.

# FORMAT JSON STRICT
Retourne UNIQUEMENT un objet JSON valide. Pas de markdown, pas de backticks, pas de texte avant ou apres.

{
  "hook": "Question choc pour le titre (8-15 mots)",
  "citation": "La citation complete",
  "auteur": "Nom de l'auteur",
  "epoque": "Epoque/contexte detaille",
  "takeaway": "Lecon percutante en 15-25 mots",
  "script_complet": "Le script narration complet (1500-3000 mots). STRUCTURE en 12 parties. Utilise [Pause] pour marquer les silences (10-15 par script).",
  "chapitres": [
    {"titre": "Titre du chapitre", "mot_index_approx": 0},
    {"titre": "Titre chapitre 2", "mot_index_approx": 80},
    ...
  ],
  "hook_text": "Texte court affiche 5 premieres secondes (5-10 mots max)",
  "yt_title": "Titre YouTube accrocheur (max 70 caracteres, avec majuscules strategiques)",
  "yt_description": "Description YouTube complete avec timestamps et liens (400-600 mots)",
  "yt_tags": ["tag1", "tag2", "... (20-30 tags pour SEO YouTube)"],
  "categorie": "stoicisme | philosophie | business | spiritualite | psychologie",
  "tags": ["mot1", "mot2", "... (8-10 hashtags courts)"],
  "cta_text": "Phrase d'appel a l'action finale YouTube",
  "mood": "dark_motivation | contemplative | warrior | rebirth | resilience",
  "thumbnail_text": "Texte COURT et CHOC pour la miniature (3-5 mots MAX, en majuscules)"
}

# REGLES IMAGE PROMPTS (20-40, en anglais)
IMPORTANT : Les images sont affichees DANS L'ORDRE pendant la narration. Chaque image correspond a un bloc de ~40-50 mots du script. Les images DOIVENT illustrer ce qui est dit a ce moment precis.

Format 16:9 OBLIGATOIRE (paysage, cinematique).

Chaque prompt doit evoquer un visuel cinematique. Style :
"dark moody cinematic lighting, dramatic shadows, teal and orange color grading, 4k ultrarealistic photography, widescreen 16:9, no text no words no writing"

Correspondance narration/images :
- Images 1-3 : INTRO HOOK (scenes d'ouverture, mystere, grandeur)
- Images 4-6 : CONTEXTE & PROMESSE
- Images 7-12 : L'AUTEUR & SON EPOQUE (portrait, epoque, lieux historiques)
- Images 13-18 : GENESE DE LA PENSEE (parcours, influences, epreuves)
- Images 19-25 : LA CITATION EXPLIQUEE (metaphores, symboles)
- Images 26-30 : APPLICATION HISTORIQUE (autre epoque, autre personnage)
- Images 31-36 : APPLICATION MODERNE (vie quotidienne, ville, technologie)
- Images 37-40 : L'OBJECTION (tension, doute, questionnement)
- Images 41-45 : REVELATION PROFONDE (lumiere, revelation, comprehension)
- Images 46-50 : EXERCICE PRATIQUE (action, mouvement, determination)
- Images 51-55 : CLIMAX EMOTIONNEL (intensite maximale, emotion pure)
- Images 56-60 : CONCLUSION (horizon, lumiere, espoir, avenir)

Categories de visuels :
- Paysages grandioses en 16:9 (montagnes, ocean, foret, desert, ciel etoile)
- Portraits cinematiques (silhouettes, gros plans, contre-jour)
- Scenes historiques (architecture antique, batailles, bibliotheques)
- Vie moderne (villes, bureaux, nature, sport)
- Art abstrait / symbolique (geometrie sacree, fractales, lumiere)
- Nature macro / micro (gouttes, flammes, textures)

# YOUTUBE DESCRIPTION
La yt_description doit inclure :
1. Un paragraphe d'accroche (2-3 phrases)
2. Les timestamps des chapitres (00:00 format)
3. La citation complete
4. Un paragraphe sur l'auteur
5. Hashtags
6. Liens fictifs vers reseaux sociaux (on les remplacera)

# YOUTUBE TITLE
Le yt_title doit :
- Faire moins de 70 caracteres
- Utiliser des majuscules strategiques (pas tout en majuscules)
- Inclure le nom de l'auteur si possible
- Creer de la curiosite ou de l'emotion

# THUMBNAIL TEXT
Le thumbnail_text doit :
- Etre en MAJUSCULES
- Maximum 3-5 mots
- Etre CHOC, emotionnel, provocant
- Exemples : "TU AS TORT", "IL AVAIT RAISON", "REVEILLE-TOI", "LA VERITE CACHEE"

# REGLE ABSOLUE SUR LES ACCENTS
Tu DOIS OBLIGATOIREMENT utiliser TOUS les accents francais.
JAMAIS ecrire sans accents. Si tu ecris un seul mot sans ses accents, le script est REJETE.

# REGLE ABSOLUE SUR LES NOMBRES
Tu DOIS ecrire TOUS les nombres en LETTRES dans le script_complet.

# REGLE SUR LES MOTS ANGLAIS
Dans script_complet, ecris les mots anglais en phonetique francaise.

# STYLE
- Alterner phrases COURTES (tension) et phrases LONGUES (reflexion)
- Tutoiement OBLIGATOIRE
- Ton : mentor sage, profond, bienveillant mais exigeant
- Transitions naturelles entre chapitres
- [Pause] = silence avant les phrases puissantes (10-15 par script)
- ZERO remplissage, CHAQUE mot doit compter
- Plus de profondeur historique et philosophique que la version TikTok
- References croisees entre auteurs/epoques
- Style narratif immersif (faire vivre les scenes)

# AUTEURS VARIES
Stoiciens, entrepreneurs, philosophes, leaders spirituels, ecrivains, scientifiques, guerriers, psychologues, mystiques...

VERIFIE : script_complet fait-il 1500-3000 mots ? TOUS les accents ? AUCUN chiffre arabe ? Mots anglais en phonetique ? 20-40 image_prompts ? Chapitres coherents ?"""


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
    KIE_CHAT_URL = "https://api.kie.ai/api/v1/chat/completions"
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

    logger.info("Calling Kie.ai LLM (deepseek-chat) for YouTube content...")
    with httpx.Client(timeout=300) as client:
        resp = client.post(KIE_CHAT_URL, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()

    return data["choices"][0]["message"]["content"]


def _generate_script(exclusion_text: str) -> dict:
    """Etape 1: Genere le script et metadata (sans image_prompts)."""
    user_prompt = f"""Cree le contenu YouTube motivationnel/philosophique du jour (FORMAT LONG 10-20 MINUTES).

{exclusion_text}

INSTRUCTIONS :
1. script_complet entre 1500 et 3000 mots (10-20 minutes de narration)
2. Structure en 12 parties avec chapitres
3. yt_title accrocheur (max 70 chars)
4. yt_description complete avec timestamps des chapitres
5. yt_tags (20-30 tags SEO YouTube)
6. thumbnail_text (3-5 mots CHOC en majuscules)
7. chapitres avec titres et positions approximatives
8. JAMAIS la meme citation que celles listees ci-dessus
9. TOUS les accents francais OBLIGATOIRES
10. TOUS les nombres en LETTRES
11. Mots anglais en phonetique francaise dans script_complet
12. mood = l'ambiance globale de la video

NE PAS inclure image_prompts dans cette reponse. Retourne UNIQUEMENT le JSON, sans backticks."""

    raw_text = _call_kie_llm(SYSTEM_PROMPT, user_prompt)
    return _parse_json(raw_text)


def _generate_image_prompts(script: str, mood: str, auteur: str) -> list[str]:
    """Etape 2: Genere les image prompts basés sur le script."""
    system = """Tu generes des prompts d'images cinematiques en anglais pour illustrer un script YouTube.
Format 16:9 OBLIGATOIRE. Chaque prompt doit evoquer un visuel cinematique.
Style : "dark moody cinematic lighting, dramatic shadows, teal and orange color grading, 4k ultrarealistic photography, widescreen 16:9, no text no words no writing"
Les images sont affichees DANS L'ORDRE pendant la narration."""

    user_prompt = f"""Genere 25-35 prompts d'images cinematiques en anglais pour ce script YouTube.

AUTEUR: {auteur}
MOOD: {mood}
SCRIPT (extrait des 500 premiers mots):
{' '.join(script.split()[:500])}

Retourne UNIQUEMENT un JSON array de strings, sans backticks. Exemple:
["prompt 1", "prompt 2", ...]"""

    raw_text = _call_kie_llm(system, user_prompt)
    cleaned = re.sub(r"```(?:json)?\s*", "", raw_text)
    cleaned = re.sub(r"```\s*$", "", cleaned).strip()

    try:
        prompts = json.loads(cleaned)
    except json.JSONDecodeError:
        # Tenter de reparer un array tronque
        if cleaned.count('"') % 2 == 1:
            cleaned += '"'
        open_brackets = cleaned.count('[') - cleaned.count(']')
        cleaned += ']' * max(0, open_brackets)
        prompts = json.loads(cleaned)

    if isinstance(prompts, list):
        return [p for p in prompts if isinstance(p, str) and len(p) > 10]
    return []


def generate_content(exclusion_text: str = "") -> dict:
    """Appelle Kie.ai LLM en 2 etapes pour generer le contenu YouTube."""
    max_retries = 2
    last_error = None

    # Etape 1: Script + metadata
    for attempt in range(max_retries + 1):
        try:
            content = _generate_script(exclusion_text)
            # Validation basique du script
            required = ["hook", "citation", "auteur", "script_complet"]
            for field in required:
                if field not in content:
                    raise ValueError(f"Champ manquant: {field}")
            word_count = len(content["script_complet"].split())
            if word_count < config.SCRIPT_MIN_WORDS:
                raise ValueError(f"Script trop court: {word_count} mots")
            logger.info(f"Script genere: {content['auteur']} | {word_count} mots")
            break
        except (json.JSONDecodeError, ValueError) as e:
            last_error = e
            logger.warning(f"Script generation attempt {attempt + 1} failed: {e}")
            if attempt >= max_retries:
                raise last_error

    # Etape 2: Image prompts (appel separe)
    try:
        image_prompts = _generate_image_prompts(
            content["script_complet"],
            content.get("mood", "dark_motivation"),
            content["auteur"],
        )
        content["image_prompts"] = image_prompts
        logger.info(f"Image prompts generes: {len(image_prompts)}")
    except Exception as e:
        logger.warning(f"Image prompts generation failed: {e}, using fallback")
        content["image_prompts"] = _fallback_image_prompts(content)

    content = _validate(content)
    logger.info(
        f"YouTube content complete: {content['auteur']} | "
        f"{len(content['script_complet'].split())} words | "
        f"{len(content['image_prompts'])} images | "
        f"Title: {content.get('yt_title', 'N/A')}"
    )
    return content


def _fallback_image_prompts(content: dict) -> list[str]:
    """Genere des prompts generiques si l'appel LLM echoue."""
    mood = content.get("mood", "dark_motivation")
    auteur = content.get("auteur", "philosopher")
    base_prompts = [
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
    return base_prompts


def _parse_json(text: str) -> dict:
    """Extrait le JSON de la reponse LLM, avec reparation si tronque."""
    cleaned = re.sub(r"```(?:json)?\s*", "", text)
    cleaned = re.sub(r"```\s*$", "", cleaned)
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON invalide (len={len(cleaned)}), tentative de reparation: {e}")

        # Strategie 1: trouver le dernier champ JSON complet et couper la
        # Chercher le dernier pattern "key": "value" ou "key": [...] complet
        patterns = [
            r'"[^"]+"\s*:\s*"[^"]*"(?=\s*[,}])',  # "key": "value"
            r'"[^"]+"\s*:\s*\[[^\]]*\](?=\s*[,}])',  # "key": [...]
            r'"[^"]+"\s*:\s*\d+(?=\s*[,}])',  # "key": 123
            r'"[^"]+"\s*:\s*(?:true|false|null)(?=\s*[,}])',  # "key": true
        ]

        best_end = -1
        for pat in patterns:
            for m in re.finditer(pat, cleaned):
                if m.end() > best_end:
                    best_end = m.end()

        if best_end > 0:
            truncated = cleaned[:best_end]
            # Nettoyer une virgule finale
            truncated = truncated.rstrip().rstrip(',')
            # Fermer les structures ouvertes
            open_brackets = truncated.count('[') - truncated.count(']')
            open_braces = truncated.count('{') - truncated.count('}')
            truncated += ']' * max(0, open_brackets)
            truncated += '}' * max(0, open_braces)
            try:
                result = json.loads(truncated)
                logger.info(f"JSON repare avec succes (coupe a pos {best_end}/{len(cleaned)})")
                return result
            except json.JSONDecodeError:
                pass

        # Strategie 2: fermer naïvement les structures ouvertes
        repaired = cleaned
        if repaired.count('"') % 2 == 1:
            repaired += '"'
        open_brackets = repaired.count('[') - repaired.count(']')
        open_braces = repaired.count('{') - repaired.count('}')
        repaired += ']' * max(0, open_brackets)
        repaired += '}' * max(0, open_braces)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            raise ValueError(f"JSON irrecuperable apres reparation (len={len(cleaned)})")


def _validate(content: dict) -> dict:
    """Valide et enrichit le contenu YouTube."""
    required = ["hook", "citation", "auteur", "script_complet", "image_prompts"]
    for field in required:
        if field not in content:
            raise ValueError(f"Champ manquant: {field}")

    # Word count
    words = content["script_complet"].split()
    word_count = len(words)
    if word_count < config.SCRIPT_MIN_WORDS:
        raise ValueError(f"Script trop court: {word_count} mots (min {config.SCRIPT_MIN_WORDS})")
    if word_count > config.SCRIPT_MAX_WORDS + 100:
        logger.warning(f"Script un peu long: {word_count} mots (max {config.SCRIPT_MAX_WORDS})")

    # Image prompts count
    if len(content["image_prompts"]) < config.MIN_IMAGE_PROMPTS:
        raise ValueError(
            f"Pas assez d'image prompts: {len(content['image_prompts'])} "
            f"(min {config.MIN_IMAGE_PROMPTS})"
        )

    # Check accents manquants
    accent_words = ["verite", "echec", "reussite", "lecon", "difference", "strategie"]
    script = content["script_complet"].lower()
    missing = [w for w in accent_words if w in script]
    if len(missing) > 2:
        logger.warning(f"Accents potentiellement manquants: {missing}")

    # Defaults
    content.setdefault("hook_text", "")
    content.setdefault("cta_text", "Abonne-toi et active la cloche")
    content.setdefault("categorie", "philosophie")
    content.setdefault("tags", [])
    content.setdefault("mood", "dark_motivation")
    content.setdefault("epoque", "")
    content.setdefault("yt_title", f"{content['hook']} — {content['auteur']}")
    content.setdefault("yt_description", "")
    content.setdefault("yt_tags", content.get("tags", []))
    content.setdefault("chapitres", [])
    content.setdefault("thumbnail_text", content["hook"][:30].upper())

    # Tronquer titre YouTube si trop long
    if len(content["yt_title"]) > 100:
        content["yt_title"] = content["yt_title"][:97] + "..."

    return content
