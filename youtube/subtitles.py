"""Generation sous-titres ASS karaoke — format 16:9 YouTube."""
import re
import logging
from . import config

logger = logging.getLogger("youtube-citations")


def _format_ass_time(seconds: float, max_duration: float = 9999) -> str:
    seconds = max(0, min(seconds, max_duration + 1))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds % 1) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _merge_punctuation(raw_tokens: list[str]) -> tuple[list[str], list[int]]:
    words = []
    timing_index_map = []
    for i, token in enumerate(raw_tokens):
        if re.match(r"^[?!.,;:\u2026]+$", token) and words:
            words[-1] += token
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
    word_starts = []
    if word_timings and len(word_timings) >= len(words) * 0.8:
        for i in range(len(words)):
            timing_idx = timing_index_map[i] if i < len(timing_index_map) else -1
            if 0 <= timing_idx < len(word_timings):
                word_starts.append(max(0, word_timings[timing_idx]["time"]))
            else:
                if word_timings:
                    last_time = word_timings[-1]["time"]
                    remaining = len(words) - i
                    time_per_word = (total_duration - last_time) / max(remaining, 1)
                    word_starts.append(last_time + (i - len(words) + remaining) * time_per_word)
                else:
                    word_starts.append(i * total_duration / max(len(words), 1))
    else:
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
    cta_text: str = "Abonne-toi et active la cloche",
) -> str:
    """Genere le contenu ASS pour YouTube 16:9."""
    clean = re.sub(r"\[Pause[^\]]*\]", "", script, flags=re.I)
    # Supprimer les en-tetes de sections LLM (ex: "1. INTRO HOOK (50-80 mots)")
    clean = re.sub(
        r"^\s*\d{1,2}\.\s*[A-ZÉÈÊÀÂÔÙÛÎ][A-ZÉÈÊÀÂÔÙÛÎ\s&']+(?:\([^)]*\))?\s*$",
        "", clean, flags=re.MULTILINE,
    )
    clean = re.sub(r"\(\d+-\d+\s*mots?\)", "", clean, flags=re.I)
    clean = re.sub(
        r"^\s*(?:INTRO(?:\s+HOOK)?|HOOK\s+D.OUVERTURE|CONTEXTE(?:\s+\+\s*PROMESSE)?|CONCLUSION|CTA|CLIMAX(?:\s+EMOTIONNEL)?|EXERCICE(?:\s+CONCRET)?|OBJECTION|REVELATION(?:\s+PROFONDE)?|APPLICATION(?:\s+MODERNE|\s+HISTORIQUE)?|GENESE|CITATION\s+(?:EXPLIQUEE|DECRYPTEE)|L.HISTOIRE\s+DU\s+PENSEUR)[^\n]*$",
        "", clean, flags=re.MULTILINE | re.I,
    )
    clean = re.sub(r"^-{2,}\s*$", "", clean, flags=re.MULTILINE)
    clean = re.sub(r"\n", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    raw_tokens = [w for w in clean.split() if w]

    words, timing_index_map = _merge_punctuation(raw_tokens)
    word_starts = _build_word_timings(words, timing_index_map, word_timings, total_duration)
    groups = _group_words(words)

    logger.info(
        f"Subtitles YT: {len(words)} display words, {len(groups)} groups, "
        f"{len(word_timings)} timepoints"
    )

    hl = config.SUBTITLE_HL_COLOR
    nl = config.SUBTITLE_NORMAL_COLOR
    bg = config.SUBTITLE_BG_COLOR
    font = config.SUBTITLE_FONT
    fs = config.SUBTITLE_FONT_SIZE
    margin_v = config.SUBTITLE_MARGIN_V

    ass = f"""[Script Info]
Title: Citation YouTube
ScriptType: v4.00+
PlayResX: {config.VIDEO_WIDTH}
PlayResY: {config.VIDEO_HEIGHT}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Karaoke,{font},{fs},{nl},&H000000FF,&H00000000,{bg},1,0,0,0,100,100,0,0,3,3,0,2,100,100,{margin_v},1
Style: Hook,{font},{config.SUBTITLE_HOOK_SIZE},&H00FFFF00,&H000000FF,&H00000000,&HB0000000,1,0,0,0,100,100,0,0,3,4,0,5,120,120,400,1
Style: CTA,{font},{config.SUBTITLE_CTA_SIZE},&H00FFFFFF,&H000000FF,&H00000000,&H90000000,1,0,0,0,100,100,0,0,3,3,0,5,100,100,300,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    # Hook text (0.5s -> 5s)
    if hook_text:
        ass += (
            f"Dialogue: 1,{_format_ass_time(0.5)},{_format_ass_time(5.0)},"
            f"Hook,,0,0,0,,{{\\fad(400,600)}}{hook_text}\n"
        )

    # Karaoke mot-par-mot
    for group in groups:
        for w_idx, word in enumerate(group["words"]):
            global_idx = group["indices"][w_idx]
            word_start = word_starts[global_idx] if global_idx < len(word_starts) else 0

            if global_idx + 1 < len(words) and global_idx + 1 < len(word_starts):
                word_end = word_starts[global_idx + 1]
            else:
                word_end = min(total_duration, word_start + 0.8)

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

    # CTA (dernieres 6 secondes pour YouTube)
    if cta_text:
        cta_start = max(0, total_duration - 6)
        ass += (
            f"Dialogue: 1,{_format_ass_time(cta_start)},"
            f"{_format_ass_time(total_duration + 0.5)},"
            f"CTA,,0,0,0,,{{\\fad(600,0)}}{cta_text}\n"
        )

    return ass
