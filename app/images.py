"""Generation d'images — Kie.ai Flux Kontext + fallback Hugging Face."""
import re
import asyncio
import logging
from pathlib import Path
import httpx
from . import config

logger = logging.getLogger("citations-v3")

KIE_API_BASE = "https://api.kie.ai/api/v1/flux/kontext"
HF_API_URL = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
BATCH_SIZE = 5
POLL_INTERVAL = 5  # secondes
MAX_TIMEOUT = 180  # secondes par image
MAX_RETRIES = 2

CINEMATIC_SUFFIX = (
    ", dark moody cinematic lighting, dramatic shadows, "
    "teal and orange color grading, 4k ultrarealistic photography, "
    "shot on Sony A7III, shallow depth of field, "
    "no text no words no letters no writing no watermark, "
    "vertical portrait composition, tall narrow frame, 9:16 aspect ratio"
)

FALLBACK_PROMPT = (
    "dark moody abstract background with dramatic shadows and volumetric light, "
    "cinematic teal and orange color grading, 4k ultrarealistic, 9:16 vertical"
)

# Flag global pour eviter de retenter Kie.ai quand les credits sont epuises
_kie_disabled = False


def _clean_prompt(prompt: str) -> str:
    """Supprime les references texte et ajoute le suffix cinematique."""
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


async def _create_task(client: httpx.AsyncClient, prompt: str) -> str:
    """Cree une tache Kie.ai, retourne le taskId."""
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

    # Detecter credits insuffisants
    if data.get("code") == 402 or (data.get("data") is None and "insufficient" in data.get("msg", "").lower()):
        global _kie_disabled
        _kie_disabled = True
        raise RuntimeError(f"Kie.ai: credits insuffisants — {data.get('msg', '')}")

    task_id = (data.get("data") or {}).get("taskId") or data.get("taskId")
    if not task_id:
        raise RuntimeError(f"Kie.ai: pas de taskId dans la reponse: {data}")
    return task_id


async def _poll_task(client: httpx.AsyncClient, task_id: str) -> str:
    """Poll jusqu'a completion, retourne l'URL de l'image."""
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


async def _download_image(client: httpx.AsyncClient, url: str, output_path: str) -> str:
    """Telecharge l'image depuis l'URL."""
    resp = await client.get(url, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    Path(output_path).write_bytes(resp.content)
    return output_path


async def _generate_hf(client: httpx.AsyncClient, prompt: str, output_path: str) -> str:
    """Genere une image via Hugging Face Inference API (FLUX.1-schnell)."""
    resp = await client.post(
        HF_API_URL,
        headers={"Authorization": f"Bearer {config.HF_TOKEN}"},
        json={"inputs": prompt},
        timeout=120,
    )
    if resp.status_code == 503:
        # Modele en chargement, attendre et retenter
        wait = resp.json().get("estimated_time", 30)
        logger.info(f"HF: modele en chargement, attente {wait:.0f}s...")
        await asyncio.sleep(min(wait, 60))
        resp = await client.post(
            HF_API_URL,
            headers={"Authorization": f"Bearer {config.HF_TOKEN}"},
            json={"inputs": prompt},
            timeout=120,
        )
    resp.raise_for_status()
    Path(output_path).write_bytes(resp.content)
    return output_path


async def _generate_single(
    client: httpx.AsyncClient, prompt: str, index: int, filename: str
) -> str:
    """Genere une seule image avec retry. Fallback Kie.ai -> HF."""
    output_path = f"{config.IMAGES_DIR}/{filename}_{index:02d}.png"

    # Tenter Kie.ai si pas desactive
    if not _kie_disabled and config.KIE_API_KEY:
        for attempt in range(MAX_RETRIES + 1):
            try:
                current_prompt = prompt if attempt == 0 else _clean_prompt(FALLBACK_PROMPT)
                task_id = await _create_task(client, current_prompt)
                logger.debug(f"Image {index}: Kie.ai task {task_id} (attempt {attempt + 1})")
                url = await _poll_task(client, task_id)
                await _download_image(client, url, output_path)
                logger.info(f"Image {index}: OK (Kie.ai)")
                return output_path
            except Exception as e:
                if _kie_disabled:
                    logger.warning(f"Image {index}: Kie.ai desactive, bascule sur HF")
                    break
                if attempt < MAX_RETRIES:
                    logger.warning(f"Image {index}: Kie.ai retry {attempt + 1} ({e})")
                else:
                    logger.warning(f"Image {index}: Kie.ai echec apres {MAX_RETRIES + 1} tentatives, bascule sur HF")

    # Fallback Hugging Face
    if config.HF_TOKEN:
        try:
            await _generate_hf(client, prompt, output_path)
            logger.info(f"Image {index}: OK (HuggingFace)")
            return output_path
        except Exception as e:
            logger.error(f"Image {index}: HF aussi en echec: {e}")
            raise
    else:
        raise RuntimeError(f"Image {index}: Kie.ai et HF indisponibles (pas de HF_TOKEN)")


async def generate_all_images(prompts: list[str], filename: str) -> list[str]:
    """Genere toutes les images en batch parallele.

    Args:
        prompts: Liste de prompts bruts (sera nettoye automatiquement)
        filename: Base du nom de fichier (sans extension)

    Returns:
        Liste ordonnee des chemins des images generees
    """
    global _kie_disabled
    _kie_disabled = False  # Reset a chaque run

    cleaned_prompts = [_clean_prompt(p) for p in prompts]
    image_paths: list[str | None] = [None] * len(cleaned_prompts)
    failed_indices: list[int] = []

    async with httpx.AsyncClient() as client:
        for batch_start in range(0, len(cleaned_prompts), BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, len(cleaned_prompts))
            batch_indices = list(range(batch_start, batch_end))

            provider = "HuggingFace" if _kie_disabled else "Kie.ai"
            logger.info(
                f"Image batch {batch_start // BATCH_SIZE + 1} ({provider}): "
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

            # Petite pause entre batches pour eviter rate limiting
            if batch_end < len(cleaned_prompts):
                await asyncio.sleep(2)

    # Fallback pour images echouees : utiliser l'image precedente ou suivante
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

    # Filtrer les None restants (ne devrait pas arriver)
    final_paths = [p for p in image_paths if p is not None]
    logger.info(f"Images: {len(final_paths)}/{len(prompts)} generated successfully")
    return final_paths
