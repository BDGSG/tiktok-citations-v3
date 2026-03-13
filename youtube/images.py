"""Generation d'images — HuggingFace FLUX.1 (prioritaire) + Kie.ai (fallback)."""
import re
import asyncio
import logging
from pathlib import Path
import httpx
from . import config

logger = logging.getLogger("youtube-citations")

# HuggingFace Inference API
HF_MODEL = "black-forest-labs/FLUX.1-schnell"
HF_API_URL = f"https://api-inference.huggingface.co/models/{HF_MODEL}"
HF_TOKEN = config.HF_TOKEN

# Kie.ai (fallback)
KIE_API_BASE = "https://api.kie.ai/api/v1/flux/kontext"

BATCH_SIZE = 5
POLL_INTERVAL = 5
MAX_TIMEOUT = 180
MAX_RETRIES = 2

# Flag global: si HF retourne 402 on bascule tout sur Kie.ai
_hf_credits_exhausted = False

CINEMATIC_SUFFIX = (
    ", dark moody cinematic lighting, dramatic shadows, "
    "teal and orange color grading, 4k ultrarealistic photography, "
    "shot on Sony A7III, shallow depth of field, "
    "no text no words no letters no writing no watermark, "
    "widescreen landscape composition, wide frame, 16:9 aspect ratio"
)

FALLBACK_PROMPT = (
    "dark moody abstract background with dramatic shadows and volumetric light, "
    "cinematic teal and orange color grading, 4k ultrarealistic, 16:9 widescreen"
)


def _clean_prompt(prompt: str) -> str:
    """Supprime les references texte et ajoute le suffix cinematique 16:9."""
    cleaned = re.sub(r"with.*?quote", "", prompt, flags=re.I)
    cleaned = re.sub(r"text.*?saying", "", cleaned, flags=re.I)
    cleaned = re.sub(r"words.*?written", "", cleaned, flags=re.I)
    cleaned = re.sub(r"showing.*?text", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\btext\b", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\bquote\b", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\bwords\b", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\bletters\b", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned + CINEMATIC_SUFFIX


# ============================================================
# HuggingFace FLUX.1 (prioritaire)
# ============================================================

async def _generate_hf(
    client: httpx.AsyncClient, prompt: str, output_path: str
) -> str:
    """Genere une image via HuggingFace Inference API (FLUX.1-schnell)."""
    global _hf_credits_exhausted

    resp = await client.post(
        HF_API_URL,
        headers={
            "Authorization": f"Bearer {HF_TOKEN}",
            "Content-Type": "application/json",
        },
        json={"inputs": prompt},
        timeout=60,
    )

    if resp.status_code == 402:
        _hf_credits_exhausted = True
        raise RuntimeError("HuggingFace: credits exhausted (402)")

    if resp.status_code == 429:
        raise RuntimeError("HuggingFace: rate limited (429)")

    if resp.status_code == 503:
        # Model loading — retry later
        raise RuntimeError("HuggingFace: model loading (503)")

    resp.raise_for_status()

    # La reponse est l'image brute (bytes)
    if len(resp.content) < 1000:
        # Probablement un message d'erreur JSON
        raise RuntimeError(f"HuggingFace: response too small ({len(resp.content)} bytes)")

    Path(output_path).write_bytes(resp.content)
    return output_path


# ============================================================
# Kie.ai Flux Kontext (fallback)
# ============================================================

async def _create_kie_task(client: httpx.AsyncClient, prompt: str) -> str:
    resp = await client.post(
        f"{KIE_API_BASE}/generate",
        headers={
            "Authorization": f"Bearer {config.KIE_API_KEY}",
            "Content-Type": "application/json",
        },
        json={"prompt": prompt, "aspect_ratio": config.IMAGE_ASPECT_RATIO},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    task_id = data.get("data", {}).get("taskId") or data.get("taskId")
    if not task_id:
        raise RuntimeError(f"Kie.ai: pas de taskId: {data}")
    return task_id


async def _poll_kie_task(client: httpx.AsyncClient, task_id: str) -> str:
    elapsed = 0
    while elapsed < MAX_TIMEOUT:
        await asyncio.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
        resp = await client.get(
            f"{KIE_API_BASE}/record-info",
            params={"taskId": task_id},
            headers={"Authorization": f"Bearer {config.KIE_API_KEY}"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        record = data.get("data", data)
        flag = record.get("successFlag", 0)
        if flag == 1:
            url = record.get("resultImageUrl") or record.get("response", {}).get("resultImageUrl")
            if url:
                return url
            raise RuntimeError(f"Kie.ai: success mais pas d'URL: {record}")
        elif flag in (2, 3):
            raise RuntimeError(f"Kie.ai: task failed (flag={flag}): {record}")
    raise TimeoutError(f"Kie.ai: timeout {MAX_TIMEOUT}s pour task {task_id}")


async def _generate_kie(
    client: httpx.AsyncClient, prompt: str, output_path: str
) -> str:
    """Genere une image via Kie.ai Flux Kontext."""
    task_id = await _create_kie_task(client, prompt)
    url = await _poll_kie_task(client, task_id)
    resp = await client.get(url, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    Path(output_path).write_bytes(resp.content)
    return output_path


# ============================================================
# Orchestration : HF prioritaire, Kie.ai fallback
# ============================================================

async def _generate_single(
    client: httpx.AsyncClient, prompt: str, index: int, filename: str
) -> str:
    """Genere une image : essaie HF d'abord, fallback Kie.ai."""
    output_path = f"{config.YT_IMAGES_DIR}/{filename}_{index:03d}.png"

    for attempt in range(MAX_RETRIES + 1):
        current_prompt = prompt if attempt == 0 else _clean_prompt(FALLBACK_PROMPT)

        # Essayer HuggingFace si credits disponibles et token present
        if HF_TOKEN and not _hf_credits_exhausted:
            try:
                await _generate_hf(client, current_prompt, output_path)
                logger.info(f"Image {index}: OK (HuggingFace)")
                return output_path
            except Exception as e:
                logger.warning(f"Image {index}: HF failed ({e}), trying Kie.ai...")

        # Fallback Kie.ai
        try:
            await _generate_kie(client, current_prompt, output_path)
            logger.info(f"Image {index}: OK (Kie.ai)")
            return output_path
        except Exception as e:
            if attempt < MAX_RETRIES:
                logger.warning(f"Image {index}: retry {attempt + 1} ({e})")
            else:
                logger.error(f"Image {index}: FAILED after {MAX_RETRIES + 1} attempts: {e}")
                raise

    return output_path


async def generate_all_images(prompts: list[str], filename: str) -> list[str]:
    """Genere toutes les images 16:9 en batch parallele.

    Priorite HuggingFace FLUX.1-schnell, fallback Kie.ai automatique.
    """
    global _hf_credits_exhausted
    _hf_credits_exhausted = False  # Reset a chaque run

    cleaned_prompts = [_clean_prompt(p) for p in prompts]
    image_paths: list[str | None] = [None] * len(cleaned_prompts)
    failed_indices: list[int] = []

    provider = "HuggingFace" if (HF_TOKEN and not _hf_credits_exhausted) else "Kie.ai"
    logger.info(f"Images: {len(prompts)} prompts, primary provider: {provider}")

    async with httpx.AsyncClient() as client:
        for batch_start in range(0, len(cleaned_prompts), BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, len(cleaned_prompts))
            batch_indices = list(range(batch_start, batch_end))

            logger.info(
                f"Image batch {batch_start // BATCH_SIZE + 1}: "
                f"indices {batch_start}-{batch_end - 1}"
            )

            tasks = [
                _generate_single(client, cleaned_prompts[i], i, filename)
                for i in batch_indices
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in zip(batch_indices, results):
                if isinstance(result, Exception):
                    logger.error(f"Image {i} failed: {result}")
                    failed_indices.append(i)
                else:
                    image_paths[i] = result

            if batch_end < len(cleaned_prompts):
                await asyncio.sleep(2)

    # Fallback pour images echouees
    for i in failed_indices:
        for offset in range(1, len(prompts)):
            if i - offset >= 0 and image_paths[i - offset]:
                image_paths[i] = image_paths[i - offset]
                logger.warning(f"Image {i}: using fallback from image {i - offset}")
                break
            if i + offset < len(prompts) and image_paths[i + offset]:
                image_paths[i] = image_paths[i + offset]
                logger.warning(f"Image {i}: using fallback from image {i + offset}")
                break

    final_paths = [p for p in image_paths if p is not None]
    logger.info(f"Images: {len(final_paths)}/{len(prompts)} generated successfully")
    return final_paths
