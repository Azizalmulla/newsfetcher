from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.services.pdf_text import ExtractedBlock, ExtractedPage


@dataclass(frozen=True)
class OcrPageResult:
    provider: str
    model: str
    text: str
    blocks: list[ExtractedBlock]
    raw: dict[str, Any]


def local_stub_ocr(page: ExtractedPage, *, page_image_hint: str = "") -> OcrPageResult:
    """Deterministic offline OCR fallback for tests/dev when Mistral is unavailable."""
    if page.text.strip():
        text = page.text
        blocks = page.blocks
        note = "reused_weak_text_layer"
    else:
        text = (
            f"[local-ocr stub] Page {page.page_number} scanned content. "
            f"{page_image_hint}".strip()
        )
        blocks = [
            ExtractedBlock(
                block_index=0,
                text=text,
                bbox_x=0.05,
                bbox_y=0.05,
                bbox_w=0.9,
                bbox_h=0.2,
                confidence=0.55,
            )
        ]
        note = "synthetic_empty_page"
    return OcrPageResult(
        provider="local_stub",
        model="local-ocr-stub-v1",
        text=text,
        blocks=blocks,
        raw={"note": note, "page_number": page.page_number},
    )


def mistral_ocr_page(
    *,
    pdf_bytes: bytes,
    page_number: int,
    settings: Settings | None = None,
) -> OcrPageResult:
    """Call Mistral OCR when key + pinned model are configured.

    Raises ValueError when credentials/model are missing so callers can fall back.
    """
    cfg = settings or get_settings()
    if not cfg.mistral_api_key:
        raise ValueError("MISTRAL_API_KEY is not configured")
    if not cfg.mistral_ocr_model:
        raise ValueError("MISTRAL_OCR_MODEL must be pinned from official docs before use")

    # Documented Mistral OCR HTTP shape may evolve — keep call isolated and raw-logged.
    url = "https://api.mistral.ai/v1/ocr"
    headers = {
        "Authorization": f"Bearer {cfg.mistral_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": cfg.mistral_ocr_model,
        "document": {
            "type": "document_url",
            # Caller should prefer upload URL; for Phase 7 we keep this path explicit.
            "document_url": f"data:application/pdf;base64,{_b64(pdf_bytes)}",
        },
        "pages": [page_number - 1],
    }
    with httpx.Client(timeout=60.0) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    text_parts: list[str] = []
    blocks: list[ExtractedBlock] = []
    pages = data.get("pages") or []
    for page in pages:
        markdown = page.get("markdown") or page.get("text") or ""
        if markdown:
            text_parts.append(str(markdown))
        for idx, block in enumerate(page.get("blocks") or []):
            block_text = str(block.get("text") or "")
            bbox = block.get("bbox") or [0, 0, 1, 1]
            blocks.append(
                ExtractedBlock(
                    block_index=idx,
                    text=block_text,
                    bbox_x=float(bbox[0]) if len(bbox) > 0 else 0.0,
                    bbox_y=float(bbox[1]) if len(bbox) > 1 else 0.0,
                    bbox_w=float(bbox[2]) if len(bbox) > 2 else 1.0,
                    bbox_h=float(bbox[3]) if len(bbox) > 3 else 1.0,
                    confidence=float(block.get("confidence") or 0.8),
                )
            )
    text = "\n".join(text_parts).strip()
    if not blocks and text:
        blocks = [
            ExtractedBlock(
                block_index=0,
                text=text,
                bbox_x=0.05,
                bbox_y=0.05,
                bbox_w=0.9,
                bbox_h=0.9,
                confidence=0.8,
            )
        ]
    return OcrPageResult(
        provider="mistral",
        model=cfg.mistral_ocr_model,
        text=text,
        blocks=blocks,
        raw=data if isinstance(data, dict) else {"response": data},
    )


def resolve_page_ocr(
    page: ExtractedPage,
    *,
    pdf_bytes: bytes,
    force_ocr: bool = False,
    settings: Settings | None = None,
) -> OcrPageResult:
    cfg = settings or get_settings()
    from app.services.pdf_text import text_layer_is_weak

    if not force_ocr and not text_layer_is_weak(page):
        return OcrPageResult(
            provider="text_layer",
            model="pypdf",
            text=page.text,
            blocks=page.blocks,
            raw={"source": "text_layer"},
        )

    if cfg.ocr_provider == "mistral" and cfg.mistral_api_key and cfg.mistral_ocr_model:
        try:
            return mistral_ocr_page(
                pdf_bytes=pdf_bytes, page_number=page.page_number, settings=cfg
            )
        except Exception as exc:  # noqa: BLE001
            stub = local_stub_ocr(page, page_image_hint=f"mistral_fallback:{exc}")
            return OcrPageResult(
                provider=stub.provider,
                model=stub.model,
                text=stub.text,
                blocks=stub.blocks,
                raw={**stub.raw, "mistral_error": str(exc)},
            )

    return local_stub_ocr(page)


def _b64(data: bytes) -> str:
    import base64

    return base64.b64encode(data).decode("ascii")
