"""Hook quality gate.

Rough heuristic to score the 0-3s hook. Not a real retention predictor —
it just refuses obviously weak hooks (greetings, generic openers, vague
questions) before we spend $$$ on TTS + image gen.

If score < THRESHOLD we ask the LLM to retry once. If it fails again we
let the pipeline proceed with a warning (no infinite loops in production).
"""
from __future__ import annotations

import re
import logging

logger = logging.getLogger("citations-v3")

THRESHOLD = 65  # below this, ask for a retry

WEAK_OPENERS = [
    r"^salut\b",
    r"^bonjour\b",
    r"^hey\b",
    r"^bienvenue\b",
    r"^aujourd'hui\b",
    r"^aujourdhui\b",
    r"^dans cette vidéo",
    r"^je vais te parler",
    r"^on va parler",
    r"^laisse[-\s]moi te dire",
]
STRONG_PATTERNS = [
    r"\b(tu|toi)\b",                          # direct address
    r"\b\d{1,2}h\d{0,2}\b",                   # specific hour ("3h47")
    r"avant (Marc|Sénèque|Nietzsche|Sartre|Beauvoir)",
    r"^(personne ne|elle a|au pays|à celle qui|ce proverbe)",
    r"^(à\s|tu peux|tu sais|imagine)",
]
SHORT_HOOK_BOOST = re.compile(r".{1,80}$")  # < 80 chars
QUESTION_MARK = re.compile(r"\?$")


def score_hook(hook: str) -> tuple[int, list[str]]:
    """Return (score 0-100, reasons[])."""
    hook = (hook or "").strip()
    if not hook:
        return 0, ["empty"]

    score = 50
    reasons: list[str] = []
    lower = hook.lower()

    for pat in WEAK_OPENERS:
        if re.search(pat, lower):
            score -= 30
            reasons.append(f"weak opener: {pat}")
            break

    for pat in STRONG_PATTERNS:
        if re.search(pat, lower):
            score += 12
            reasons.append(f"strong pattern: {pat}")

    if SHORT_HOOK_BOOST.match(hook):
        score += 8
        reasons.append("short concise hook")

    if QUESTION_MARK.search(hook):
        score += 6
        reasons.append("ends on a question")

    word_count = len(hook.split())
    if word_count < 4:
        score -= 10
        reasons.append("too short (<4 words)")
    elif word_count > 20:
        score -= 8
        reasons.append("too long (>20 words)")

    score = max(0, min(100, score))
    return score, reasons


def passes(hook: str) -> bool:
    score, reasons = score_hook(hook)
    if score < THRESHOLD:
        logger.warning(f"Hook gate FAIL ({score}): {hook!r} — {reasons}")
        return False
    logger.info(f"Hook gate OK ({score}): {hook!r}")
    return True
