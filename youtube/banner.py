"""Generation de la miniature YouTube (thumbnail) via FFmpeg.

Cree une miniature 1280x720 avec :
- Image de fond (premiere image generee)
- Texte CHOC (thumbnail_text)
- Logo en bas a droite
- Gradient overlay pour lisibilite
"""
import os
import logging
from pathlib import Path
from . import config
from app.utils import run_ffmpeg

logger = logging.getLogger("youtube-citations")


def generate_thumbnail(
    background_image: str,
    thumbnail_text: str,
    filename: str,
    author: str = "",
) -> str:
    """Genere une miniature YouTube 1280x720.

    Args:
        background_image: Chemin vers l'image de fond (une des images generees)
        thumbnail_text: Texte court et choc (3-5 mots, majuscules)
        filename: Base du nom de fichier
        author: Nom de l'auteur (affiche en bas)

    Returns:
        Chemin vers la miniature generee
    """
    output_path = f"{config.YT_THUMBNAILS_DIR}/{filename}_thumb.png"
    w = config.THUMB_WIDTH
    h = config.THUMB_HEIGHT

    # Construire le filtre complexe
    font_path = f"{config.FONTS_DIR}/Montserrat-ExtraBold.ttf".replace("\\", "/").replace(":", "\\\\:")
    bg_escaped = background_image.replace("\\", "/")

    # Texte principal : gros, gras, avec ombre
    # Nettoyer le texte pour FFmpeg (echapper les caracteres speciaux)
    text_clean = thumbnail_text.replace("'", "\u2019").replace(":", "\\:")
    author_clean = author.replace("'", "\u2019").replace(":", "\\:")

    # Verifier si le logo existe
    logo_path = config.LOGO_PATH.replace("\\", "/")
    has_logo = os.path.isfile(config.LOGO_PATH)

    if has_logo:
        # Avec logo en bas a droite
        filter_complex = (
            f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
            # Gradient noir en bas pour lisibilite
            f"drawbox=x=0:y=ih*0.55:w=iw:h=ih*0.45:color=black@0.6:t=fill,"
            # Vignette pour profondeur
            f"vignette=PI/4,"
            # Augmenter contraste
            f"eq=contrast=1.2:brightness=-0.05:saturation=1.1,"
            # Texte principal (centre, gros)
            f"drawtext=fontfile='{font_path}':"
            f"text='{text_clean}':"
            f"fontsize=80:fontcolor=white:"
            f"borderw=5:bordercolor=black:"
            f"shadowcolor=black@0.8:shadowx=4:shadowy=4:"
            f"x=(w-text_w)/2:y=(h-text_h)/2-30[bg];"
            # Logo overlay
            f"[1:v]scale=120:-1[logo];"
            f"[bg][logo]overlay=W-w-30:H-h-30"
        )

        # Ajouter le nom de l'auteur si present
        if author:
            filter_complex = (
                f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
                f"drawbox=x=0:y=ih*0.55:w=iw:h=ih*0.45:color=black@0.6:t=fill,"
                f"vignette=PI/4,"
                f"eq=contrast=1.2:brightness=-0.05:saturation=1.1,"
                f"drawtext=fontfile='{font_path}':"
                f"text='{text_clean}':"
                f"fontsize=80:fontcolor=white:"
                f"borderw=5:bordercolor=black:"
                f"shadowcolor=black@0.8:shadowx=4:shadowy=4:"
                f"x=(w-text_w)/2:y=(h-text_h)/2-50,"
                # Nom de l'auteur en dessous
                f"drawtext=fontfile='{font_path}':"
                f"text='— {author_clean}':"
                f"fontsize=36:fontcolor=gold:"
                f"borderw=3:bordercolor=black:"
                f"shadowcolor=black@0.6:shadowx=2:shadowy=2:"
                f"x=(w-text_w)/2:y=(h-text_h)/2+60[bg];"
                f"[1:v]scale=120:-1[logo];"
                f"[bg][logo]overlay=W-w-30:H-h-30"
            )

        cmd = (
            f'ffmpeg -y -i "{bg_escaped}" -i "{logo_path}" '
            f'-filter_complex "{filter_complex}" '
            f'"{output_path}"'
        )
    else:
        # Sans logo
        vf = (
            f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
            f"drawbox=x=0:y=ih*0.55:w=iw:h=ih*0.45:color=black@0.6:t=fill,"
            f"vignette=PI/4,"
            f"eq=contrast=1.2:brightness=-0.05:saturation=1.1,"
            f"drawtext=fontfile='{font_path}':"
            f"text='{text_clean}':"
            f"fontsize=80:fontcolor=white:"
            f"borderw=5:bordercolor=black:"
            f"shadowcolor=black@0.8:shadowx=4:shadowy=4:"
            f"x=(w-text_w)/2:y=(h-text_h)/2-50"
        )

        if author:
            vf += (
                f","
                f"drawtext=fontfile='{font_path}':"
                f"text='— {author_clean}':"
                f"fontsize=36:fontcolor=gold:"
                f"borderw=3:bordercolor=black:"
                f"shadowcolor=black@0.6:shadowx=2:shadowy=2:"
                f"x=(w-text_w)/2:y=(h-text_h)/2+60"
            )

        cmd = (
            f'ffmpeg -y -i "{bg_escaped}" '
            f'-vf "{vf}" '
            f'"{output_path}"'
        )

    run_ffmpeg(cmd, timeout=60)
    logger.info(f"Thumbnail generated: {output_path} (logo={'yes' if has_logo else 'no'})")
    return output_path
