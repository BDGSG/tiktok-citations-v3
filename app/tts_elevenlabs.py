"""ElevenLabs TTS provider — multilingual_v2 with character timestamps.

Returns the same AudioResult shape as the Google TTS provider so it's a
drop-in replacement.

Voice IDs (default per angle, override via content["_voice_id"]) :
  - Charlotte (XB0fDUnXU5powFXDhCwa) — FR female, contemplative (angle A)
  - Antoni    (ErXwobaYiN019PkySvjV) — warm male, griot tone     (angle B)
  - Bella     (EXAVITQu4vr4xnSDxMAC) — younger female, narrative (angle D)
"""
from __future__ import annotations

import base64
import json
import logging
import os
from pathlib import Path

import httpx

from . import config
from .tts import (
    AudioResult,
    _apply_corrections,
    _clean_script,
    _convert_numbers,
)
from .utils import get_audio_duration

logger = logging.getLogger("citations-v3")

ELEVEN_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVEN_MODEL = os.getenv("ELEVENLABS_MODEL", "eleven_multilingual_v2")
ELEVEN_TIMESTAMPS_URL = (
    "https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps"
)


def _build_payload(text: str) -> dict:
    """Voice settings tuned for slow contemplative reading + subtle prosody.
    Higher stability = calmer; similarity_boost = stay close to voice timbre.
    """
    return {
        "text": text,
        "model_id": ELEVEN_MODEL,
        "voice_settings": {
            "stability": 0.62,
            "similarity_boost": 0.78,
            "style": 0.45,         # add some emotional inflection (v2 supports this)
            "use_speaker_boost": True,
        },
        "output_format": "mp3_44100_128",
    }


def _normalize_alignment(payload: dict, words: list[str]) -> list[dict]:
    """Convert ElevenLabs character alignment → per-word time points
    matching the Google TTS schema [{"index": n, "time": seconds}, ...]."""
    align = payload.get("normalized_alignment") or payload.get("alignment")
    if not align:
        return []
    chars = align.get("characters") or []
    starts = align.get("character_start_times_seconds") or []
    if not chars or not starts:
        return []

    # Reconstruct word boundaries by walking characters.
    timings: list[dict] = []
    word_idx = 0
    in_word = False
    word_start_time: float | None = None

    for c, t in zip(chars, starts):
        is_space = c.isspace() or c in (",", ".", ";", ":", "—", "–")
        if not is_space:
            if not in_word:
                word_start_time = t
                in_word = True
        else:
            if in_word:
                if word_idx < len(words):
                    timings.append({"index": word_idx, "time": float(word_start_time)})
                word_idx += 1
                in_word = False
                word_start_time = None
    if in_word and word_idx < len(words):
        timings.append({"index": word_idx, "time": float(word_start_time)})

    return timings


def _synthesize(text: str, voice_id: str) -> tuple[bytes, list[dict]]:
    """Call ElevenLabs with-timestamps endpoint. Returns (mp3_bytes, raw_alignment)."""
    if not ELEVEN_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY missing in env")
    url = ELEVEN_TIMESTAMPS_URL.format(voice=voice_id)
    headers = {
        "xi-api-key": ELEVEN_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body = _build_payload(text)
    logger.info(
        f"ElevenLabs TTS: voice={voice_id} model={ELEVEN_MODEL} "
        f"chars={len(text)}"
    )
    with httpx.Client(timeout=120) as client:
        resp = client.post(url, headers=headers, json=body)
    if resp.status_code != 200:
        # Surface useful error
        try:
            payload = resp.json()
        except Exception:
            payload = {"raw": resp.text[:300]}
        raise RuntimeError(
            f"ElevenLabs HTTP {resp.status_code}: {payload}"
        )
    data = resp.json()
    audio_b64 = data.get("audio_base64") or data.get("audio")
    if not audio_b64:
        raise RuntimeError(f"ElevenLabs: no audio in response keys={list(data.keys())}")
    audio = base64.b64decode(audio_b64)
    return audio, data


def generate_audio(script: str, filename: str, voice_id: str | None = None) -> AudioResult:
    """ElevenLabs equivalent of tts.generate_audio()."""
    if not voice_id:
        voice_id = os.getenv("ELEVENLABS_DEFAULT_VOICE", "XB0fDUnXU5powFXDhCwa")

    cleaned = _clean_script(script)
    original_words = [w for w in cleaned.split() if w]
    converted = _convert_numbers(cleaned)
    corrected = _apply_corrections(converted)
    corrected_words = [w for w in corrected.split() if w]
    text_to_speak = " ".join(corrected_words)

    audio_bytes, raw = _synthesize(text_to_speak, voice_id)

    output_path = f"{config.AUDIO_DIR}/{filename}.mp3"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_bytes(audio_bytes)

    duration = get_audio_duration(output_path)
    timings = _normalize_alignment(raw, corrected_words)

    if not timings:
        logger.warning(
            "ElevenLabs: no alignment returned, falling back to linear distribution"
        )
        if corrected_words:
            step = duration / max(len(corrected_words), 1)
            timings = [{"index": i, "time": i * step} for i in range(len(corrected_words))]

    # Map corrected → original (1:1 most of the time, fallback linear)
    if len(corrected_words) == len(original_words):
        word_start_times = [
            t["time"] for t in sorted(timings, key=lambda x: x["index"])
        ]
        # Pad with linear if mismatch
        if len(word_start_times) < len(original_words):
            step = duration / max(len(original_words), 1)
            word_start_times.extend(
                step * i for i in range(len(word_start_times), len(original_words))
            )
    else:
        step = duration / max(len(original_words), 1)
        word_start_times = [step * i for i in range(len(original_words))]

    logger.info(
        f"ElevenLabs TTS done: {duration:.1f}s, {len(original_words)} words, "
        f"{len(timings)} timepoints"
    )
    return AudioResult(
        audio_path=output_path,
        duration=duration,
        word_timings=timings,
        original_words=original_words,
        word_start_times=word_start_times,
        word_count=len(original_words),
    )
