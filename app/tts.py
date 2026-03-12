"""Google TTS v1beta1 — SSML, corrections prononciation, timepoints."""
import re
import json
import base64
import logging
from dataclasses import dataclass, field
from pathlib import Path
import httpx
from . import config
from .utils import number_to_french, get_audio_duration

logger = logging.getLogger("citations-v3")


@dataclass
class AudioResult:
    audio_path: str
    duration: float
    word_timings: list[dict] = field(default_factory=list)
    original_words: list[str] = field(default_factory=list)
    word_count: int = 0


# ============================================================
# Corrections prononciation pour TTS francais
# (port direct du JS existant — 30+ regles)
# ============================================================
CORRECTIONS: list[tuple[re.Pattern, str]] = [
    # Lettres muettes francaises
    (re.compile(r"\bestomac\b", re.I), "estoma"),
    (re.compile(r"\btabac\b", re.I), "taba"),
    (re.compile(r"\bclerc\b", re.I), "claire"),
    (re.compile(r"\bporc\b", re.I), "pore"),
    (re.compile(r"\bblanc\b", re.I), "blan"),
    (re.compile(r"\bfranc\b", re.I), "fran"),
    (re.compile(r"\brespect\b", re.I), "respeh"),
    (re.compile(r"\baspect\b", re.I), "aspeh"),
    (re.compile(r"\binstinct\b", re.I), "instin"),
    (re.compile(r"\bdistinct\b", re.I), "distin"),
    (re.compile(r"\bsuccinct\b", re.I), "sucsin"),
    # Noms propres
    (re.compile(r"\bNietzsche\b", re.I), "Nitche"),
    (re.compile(r"\bSchopenhauer\b", re.I), "Chopennaweur"),
    (re.compile(r"\bThoreau\b", re.I), "Toro"),
    (re.compile(r"\bEckhart Tolle\b", re.I), "Eckart Tol\u00e9"),
    (re.compile(r"\bEpict\u00e8te\b", re.I), "\u00c9pict\u00e8te"),
    (re.compile(r"\bRumi\b", re.I), "Roumi"),
    (re.compile(r"\bSto\u00efciens?\b"), "Sto-iciens"),
    # Mots anglais -> phonetique francaise
    (re.compile(r"\bmindsets?\b", re.I), "ma\u00efndes\u00e8te"),
    (re.compile(r"\bfeedback\b", re.I), "fidebake"),
    (re.compile(r"\bburnouts?\b", re.I), "beurnaoute"),
    (re.compile(r"\bcoaching\b", re.I), "cotchingue"),
    (re.compile(r"\bleadership\b", re.I), "lideurshippe"),
    (re.compile(r"\bscrollers?\b", re.I), "scrol\u00e9"),
    (re.compile(r"\bfocus\b", re.I), "fokeusse"),
    (re.compile(r"\bfocuser?\b", re.I), "fok\u00e9uss\u00e9"),
    (re.compile(r"\bself-made\b", re.I), "selfe m\u00e9de"),
    (re.compile(r"\bhustle\b", re.I), "heusseul"),
    (re.compile(r"\bgrowth\b", re.I), "groce"),
    (re.compile(r"\bbusiness\b", re.I), "biznesse"),
    (re.compile(r"\bsuccess\b", re.I), "seucs\u00e8sse"),
    (re.compile(r"\bskills?\b", re.I), "skile"),
    (re.compile(r"\bstartup\b", re.I), "starteuppe"),
    (re.compile(r"\bgame\s*changer\b", re.I), "gu\u00e9\u00efme tch\u00e9\u00efndjeur"),
    (re.compile(r"\bchallenge\b", re.I), "tchalindje"),
    (re.compile(r"\bflow\b", re.I), "flo"),
    (re.compile(r"\bpower\b", re.I), "paoueur"),
    (re.compile(r"\bwinner\b", re.I), "ouineur"),
    (re.compile(r"\bloser\b", re.I), "louzeur"),
    (re.compile(r"\bboost(?:er)?\b", re.I), "boust\u00e9"),
    (re.compile(r"\bnetwork(?:ing)?\b", re.I), "n\u00e8tew\u00eburking"),
    (re.compile(r"\boverth?inking\b", re.I), "oveurssinkingue"),
    (re.compile(r"\bgrind(?:er)?\b", re.I), "gra\u00efnd\u00e9"),
    (re.compile(r"\bsave\b", re.I), "s\u00e9ve"),
    (re.compile(r"\bfollow\b", re.I), "folo"),
    # Abreviations
    (re.compile(r"\betc\b\.?", re.I), "ets\u00e9t\u00e9ra"),
    (re.compile(r"\bvs\.?\b", re.I), "versuce"),
    # Liaison francaise
    (re.compile(r"\bplus\b(?=\s+[aeiouy\u00e9\u00e8\u00ea\u00e0\u00e2\u00f4\u00f9\u00fb\u00ee])", re.I), "pluz"),
]


def _clean_script(raw: str) -> str:
    """Nettoie le script brut (supprime [Pause], en-tetes de sections, normalise espaces)."""
    text = re.sub(r"\[Pause[^\]]*\]", "", raw, flags=re.I)
    # Supprimer les en-tetes de sections LLM (ex: "1. INTRO HOOK (50-80 mots)")
    text = re.sub(
        r"^\s*\d{1,2}\.\s*[A-ZÉÈÊÀÂÔÙÛÎ][A-ZÉÈÊÀÂÔÙÛÎ\s&']+(?:\([^)]*\))?\s*$",
        "", text, flags=re.MULTILINE,
    )
    # Supprimer les indications de mots entre parentheses (ex: "(150-200 mots)")
    text = re.sub(r"\(\d+-\d+\s*mots?\)", "", text, flags=re.I)
    # Supprimer les titres de sections en majuscules seuls sur une ligne
    text = re.sub(r"^\s*(?:INTRO(?:\s+HOOK)?|CONTEXTE|CONCLUSION|CTA|CLIMAX|EXERCICE|OBJECTION|REVELATION|APPLICATION|GENESE|CITATION EXPLIQUEE)[^\n]*$", "", text, flags=re.MULTILINE | re.I)
    # Supprimer lignes "---" restantes
    text = re.sub(r"^-{2,}\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _convert_numbers(text: str) -> str:
    """Convertit les nombres en mots francais (safety net)."""
    # Nombres avec separateurs (10 000, 1 000 000)
    text = re.sub(
        r"\d{1,3}(?:[\s\u00a0]\d{3})+",
        lambda m: number_to_french(int(re.sub(r"[\s\u00a0]", "", m.group()))),
        text,
    )
    # Pourcentages
    text = re.sub(
        r"(\d+)\s*%",
        lambda m: f"{number_to_french(int(m.group(1)))} pour cent",
        text,
    )
    # Ordinaux
    text = re.sub(r"\b1er\b", "premier", text, flags=re.I)
    text = re.sub(r"\b1\u00e8re\b", "premi\u00e8re", text, flags=re.I)
    text = re.sub(
        r"(\d+)(?:e|eme|ème)\b",
        lambda m: f"{number_to_french(int(m.group(1)))}i\u00e8me",
        text,
        flags=re.I,
    )
    # Nombres restants
    text = re.sub(
        r"\b\d+\b",
        lambda m: number_to_french(int(m.group())) if int(m.group()) <= 999_999_999_999 else m.group(),
        text,
    )
    return text


def _apply_corrections(text: str) -> str:
    """Applique les corrections de prononciation."""
    for pattern, replacement in CORRECTIONS:
        text = pattern.sub(replacement, text)
    return text


def _escape_xml(text: str) -> str:
    """Echappe les caracteres speciaux XML/SSML."""
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace('"', "&quot;")
    return text


def _build_ssml(corrected_words: list[str]) -> str:
    """Construit le SSML avec marks et pauses intelligentes."""
    parts = ["<speak>"]
    for i, word in enumerate(corrected_words):
        is_last = i == len(corrected_words) - 1
        safe_word = _escape_xml(word)
        parts.append(f'<mark name="w{i}"/>{safe_word} ')

        # Systeme de pauses intelligent
        if re.search(r"[?]$", word):
            parts.append('<break time="600ms"/>')
        elif re.search(r"[!]$", word):
            parts.append('<break time="550ms"/>')
        elif re.search(r"[.]$", word) and not is_last:
            parts.append('<break time="450ms"/>')
        elif re.search(r"[\u2026]$", word) or re.search(r"\.{2,}$", word):
            parts.append('<break time="750ms"/>')
        elif re.search(r"[:]$", word):
            parts.append('<break time="400ms"/>')
        elif re.search(r"[;]$", word):
            parts.append('<break time="300ms"/>')
        elif re.search(r"[,]$", word):
            parts.append('<break time="200ms"/>')
        elif re.search(r"[\u2014\u2013-]$", word) and not is_last:
            parts.append('<break time="350ms"/>')

    parts.append("</speak>")
    return "".join(parts)


def _split_ssml_chunks(corrected_words: list[str], max_bytes: int = None) -> list[list[str]]:
    """Decoupe les mots en chunks si le SSML depasse max_bytes."""
    if max_bytes is None:
        max_bytes = config.TTS_MAX_SSML_BYTES

    full_ssml = _build_ssml(corrected_words)
    if len(full_ssml.encode("utf-8")) <= max_bytes:
        return [corrected_words]

    # Split en chunks sur les fins de phrases
    chunks = []
    current_chunk: list[str] = []
    for word in corrected_words:
        current_chunk.append(word)
        test_ssml = _build_ssml(current_chunk)
        if len(test_ssml.encode("utf-8")) > max_bytes - 200:
            # Trouver le dernier point/fin de phrase dans le chunk
            split_idx = len(current_chunk) - 1
            for j in range(len(current_chunk) - 1, max(0, len(current_chunk) - 20), -1):
                if re.search(r"[.!?]$", current_chunk[j]):
                    split_idx = j + 1
                    break
            chunks.append(current_chunk[:split_idx])
            current_chunk = current_chunk[split_idx:]

    if current_chunk:
        chunks.append(current_chunk)
    return chunks


def _synthesize_chunk(ssml: str) -> tuple[bytes, list[dict]]:
    """Appelle Google TTS v1beta1 pour un chunk SSML."""
    url = f"https://texttospeech.googleapis.com/v1beta1/text:synthesize?key={config.GCP_API_KEY}"
    body = {
        "input": {"ssml": ssml},
        "voice": {
            "languageCode": "fr-FR",
            "name": config.TTS_VOICE,
            "ssmlGender": "MALE",
        },
        "audioConfig": {
            "audioEncoding": "MP3",
            "speakingRate": config.TTS_SPEED,
            "pitch": config.TTS_PITCH,
            "sampleRateHertz": config.TTS_SAMPLE_RATE,
            "effectsProfileId": ["headphone-class-device"],
        },
        "enableTimePointing": ["SSML_MARK"],
    }

    with httpx.Client(timeout=60) as client:
        resp = client.post(url, json=body)
        resp.raise_for_status()
        data = resp.json()

    audio_bytes = base64.b64decode(data["audioContent"])
    timepoints = []
    for tp in data.get("timepoints", []):
        mark = tp.get("markName", "")
        if mark.startswith("w"):
            idx = int(mark[1:])
            timepoints.append({"index": idx, "time": tp["timeSeconds"]})

    return audio_bytes, timepoints


def generate_audio(script: str, filename: str) -> AudioResult:
    """Pipeline complet : clean -> convert -> correct -> SSML -> TTS -> save."""
    # 1. Clean
    cleaned = _clean_script(script)

    # 2. Garder les mots originaux (pour sous-titres)
    original_words = [w for w in cleaned.split() if w]

    # 3. Convertir nombres + corrections prononciation
    converted = _convert_numbers(cleaned)
    corrected = _apply_corrections(converted)
    corrected_words = [w for w in corrected.split() if w]

    logger.info(f"TTS: {len(original_words)} original words, {len(corrected_words)} corrected words")

    # 4. Split en chunks si necessaire
    chunks = _split_ssml_chunks(corrected_words)
    logger.info(f"TTS: {len(chunks)} chunk(s)")

    # 5. Synthetiser chaque chunk
    all_audio = []
    all_timepoints = []
    time_offset = 0.0

    for i, chunk_words in enumerate(chunks):
        ssml = _build_ssml(chunk_words)
        audio_bytes, timepoints = _synthesize_chunk(ssml)

        # Sauver le chunk temporairement
        chunk_path = f"{config.AUDIO_DIR}/{filename}_chunk{i}.mp3"
        Path(chunk_path).write_bytes(audio_bytes)
        all_audio.append(chunk_path)

        # Ajuster les timepoints avec l'offset
        for tp in timepoints:
            # Recalculer l'index global
            global_idx = tp["index"]
            for prev_chunk in chunks[:i]:
                global_idx += len(prev_chunk)
            all_timepoints.append({"index": global_idx, "time": tp["time"] + time_offset})

        # Calculer la duree du chunk
        chunk_duration = get_audio_duration(chunk_path)
        time_offset += chunk_duration

    # 6. Concatener si plusieurs chunks
    output_path = f"{config.AUDIO_DIR}/{filename}.mp3"
    if len(all_audio) == 1:
        import shutil
        shutil.move(all_audio[0], output_path)
    else:
        # Concat via ffmpeg
        concat_list = f"{config.AUDIO_DIR}/{filename}_concat.txt"
        with open(concat_list, "w") as f:
            for p in all_audio:
                f.write(f"file '{p}'\n")

        from .utils import run_ffmpeg
        run_ffmpeg(f'ffmpeg -y -f concat -safe 0 -i "{concat_list}" -c copy "{output_path}"')

        # Cleanup chunks
        for p in all_audio:
            Path(p).unlink(missing_ok=True)
        Path(concat_list).unlink(missing_ok=True)

    duration = get_audio_duration(output_path)
    logger.info(f"TTS: audio generated — {duration:.1f}s, {len(all_timepoints)} timepoints")

    return AudioResult(
        audio_path=output_path,
        duration=duration,
        word_timings=all_timepoints,
        original_words=original_words,
        word_count=len(original_words),
    )
