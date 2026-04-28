"""TTS provider router.

Picks the provider based on ``TTS_PROVIDER`` env var or whether a voice_id is
given. Defaults to ElevenLabs when ``ELEVENLABS_API_KEY`` is set, otherwise
falls back to Google TTS Neural2 (legacy).
"""
from __future__ import annotations

import os
import logging

from . import tts as google_tts
from .tts import AudioResult

logger = logging.getLogger("citations-v3")

PROVIDER = os.getenv("TTS_PROVIDER", "auto").lower()  # "auto", "elevenlabs", "google"


def _provider_for(voice_id: str | None) -> str:
    if PROVIDER in ("elevenlabs", "google"):
        return PROVIDER
    if voice_id and os.getenv("ELEVENLABS_API_KEY"):
        return "elevenlabs"
    if os.getenv("ELEVENLABS_API_KEY"):
        return "elevenlabs"
    return "google"


def generate_audio(script: str, filename: str, voice_id: str | None = None) -> AudioResult:
    provider = _provider_for(voice_id)
    logger.info(f"TTS router → provider={provider}")
    if provider == "elevenlabs":
        try:
            from . import tts_elevenlabs
            return tts_elevenlabs.generate_audio(script, filename, voice_id=voice_id)
        except Exception as e:
            logger.error(f"ElevenLabs failed, falling back to Google TTS: {e}")
            return google_tts.generate_audio(script, filename)
    return google_tts.generate_audio(script, filename)
