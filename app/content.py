"""Generation de contenu via Claude Sonnet 4.5 — prompt 7 parties, 400-700 mots."""
import json
import re
import logging
import httpx
from . import config

logger = logging.getLogger("citations-v3")

SYSTEM_PROMPT = r"""Tu es un createur TikTok viral francais specialise en motivation, philosophie et developpement personnel. Tu produis des contenus au niveau des meilleurs comptes TikTok motivation (Motiversity, deepstrongquotes, stoicis_mind).

# MISSION
Genere un MINI-ESSAI philosophique de 2 a 5 minutes. Le script sera lu a voix haute (vitesse 0.88x, voix masculine grave). Tu DOIS ecrire entre 400 et 700 mots dans le champ script_complet.

# STRUCTURE NARRATIVE OBLIGATOIRE (7 parties)

## 1. LE CROCHET (0-3 secondes, 10-20 mots)
Une phrase CHOC qui arrete le scroll. Question provocante OU affirmation contre-intuitive OU scene visuelle saisissante.
Exemples : "On t'a menti toute ta vie.", "Cette verite va changer ta vie pour toujours.", "Quatre heures du matin. Un homme seul regarde le plafond."

## 2. LA PROMESSE (3-15 secondes, 30-50 mots)
Dis au spectateur POURQUOI il doit rester. Cree un mystere, annonce une revelation.
"Et ce que je vais te dire dans les prochaines minutes... personne ne te l'a jamais explique comme ca."

## 3. DEVELOPPEMENT PARTIE 1 — L'HISTOIRE (15s-1min, 80-120 mots)
Raconte l'histoire derriere la citation. Le contexte, l'epoque, le personnage. Amene le spectateur dans un univers. Utilise des details concrets : dates, lieux, sensations.
"En l'an soixante-cinq de notre ere, a Rome, un homme fait face a Neron..."

## 4. LE MESSAGE CENTRAL (1-2 min, 100-150 mots)
La citation elle-meme, expliquee, decortiquee, rendue concrete. Chaque mot analyse.
"Quand [auteur] dit '[citation]', il ne parle pas de [interpretation surface]. Il parle de..."

## 5. L'APPROFONDISSEMENT (2-3 min, 100-150 mots)
Applications concretes dans la vie moderne. Connecte la sagesse ancienne au quotidien.
"Ca veut dire quoi concretement ? Ca veut dire que demain matin, quand ton alarme sonne..."

## 6. LE CLIMAX EMOTIONNEL (3-4 min, 60-80 mots)
La revelation finale. Le moment ou tout se connecte. Rythme LENT, phrases COURTES. Chaque phrase est une bombe.
"Et c'est LA que tu comprends. [Pause] Tout ce que tu as traverse. [Pause] Chaque echec. [Pause] Chaque nuit blanche. [Pause] C'etait le PRIX."

## 7. CONCLUSION + CTA (4-5 min, 40-60 mots)
Referme l'arc narratif. Rappelle le hook. Appel a l'action puissant.
"Alors maintenant tu sais. La question c'est : qu'est-ce que tu vas en faire ? Save cette video. Envoie-la a quelqu'un qui en a besoin. Et surtout, reviens demain."

# FORMAT JSON STRICT
Retourne UNIQUEMENT un objet JSON valide. Pas de markdown, pas de backticks, pas de texte avant ou apres.

{
  "hook": "Question choc (8-15 mots)",
  "citation": "La citation complete",
  "auteur": "Nom de l'auteur",
  "epoque": "Epoque/contexte (ex: Rome, 65 apr. J-C)",
  "takeaway": "Lecon percutante en 15-25 mots",
  "script_complet": "Le script narration complet (400-700 mots). STRUCTURE en 7 parties. Utilise [Pause] pour marquer les silences strategiques (5-8 par script).",
  "hook_text": "Texte court affiche 3 premieres secondes (5-8 mots max)",
  "image_prompts": ["prompt 1 en anglais", "prompt 2", "... (15-20 prompts)"],
  "categorie": "stoicisme | philosophie | business | spiritualite | psychologie",
  "tags": ["mot1", "mot2", "mot3", "mot4", "mot5", "mot6", "mot7", "mot8"],
  "cta_text": "Phrase d'appel a l'action finale",
  "mood": "dark_motivation | contemplative | warrior | rebirth | resilience"
}

# REGLES IMAGE PROMPTS (15-20, en anglais)
IMPORTANT : Les images sont affichees DANS L'ORDRE pendant la narration. Chaque image correspond a un bloc de ~30 mots du script. Les images DOIVENT illustrer ce qui est dit a ce moment precis.

Chaque prompt doit evoquer un visuel cinematique. Style a ajouter dans chaque prompt :
"dark moody cinematic lighting, dramatic shadows, teal and orange color grading, 4k ultrarealistic photography, no text no words no writing"

Correspondance obligatoire narration/images :
- Image 1 : illustre le CROCHET (scene d'ouverture, mystere)
- Images 2-3 : illustre la PROMESSE (tension, attente)
- Images 4-7 : illustre l'HISTOIRE (epoque, personnage, contexte historique)
- Images 8-12 : illustre le MESSAGE CENTRAL (metaphores, symboles de la citation)
- Images 13-16 : illustre l'APPROFONDISSEMENT (vie moderne, applications concretes)
- Images 17-19 : illustre le CLIMAX (intensite maximale, revelation, emotion)
- Image 20 : illustre la CONCLUSION (lumiere, espoir, horizon)

Categories de visuels a varier :
- Statues antiques (grecques, romaines) avec lumiere dramatique
- Paysages dramatiques (montagnes brume, ocean dechaine, foret sombre)
- Silhouettes humaines (homme seul falaise, couloir sombre)
- Scenes urbaines nocturnes (skyline, neon, pluie beton)
- Gros plans symboliques (poing serre, oeil gros plan, flamme)
- Art abstrait / AI art (geometrie sacree, fractales, energie)

# REGLE ABSOLUE SUR LES ACCENTS
Tu DOIS OBLIGATOIREMENT utiliser TOUS les accents francais : e, e, e, a, a, o, u, u, i, i, c, e.
JAMAIS ecrire sans accents. Si tu ecris un seul mot sans ses accents, le script est REJETE.

# REGLE ABSOLUE SUR LES NOMBRES
Tu DOIS ecrire TOUS les nombres en LETTRES dans le script_complet. Le script est lu par un TTS.
- "10 000" -> "dix mille" | "100" -> "cent" | "2025" -> "deux mille vingt-cinq"
- "50%" -> "cinquante pour cent" | "1er" -> "premier"
JAMAIS de chiffres arabes (0-9) dans le script_complet. Tout en lettres.

# REGLE SUR LES MOTS ANGLAIS
Dans script_complet, ecris les mots anglais en phonetique francaise :
- "mindset" -> "maindsete" | "burnout" -> "beurnaoute" | "leadership" -> "lideurshippe"
- "coaching" -> "cotchingue" | "focus" -> "fokeusse" | "business" -> "biznesse"
Note : dans les AUTRES champs JSON, tu peux ecrire les mots normalement.

# STYLE
- Phrases COURTES pour la tension (5-10 mots)
- Phrases LONGUES pour la reflexion (15-25 mots)
- Tutoiement OBLIGATOIRE
- Ton : mentor dur mais bienveillant
- Transitions naturelles : "Ecoute-moi bien...", "Et c'est la que ca change tout..."
- [Pause] = silence avant les phrases puissantes (5-8 par script)
- ZERO remplissage, CHAQUE mot doit compter
- Varie le rythme : phrases courtes rapides -> pause -> phrase longue impactante

# AUTEURS VARIES
Stoiciens, entrepreneurs, philosophes, leaders spirituels, ecrivains, scientifiques, guerriers...

VERIFIE : script_complet fait-il 400-700 mots ? TOUS les accents ? AUCUN chiffre arabe ? Mots anglais en phonetique ? 15-20 image_prompts ?"""


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
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ],
    }

    logger.info("Calling Kie.ai LLM (deepseek-chat)...")
    with httpx.Client(timeout=180) as client:
        resp = client.post(KIE_CHAT_URL, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()

    if "choices" not in data:
        error_msg = data.get("msg", data.get("message", str(data)))
        raise RuntimeError(f"Kie.ai API error: {error_msg}")

    return data["choices"][0]["message"]["content"]


def generate_content(exclusion_text: str = "") -> dict:
    """Appelle Kie.ai LLM pour generer le contenu. Retourne le JSON parse."""
    user_prompt = f"""Cree le contenu TikTok motivationnel/philosophique du jour.

{exclusion_text}

INSTRUCTIONS :
1. script_complet entre 400 et 700 mots
2. 15-20 image_prompts cinematiques en anglais
3. Structure en 7 parties (hook, promesse, histoire, message, approfondissement, climax, conclusion)
4. Hook qui arrete le scroll
5. JAMAIS la meme citation que celles listees ci-dessus
6. Tags = mots-cles SANS espaces, minuscules, pour hashtags TikTok
7. TOUS les accents francais OBLIGATOIRES
8. TOUS les nombres en LETTRES
9. Mots anglais en phonetique francaise dans script_complet
10. mood = l'ambiance globale de la video

Retourne UNIQUEMENT le JSON, sans backticks, sans texte avant ou apres."""

    raw_text = _call_kie_llm(SYSTEM_PROMPT, user_prompt)
    content = _parse_json(raw_text)
    content = _validate(content)
    logger.info(
        f"Content generated: {content['auteur']} | "
        f"{len(content['script_complet'].split())} words | "
        f"{len(content['image_prompts'])} images"
    )
    return content


def _parse_json(text: str) -> dict:
    """Extrait le JSON de la reponse Claude (avec ou sans backticks)."""
    # Supprime les backticks markdown si presents
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

    # Word count
    words = content["script_complet"].split()
    word_count = len(words)
    if word_count < config.SCRIPT_MIN_WORDS:
        raise ValueError(f"Script trop court: {word_count} mots (min {config.SCRIPT_MIN_WORDS})")
    if word_count > config.SCRIPT_MAX_WORDS + 50:  # petite marge
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
    content.setdefault("cta_text", "Save cette video")
    content.setdefault("categorie", "philosophie")
    content.setdefault("tags", [])
    content.setdefault("mood", "dark_motivation")
    content.setdefault("epoque", "")

    return content
