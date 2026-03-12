"""Utilitaires partages : logging, ffmpeg runner, helpers."""
import logging
import subprocess
import re
import unicodedata

logger = logging.getLogger("citations-v3")


def setup_logging():
    """Configure le logging structure."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logger


def run_ffmpeg(cmd: str, timeout: int = 600) -> subprocess.CompletedProcess:
    """Execute une commande FFmpeg avec timeout et capture stderr."""
    logger.info(f"FFmpeg: {cmd[:120]}...")
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, timeout=timeout
    )
    if result.returncode != 0:
        logger.error(f"FFmpeg stderr: {result.stderr[-500:]}")
        raise RuntimeError(f"FFmpeg failed (rc={result.returncode}): {result.stderr[-300:]}")
    return result


def get_audio_duration(path: str) -> float:
    """Retourne la duree d'un fichier audio en secondes via ffprobe."""
    result = subprocess.run(
        f'ffprobe -v error -select_streams a:0 -show_entries stream=duration '
        f'-of default=noprint_wrappers=1:nokey=1 "{path}"',
        shell=True, capture_output=True, text=True, timeout=30,
    )
    return float(result.stdout.strip())


def clean_filename(name: str) -> str:
    """Nettoie un nom pour l'utiliser comme filename (supprime accents, caracteres speciaux)."""
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_str = nfkd.encode("ASCII", "ignore").decode("ASCII")
    cleaned = re.sub(r"[^a-zA-Z0-9]", "_", ascii_str).strip("_")
    return cleaned.lower()[:40]


# ===========================================================
# Convertisseur nombres -> francais (port direct du JS existant)
# ===========================================================
_UNITS = [
    "", "un", "deux", "trois", "quatre", "cinq", "six", "sept",
    "huit", "neuf", "dix", "onze", "douze", "treize", "quatorze",
    "quinze", "seize",
]
_TENS = ["", "", "vingt", "trente", "quarante", "cinquante", "soixante"]


def _convert_below_1000(n: int) -> str:
    if n == 0:
        return ""
    if n < 17:
        return _UNITS[n]
    if n < 20:
        return f"dix-{_UNITS[n - 10]}"
    if n < 70:
        t, u = divmod(n, 10)
        if u == 0:
            return _TENS[t]
        if u == 1:
            return f"{_TENS[t]}-et-un"
        return f"{_TENS[t]}-{_UNITS[u]}"
    if n < 80:
        if n == 70:
            return "soixante-dix"
        if n == 71:
            return "soixante-et-onze"
        r = n - 60
        return f"soixante-{_UNITS[r]}" if r < 17 else f"soixante-dix-{_UNITS[r - 10]}"
    if n < 100:
        u = n - 80
        if u == 0:
            return "quatre-vingts"
        if u < 10:
            return f"quatre-vingt-{_UNITS[u]}"
        if u == 10:
            return "quatre-vingt-dix"
        if u == 11:
            return "quatre-vingt-onze"
        return f"quatre-vingt-{_UNITS[u]}" if u < 17 else f"quatre-vingt-dix-{_UNITS[u - 10]}"
    # 100-999
    h, r = divmod(n, 100)
    if h == 1:
        base = "cent"
    else:
        base = f"{_UNITS[h]} cents" if r == 0 else f"{_UNITS[h]} cent"
    if r > 0:
        base += f" {_convert_below_1000(r)}"
    return base


def number_to_french(n: int) -> str:
    """Convertit un entier en mots francais."""
    if n == 0:
        return "zero"
    if n < 0:
        return f"moins {number_to_french(-n)}"
    if n < 1000:
        return _convert_below_1000(n)
    if n < 1_000_000:
        thousands, remainder = divmod(n, 1000)
        result = "mille" if thousands == 1 else f"{_convert_below_1000(thousands)} mille"
        if remainder > 0:
            result += f" {_convert_below_1000(remainder)}"
        return result
    if n < 1_000_000_000:
        millions, remainder = divmod(n, 1_000_000)
        s = "s" if millions > 1 else ""
        result = f"{_convert_below_1000(millions)} million{s}"
        if remainder > 0:
            result += f" {number_to_french(remainder)}"
        return result
    milliards, remainder = divmod(n, 1_000_000_000)
    s = "s" if milliards > 1 else ""
    result = f"{_convert_below_1000(milliards)} milliard{s}"
    if remainder > 0:
        result += f" {number_to_french(remainder)}"
    return result
