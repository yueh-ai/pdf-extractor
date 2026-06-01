from __future__ import annotations

import math
import os
import threading
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image


PDF_RENDER_SCALE = 2.0
PDF_MIN_RENDER_SCALE = 0.1
DEFAULT_MAX_IMAGE_PIXELS = 178_956_970
_PDFIUM_LOCK = threading.Lock()


class PDFRenderSizeError(ValueError):
    pass


def page_dir_name(page: int) -> str:
    return f"page_{page:04d}"


def estimate_render_pixels(page_size: tuple[float, float], scale: float) -> tuple[int, int, int]:
    width, height = page_size
    width_px = int(math.ceil(float(width) * scale))
    height_px = int(math.ceil(float(height) * scale))
    return width_px, height_px, width_px * height_px


def render_scale_within_pixel_limit(
    page_size: tuple[float, float],
    *,
    page_number: int,
    requested_scale: float = PDF_RENDER_SCALE,
    min_scale: float = PDF_MIN_RENDER_SCALE,
    max_pixels: int = DEFAULT_MAX_IMAGE_PIXELS,
) -> float:
    width, height = float(page_size[0]), float(page_size[1])
    if width <= 0 or height <= 0:
        raise ValueError(f"Page {page_number}: invalid PDF page size {width}x{height}")
    if requested_scale <= 0:
        raise ValueError(f"PDF render scale must be positive, got {requested_scale}")
    if min_scale <= 0:
        raise ValueError(f"Minimum PDF render scale must be positive, got {min_scale}")
    if max_pixels <= 0:
        raise ValueError(f"Maximum image pixels must be positive, got {max_pixels}")

    _, _, requested_pixels = estimate_render_pixels((width, height), requested_scale)
    if requested_pixels <= max_pixels:
        return requested_scale

    min_width, min_height, min_pixels = estimate_render_pixels((width, height), min_scale)
    if min_pixels > max_pixels:
        raise PDFRenderSizeError(
            f"Page {page_number}: render size {min_width}x{min_height} at scale "
            f"{min_scale} exceeds max pixel budget {max_pixels}"
        )

    upper = min(requested_scale, math.sqrt(max_pixels / (width * height)))
    lower = min_scale
    for _ in range(32):
        scale = (lower + upper) / 2
        _, _, pixels = estimate_render_pixels((width, height), scale)
        if pixels <= max_pixels:
            lower = scale
        else:
            upper = scale
    return lower


def get_pdf_page_count(pdf_path: Path) -> int:
    with _PDFIUM_LOCK:
        doc = pdfium.PdfDocument(str(pdf_path))
        try:
            doc.init_forms()
            return len(doc)
        finally:
            doc.close()


def render_page_to_png(
    pdf_path: Path,
    *,
    page_number: int,
    out_path: Path,
    scale: float = PDF_RENDER_SCALE,
    min_scale: float = PDF_MIN_RENDER_SCALE,
    max_pixels: int = DEFAULT_MAX_IMAGE_PIXELS,
) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_name(f".{out_path.name}.tmp")
    with _PDFIUM_LOCK:
        doc = pdfium.PdfDocument(str(pdf_path))
        try:
            doc.init_forms()
            if page_number < 1 or page_number > len(doc):
                raise ValueError(f"Page {page_number} is outside 1-{len(doc)}")
            page = doc.get_page(page_number - 1)
            try:
                render_scale = render_scale_within_pixel_limit(
                    page.get_size(),
                    page_number=page_number,
                    requested_scale=scale,
                    min_scale=min_scale,
                    max_pixels=max_pixels,
                )
                array = page.render(scale=render_scale, rotation=0).to_numpy().copy()
            finally:
                page.close()
        finally:
            doc.close()

    if array.ndim == 3 and array.shape[2] >= 3:
        rgb = array[:, :, :3][:, :, ::-1]
        image = Image.fromarray(rgb, mode="RGB")
    else:
        image = Image.fromarray(array)
    image.save(tmp_path, format="PNG")
    os.replace(tmp_path, out_path)
    return out_path
