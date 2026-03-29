"""Generation sous-titres ASS karaoke — highlight mot-par-mot."""
import re
import logging
from . import config

logger = logging.getLogger("citations-v3")


def _format_ass_time(seconds: float, max_duration: float = 9999) -> str:
    """Convertit secondes -> H:MM:SS.CC (format ASS)."""
    seconds = max(0, min(seconds, max_duration + 1))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds % 1) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _merge_punctuation(raw_tokens: list[str]) -> tuple[list[str], list[int]]:
    """Fusionne la ponctuation standalone dans le mot precedent.

    Retourne (display_words, timing_index_map) ou timing_index_map[i]
    est l'index du raw_token correspondant au display_word[i].
    (Port direct du fix de fix_subtitle_sync_v2.py)
    """
    words = []
    timing_index_map = []

    for i, token in enumerate(raw_tokens):
        if re.match(r"^[?!.,;:\u2026]+$", token) and words:
            words[-1] += token
            # Ne PAS ajouter au timing_index_map — skip ce timepoint
        else:
            words.append(token)
            timing_index_map.append(i)

    return words, timing_index_map


def _build_word_timings(
    words: list[str],
    timing_index_map: list[int],
    word_timings: list[dict],
    total_duration: float,
) -> list[float]:
    """Calcule les temps de debut de chaque mot affiche."""
    word_starts = []

    if word_timings and len(word_timings) >= len(words) * 0.8:
        # Utiliser les timepoints TTS avec mapping correct
        for i in range(len(words)):
            timing_idx = timing_index_map[i] if i < len(timing_index_map) else -1
            if 0 <= timing_idx < len(word_timings):
                word_starts.append(max(0, word_timings[timing_idx]["time"]))
            else:
                # Extrapoler pour les mots au-dela des timepoints
                if word_timings:
                    last_time = word_timings[-1]["time"]
                    remaining = len(words) - i
                    time_per_word = (total_duration - last_time) / max(remaining, 1)
                    word_starts.append(last_time + (i - len(words) + remaining) * time_per_word)
                else:
                    word_starts.append(i * total_duration / max(len(words), 1))
    else:
        # Fallback : estimation proportionnelle basee sur les caracteres
        weights = []
        for w in words:
            letters = re.sub(r"[^a-zA-Z\u00e0-\u00ff]", "", w)
            weight = max(len(letters), 1)
            if re.search(r"[.!?]$", w):
                weight += 4
            elif re.search(r"[,;:]$", w):
                weight += 2
            weights.append(weight)

        total_weight = sum(weights) or 1
        time_per_unit = total_duration / total_weight
        cum_time = 0.0
        for w_weight in weights:
            word_starts.append(cum_time)
            cum_time += w_weight * time_per_unit

    return word_starts


def _group_words(
    words: list[str], max_per_group: int = None
) -> list[dict]:
    """Regroupe les mots en phrases courtes (2-3 mots, break sur ponctuation)."""
    if max_per_group is None:
        max_per_group = config.SUBTITLE_WORDS_PER_GROUP

    groups = []
    current_words = []
    current_indices = []

    for i, word in enumerate(words):
        current_words.append(word)
        current_indices.append(i)

        ends_with_punct = bool(re.search(r"[.!?,;:]$", word))
        if (ends_with_punct and len(current_words) >= 2) or len(current_words) >= max_per_group + 1:
            groups.append({"words": list(current_words), "indices": list(current_indices)})
            current_words = []
            current_indices = []

    if current_words:
        # Mot(s) restant(s) : fusionner avec le dernier groupe si 1 seul
        if len(current_words) == 1 and groups:
            groups[-1]["words"].extend(current_words)
            groups[-1]["indices"].extend(current_indices)
        else:
            groups.append({"words": current_words, "indices": current_indices})

    return groups


def generate_ass(
    script: str,
    word_timings: list[dict],
    total_duration: float,
    hook_text: str = "",
    cta_text: str = "Save cette video",
) -> str:
    """Genere le contenu ASS complet avec karaoke mot-par-mot."""

    # 1. Nettoyer le script pour affichage
    clean = re.sub(r"\[Pause[^\]]*\]", "", script, flags=re.I)
    clean = re.sub(r"\n", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    raw_tokens = [w for w in clean.split() if w]

    # 2. Fusionner ponctuation + mapping index
    words, timing_index_map = _merge_punctuation(raw_tokens)

    # 3. Calculer timings
    word_starts = _build_word_timings(words, timing_index_map, word_timings, total_duration)

    # 4. Grouper les mots
    groups = _group_words(words)

    logger.info(
        f"Subtitles: {len(words)} display words, {len(groups)} groups, "
        f"{len(word_timings)} timepoints"
    )

    # 5. Construire l'ASS
    hl = config.SUBTITLE_HL_COLOR      # Dore highlight
    nl = config.SUBTITLE_NORMAL_COLOR  # Blanc normal
    bg = config.SUBTITLE_BG_COLOR      # Fond noir
    font = config.SUBTITLE_FONT
    fs = config.SUBTITLE_FONT_SIZE
    margin_v = config.SUBTITLE_MARGIN_V

    ass = f"""[Script Info]
Title: Citation du Jour V3
ScriptType: v4.00+
PlayResX: {config.VIDEO_WIDTH}
PlayResY: {config.VIDEO_HEIGHT}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Karaoke,{font},{fs},{nl},&H000000FF,&H00000000,{bg},1,0,0,0,100,100,0,0,3,5,0,2,60,60,{margin_v},1
Style: Hook,{font},{config.SUBTITLE_HOOK_SIZE},&H00FFFF00,&H000000FF,&H00000000,&HB0000000,1,0,0,0,100,100,0,0,3,5,0,5,80,80,750,1
Style: CTA,{font},{config.SUBTITLE_CTA_SIZE},&H00FFFFFF,&H000000FF,&H00000000,&H90000000,1,0,0,0,100,100,0,0,3,4,0,5,60,60,500,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    # Hook text (0.2s -> 3.5s avec fade)
    if hook_text:
        ass += (
            f"Dialogue: 1,{_format_ass_time(0.2)},{_format_ass_time(3.5)},"
            f"Hook,,0,0,0,,{{\\fad(300,500)}}{hook_text}\n"
        )

    # Karaoke mot-par-mot
    for group in groups:
        for w_idx, word in enumerate(group["words"]):
            global_idx = group["indices"][w_idx]
            word_start = word_starts[global_idx] if global_idx < len(word_starts) else 0

            # Fin = debut du mot suivant, ou +0.8s pour le dernier
            if global_idx + 1 < len(words) and global_idx + 1 < len(word_starts):
                word_end = word_starts[global_idx + 1]
            else:
                word_end = min(total_duration, word_start + 0.8)

            # Construire le texte avec highlight sur le mot courant
            parts = []
            for i, w in enumerate(group["words"]):
                if i == w_idx:
                    parts.append(f"{{\\c{hl}}}{w}{{\\c{nl}}}")
                else:
                    parts.append(w)
            text = " ".join(parts)

            ass += (
                f"Dialogue: 0,{_format_ass_time(word_start, total_duration)},"
                f"{_format_ass_time(word_end, total_duration)},"
                f"Karaoke,,0,0,0,,{text}\n"
            )

    # CTA (dernieres 4 secondes avec fade in)
    if cta_text:
        cta_start = max(0, total_duration - 4)
        ass += (
            f"Dialogue: 1,{_format_ass_time(cta_start)},"
            f"{_format_ass_time(total_duration + 0.5)},"
            f"CTA,,0,0,0,,{{\\fad(500,0)}}{cta_text}\n"
        )

    return ass
