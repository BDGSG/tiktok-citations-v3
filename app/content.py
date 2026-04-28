"""Content generation v4 — 3 angles éditoriaux (A, B, D) avec personas distinctes.

Angle A — Stoïcisme féminin (rupture, charge mentale, deuil, corps, féminin sigma)
Angle B — Sagesse africaine francophone (proverbes wolof/peul/bambara/lingala + penseurs africains)
Angle D — Philosophes femmes oubliées (Hildegarde, Hypatie, Christine de Pizan, Beauvoir, etc.)

Chaque angle a sa voix éditoriale propre. Le pipeline tourne en rotation pour ne pas
saturer un angle.
"""
from __future__ import annotations

import json
import os
import random
import re
from pathlib import Path
from typing import Optional

import httpx
import logging

from . import config
from . import supabase_client

logger = logging.getLogger("citations-v3")

# ─────────────────────────────────────────────────────────────────────────────
# Database
# ─────────────────────────────────────────────────────────────────────────────

_PHILOSOPHERS_PATH = Path(__file__).parent / "data" / "philosophers.json"
_philosophers_cache: list[dict] | None = None


def _load_philosophers() -> list[dict]:
    global _philosophers_cache
    if _philosophers_cache is None:
        with open(_PHILOSOPHERS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        _philosophers_cache = data["thinkers"]
        logger.info(f"Philosophers v4: loaded {len(_philosophers_cache)} thinkers")
    return _philosophers_cache


# ─────────────────────────────────────────────────────────────────────────────
# Editorial angles
# ─────────────────────────────────────────────────────────────────────────────

ANGLES = {
    "A": {
        "label": "Stoïcisme féminin",
        "voice_id": "XB0fDUnXU5powFXDhCwa",  # ElevenLabs - Charlotte (FR female, contemplative)
        "audience": "Femmes 25-45 ans qui traversent rupture, burnout, charge mentale, deuil. Cherchent une voix grave qui parle vrai sans condescendance.",
        "tone": "contemplative-précise, ferme sans dureté, jamais infantilisante. Tutoiement direct, vocabulaire concret du quotidien féminin (cycle, fatigue, regard porté sur soi). Phrases courtes pour la frappe, longues pour l'apaisement.",
        "themes_priority": ["solitude", "rupture", "charge mentale", "deuil", "corps", "récupération", "regard de soi", "cycle"],
        "hook_patterns": [
            "À celle qui lit ça à 23h47…",
            "Tu peux pleurer ET rester debout. C'est exactement ce que disait…",
            "Un homme antique a écrit pour toi. Sans le savoir.",
            "Avant Beauvoir, une femme du Moyen Âge a écrit ces mots qu'on a oubliés.",
            "Marc Aurèle a écrit ça à 3h du matin. Toi tu vas le lire à la même heure.",
            "Ce que les hommes appellent force, elles l'appellent endurance.",
        ],
        "image_style_seed": "soft natural lighting, warm cinematic film grain, nature textures (water, autumn leaves, stone, candlelight), feminine silhouettes (ancient marble statues of women, hands holding tea, woman walking alone), muted earth tones with golden hour, intimate composition, no faces visible, vertical 9:16",
        "cta_examples": [
            "Tu es d'accord ?",
            "Garde cette phrase pour les jours où tu doutes.",
            "Partage à celle qui en a besoin ce soir.",
            "Note-le. Tu y reviendras.",
        ],
        "hashtags": ["pourtoi", "stoicisme", "femmesigma", "developpementpersonnel", "lacherprise"],
    },
    "B": {
        "label": "Sagesse africaine francophone",
        "voice_id": "ErXwobaYiN019PkySvjV",  # ElevenLabs - Antoni (warm masculine, griot tone)
        "audience": "Diaspora francophone Afrique de l'Ouest, jeunes adultes 18-35, fiers de leurs racines, cherchent une voix qui rend l'oralité sage actuelle.",
        "tone": "voix de griot moderne, chaleureuse, posée. Mélange français châtié et expressions issues de l'oralité (incipit type 'Au pays où je viens…'). Tutoiement respectueux. Évite les clichés afrocentriques et les caricatures.",
        "themes_priority": ["communauté", "patience", "transmission orale", "ancêtres", "honneur", "ubuntu", "voyage", "résistance"],
        "hook_patterns": [
            "Au pays où je viens, on dit…",
            "Avant Marc Aurèle, ce sage de Tombouctou écrivait déjà…",
            "Ce proverbe wolof a deux mille ans. Il vient d'écraser ton ego.",
            "Quand le baobab tombe, les chèvres pleurent. Mais ce que disent les anciens…",
            "L'Europe ne te l'apprendra pas. Mais ta grand-mère, peut-être.",
            "Sankofa. Reviens chercher ce que tu as oublié.",
        ],
        "image_style_seed": "warm African golden hour, terracotta and ochre palette, baobab silhouettes, traditional textures (mud cloth bogolan, kente, woven baskets, calabashes), elder hands holding objects, vertical compositions of African landscapes (Sahel, savanna, river deltas), no recognizable faces, ancient Saharan manuscripts, vertical 9:16",
        "cta_examples": [
            "Sais-tu qui le disait avant nous ?",
            "Envoie ça à un cousin, à une sœur. Ils en ont besoin.",
            "Quel proverbe ta grand-mère t'a transmis ? Réponds en commentaire.",
            "Note ce mot. Tu le diras un jour à tes enfants.",
        ],
        "hashtags": ["pourtoi", "sagesseafricaine", "ubuntu", "afrique", "diaspora", "proverbe"],
    },
    "D": {
        "label": "Philosophes femmes oubliées",
        "voice_id": "EXAVITQu4vr4xnSDxMAC",  # ElevenLabs - Bella (younger female, narrative, scholarly)
        "audience": "Public 20-40 mixte mais penché féminin, cultivé ou avide de l'être, fatigué des mêmes 5 philosophes hommes cités partout. Veut découvrir.",
        "tone": "curieux-érudit, presque narratif. Pose toujours le contexte historique de la femme citée (qui elle était, l'époque, ce qu'elle a osé). Ton émerveillé sans être révérencieux, parfois indigné de l'oubli historique.",
        "themes_priority": ["histoire effacée", "courage intellectuel", "création", "savoir", "résistance", "transmission", "voix retrouvée"],
        "hook_patterns": [
            "Personne ne t'a parlé d'elle au lycée. Pourtant…",
            "Elle a écrit ces mots en 1405. Avant Descartes, avant Kant.",
            "Hypatie d'Alexandrie a été assassinée pour ses idées. Voici lesquelles.",
            "Tu connais Nietzsche. Tu n'as jamais entendu parler d'elle. Erreur historique.",
            "La phrase la plus radicale du XIIe siècle a été écrite par une femme.",
            "Avant Sartre, elle était. Avant Beauvoir, elle l'avait dit.",
        ],
        "image_style_seed": "Renaissance painting aesthetic, oil paint texture, candlelight chiaroscuro, illuminated medieval manuscripts, marble busts of unknown women, cathedral light, ancient libraries, parchment scrolls, telling hands, no recognizable contemporary faces, sepia and gold palette, vertical 9:16",
        "cta_examples": [
            "Tu connaissais ?",
            "Cherche son nom. Lis son livre. Honore-la.",
            "Dis-moi en commentaire si tu en as déjà entendu parler.",
            "Garde ce nom. Tu le retrouveras.",
        ],
        "hashtags": ["pourtoi", "philosophie", "femmesphilosophes", "histoire", "feminisme", "savoir"],
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Narrative structures (preserved from v3, light tweaks)
# ─────────────────────────────────────────────────────────────────────────────

NARRATIVE_STRUCTURES = {
    "classic": "Hook 0-3s → promesse 3-15s → contexte historique 15s-1m → message central 1-2m → application moderne 2-3m → climax 3-4m → conclusion + CTA boucle 4-5m.",
    "debate": "Question existentielle 0-5s → arguments pour 5-45s → arguments contre 45s-1m30 → la citation tranche 1m30-3m → résolution 3-4m + CTA.",
    "what_if": "Scénario hypothétique 0-10s → exploration 10s-1m → la citation comme révélation 1-2m → impact concret sur ta vie 2-3m → retour au scénario transformé 3-4m + CTA.",
    "letter": "Adresse intime 0-5s → constat sur le spectateur 5-45s → la citation comme conseil personnel 45s-2m → ta propre interprétation 2-3m → signature 3-4m + CTA.",
    "countdown": "Annonce numérotée 0-5s → point 1 5-30s → point 2 30s-1m → point 3 = la citation 1-2m → synthèse 2-3m + CTA.",
    "encounter": "Rencontre racontée 0-10s → décor de l'époque 10s-45s → la voix de l'auteur 45s-2m → ce qu'elle te disait à toi sans le savoir 2-3m → ce que tu ramènes 3-4m + CTA.",
}


def _pick_narrative_structure() -> str:
    recent = supabase_client.get_recent_structures(days=10, platform="tiktok")
    keys = list(NARRATIVE_STRUCTURES.keys())
    unused = [k for k in keys if k not in recent]
    if not unused:
        unused = keys
    return random.choice(unused)


def _pick_angle() -> str:
    """Rotate through angles A/B/D, biased to under-served lately."""
    try:
        recent = supabase_client.get_recent_angles(days=7, platform="tiktok")
    except Exception:
        recent = []
    counts = {"A": 0, "B": 0, "D": 0}
    for a in recent:
        if a in counts:
            counts[a] += 1
    # Pick min-count angle; tie → random
    min_count = min(counts.values())
    candidates = [a for a, c in counts.items() if c == min_count]
    return random.choice(candidates)


def _pick_thinkers_for_angle(angle: str, count: int = 5) -> list[dict]:
    philosophers = _load_philosophers()
    pool = [p for p in philosophers if angle in p.get("angles", [])]
    if not pool:
        logger.warning(f"No thinkers for angle {angle}, falling back to all")
        pool = philosophers

    recent = supabase_client.get_recent_authors(days=14, platform="tiktok")
    recent_set = {a.lower() for a in recent}
    unused = [p for p in pool if p["name"].lower() not in recent_set]
    if len(unused) < count:
        unused = pool

    random.shuffle(unused)
    return unused[:count]


# ─────────────────────────────────────────────────────────────────────────────
# OpenRouter / Claude
# ─────────────────────────────────────────────────────────────────────────────

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4-6")


def _call_claude(system: str, user_prompt: str) -> str:
    if not OPENROUTER_KEY:
        raise RuntimeError("OPENROUTER_API_KEY missing in env")
    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://citations-v3.coolify.inkora.art",
        "X-Title": "citations-v3",
    }
    body = {
        "model": OPENROUTER_MODEL,
        "max_tokens": 8192,
        "temperature": 0.85,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ],
    }
    logger.info(f"Calling Claude via OpenRouter ({OPENROUTER_MODEL})...")
    with httpx.Client(timeout=240) as client:
        resp = client.post(OPENROUTER_URL, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()
    if "choices" not in data:
        raise RuntimeError(f"OpenRouter API error: {data}")
    return data["choices"][0]["message"]["content"]


# ─────────────────────────────────────────────────────────────────────────────
# Prompt template
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT_TEMPLATE = r"""Tu es l'auteur d'un compte TikTok français à très haute qualité éditoriale, spécialisé sur l'angle suivant :

# ANGLE ÉDITORIAL : {angle_label}

**Audience** : {audience}

**Voix** : {tone}

**Thèmes prioritaires** : {themes}

# MISSION
Génère le SCRIPT NARRATIF complet d'une vidéo TikTok au format 9:16 — 28 secondes ciblées (entre 22 et 34s strictement), lue à voix haute. Le script doit faire **65 à 95 mots** (vitesse lecture 0.92x, voix calme).

ATTENTION : nous visons 70 % de retention à 3 secondes. Le hook 0-3s est CRITIQUE. Si l'audience décroche, l'algo TikTok te tue.

# AUTEUR DE LA CITATION
Choisis UN auteur dans cette liste (rotation pour éviter la répétition) :
{author_choices}

Tu DOIS choisir parmi ces noms — leur catégorie/époque conditionne le ton.

# STRUCTURE NARRATIVE
{structure_description}

# HOOK 0-3s — RÈGLES STRICTES
Choisis UN pattern parmi ceux-ci, OU crée une variante dans le même esprit :
{hook_examples}

JAMAIS : "Salut", "Bonjour", "Aujourd'hui on va parler de…", "Bienvenue".

# CITATION
- La citation doit être réelle ou fortement plausible (esprit de l'auteur). Pour les proverbes africains, mentionne le peuple ("Un proverbe wolof dit…").
- Traduction française fluide, JAMAIS d'anglais.
- Maximum 25 mots dans la citation elle-même.

# CTA FINAL
Dans les 5 derniers mots, finis sur l'un de ces patterns (ou inspire-toi) :
{cta_examples}

# IMAGE PROMPTS (10 EXACTEMENT)
Style visuel signature angle {angle_letter} :
{image_style_seed}

Chaque prompt 40-80 mots EN ANGLAIS, ultra-détaillé : sujet, composition, lumière, ambiance, style. JAMAIS de visages reconnaissables (silhouettes / mains / objets / paysages / sculptures anciennes uniquement). JAMAIS de texte ou mots dans l'image.

# RÈGLES DURES (non négociables)
- Tous les accents français (é è ê à ï î ô û ç) : OBLIGATOIRES
- Tous les nombres ÉCRITS EN LETTRES (vingt-trois, pas 23)
- Mots anglais en phonétique française si présents (mindset → maindsete)
- 65-95 mots dans script_complet, JAMAIS plus de 95 mots
- 10 image_prompts EXACTEMENT
- Tutoiement OBLIGATOIRE
- Pas d'emoji dans le script (sauf dans hashtags si demandé)

# FORMAT JSON STRICT (sans backticks)
{{
  "angle": "{angle_letter}",
  "hook": "Texte 8-15 mots qui arrête le scroll",
  "hook_text_overlay": "Texte court 4-7 mots affiché 0-3s en superposition",
  "citation": "Citation française complète, max 25 mots",
  "auteur": "Nom exact (depuis la liste)",
  "epoque": "Date approximative ou siècle/lieu (ex: 'Sénégal, sagesse orale ancestrale')",
  "takeaway": "Phrase mémorable de 12-20 mots qui résume",
  "script_complet": "Le script complet 65-95 mots — ce qui sera lu par la voix off",
  "image_prompts": ["prompt 1 EN ANGLAIS 40-80 mots", "prompt 2", "...exactement 10"],
  "cta_text": "Texte court à afficher en bas de la dernière scène",
  "mood": "contemplative | warrior | rebirth | dignified | grief | tender",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6"]
}}

VÉRIFIE AVANT DE RÉPONDRE :
- script_complet entre 65 et 95 mots ?
- 10 image_prompts ?
- Hook 0-3s qui choque sans crier ?
- CTA dans les 5 derniers mots ?
- Tous les accents ?"""


def _build_user_prompt(exclusion_text: str) -> str:
    return f"""Crée le contenu TikTok du jour pour cet angle éditorial.

{exclusion_text}

Respecte STRICTEMENT le format JSON. Pas de backticks, pas de texte avant/après le JSON."""


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def build_exclusion_text(history: list[dict]) -> str:
    if not history:
        return ""
    lines = ["CITATIONS DEJA UTILISEES (ne JAMAIS les répéter) :"]
    seen_authors = set()
    for row in history[-30:]:
        author = row.get("auteur", "")
        citation = row.get("citation", "")
        if citation:
            lines.append(f"- \"{citation}\" — {author}")
        if author:
            seen_authors.add(author)
    if seen_authors:
        lines.append(f"\nAuteurs déjà cités récemment : {', '.join(sorted(seen_authors))}")
        lines.append("Privilégie un auteur DIFFÉRENT.")
    return "\n".join(lines)


def generate_content(exclusion_text: str = "", angle: Optional[str] = None) -> dict:
    """Generate one piece of content for the rotation.

    Args:
        exclusion_text: previously used citations to avoid.
        angle: optional override ('A'|'B'|'D'). If None, picked by rotation.
    """
    angle = angle or _pick_angle()
    angle_cfg = ANGLES[angle]
    structure_key = _pick_narrative_structure()
    structure_desc = NARRATIVE_STRUCTURES[structure_key]

    candidates = _pick_thinkers_for_angle(angle, count=5)
    author_choices = "\n".join(
        f"- {c['name']} ({c['category']}, {c['era']}) — connu pour : {c['famous_for']}. "
        f"Thèmes : {', '.join(c['key_themes'])}"
        for c in candidates
    )

    system = SYSTEM_PROMPT_TEMPLATE.format(
        angle_letter=angle,
        angle_label=angle_cfg["label"],
        audience=angle_cfg["audience"],
        tone=angle_cfg["tone"],
        themes=", ".join(angle_cfg["themes_priority"]),
        author_choices=author_choices,
        structure_description=structure_desc,
        hook_examples="\n".join(f"  - {h}" for h in angle_cfg["hook_patterns"]),
        cta_examples="\n".join(f"  - {c}" for c in angle_cfg["cta_examples"]),
        image_style_seed=angle_cfg["image_style_seed"],
    )

    user_prompt = _build_user_prompt(exclusion_text)

    from . import hook_gate
    content: dict | None = None
    for attempt in range(2):
        raw_text = _call_claude(system, user_prompt)
        candidate = _parse_json(raw_text)
        candidate = _validate(candidate, angle)
        if hook_gate.passes(candidate.get("hook", "")):
            content = candidate
            break
        if attempt == 0:
            user_prompt += (
                "\n\nNOTE : ton hook précédent était trop faible (commençait par un cliché ou "
                "ne tutoyait pas directement). Réécris un hook 0-3s avec 'tu', spécifique, frappant. "
                "Modèles: 'À celle qui lit ça à 23h47…' / 'Avant Sartre, elle l'avait dit.' / "
                "'Ce proverbe wolof a deux mille ans.'"
            )
        else:
            content = candidate
            logger.warning("Hook gate failed twice — proceeding anyway")
    assert content is not None

    # Inject angle metadata for downstream modules (TTS voice, image style, etc.)
    content["_angle"] = angle
    content["_angle_label"] = angle_cfg["label"]
    content["_voice_id"] = angle_cfg["voice_id"]
    content["_hashtags_suffix"] = angle_cfg["hashtags"]

    try:
        supabase_client.save_to_history(
            content,
            platform="tiktok",
            narrative_structure=structure_key,
            angle=angle,
        )
    except Exception as e:
        logger.warning(f"supabase save failed: {e}")

    word_count = len(content["script_complet"].split())
    logger.info(
        f"Content v4: angle={angle} ({angle_cfg['label']}) | "
        f"author={content['auteur']} | structure={structure_key} | "
        f"words={word_count} | images={len(content['image_prompts'])}"
    )
    return content


def _parse_json(text: str) -> dict:
    cleaned = re.sub(r"```(?:json)?\s*", "", text)
    cleaned = re.sub(r"```\s*$", "", cleaned)
    cleaned = cleaned.strip()
    return json.loads(cleaned)


def _validate(content: dict, angle: str) -> dict:
    required = ["hook", "citation", "auteur", "script_complet", "image_prompts"]
    for field in required:
        if field not in content:
            raise ValueError(f"Missing field: {field}")

    words = content["script_complet"].split()
    word_count = len(words)
    # New range: 60-100 (target 65-95)
    if word_count < 50:
        raise ValueError(f"Script too short: {word_count} words (need >=50)")
    if word_count > 110:
        logger.warning(f"Script slightly long: {word_count} words (target ≤95)")

    if len(content["image_prompts"]) < 8:
        raise ValueError(f"Not enough image prompts: {len(content['image_prompts'])} (need 8+)")
    if len(content["image_prompts"]) > 12:
        content["image_prompts"] = content["image_prompts"][:10]
        logger.warning("Trimmed image_prompts to 10")

    content.setdefault("hook_text_overlay", content.get("hook", "")[:50])
    content.setdefault("cta_text", "Note ce nom.")
    content.setdefault("mood", "contemplative")
    content.setdefault("tags", [])
    content.setdefault("epoque", "")
    content.setdefault("takeaway", "")
    content["angle"] = angle

    return content
