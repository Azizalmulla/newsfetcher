from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from pypdf import PdfReader


@dataclass(frozen=True)
class ExtractedBlock:
    block_index: int
    text: str
    bbox_x: float
    bbox_y: float
    bbox_w: float
    bbox_h: float
    confidence: float = 1.0


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    width: float
    height: float
    text: str
    blocks: list[ExtractedBlock]


def extract_text_layer(pdf_bytes: bytes) -> list[ExtractedPage]:
    """Extract text-layer content and approximate line blocks with normalized bboxes."""
    reader = PdfReader(BytesIO(pdf_bytes))
    pages: list[ExtractedPage] = []
    for page_idx, page in enumerate(reader.pages, start=1):
        width = float(page.mediabox.width) if page.mediabox else 595.0
        height = float(page.mediabox.height) if page.mediabox else 842.0
        raw = page.extract_text() or ""
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        blocks: list[ExtractedBlock] = []
        if lines:
            line_h = 1.0 / max(len(lines), 1)
            for idx, line in enumerate(lines):
                blocks.append(
                    ExtractedBlock(
                        block_index=idx,
                        text=line,
                        bbox_x=0.05,
                        bbox_y=min(0.95, idx * line_h),
                        bbox_w=0.90,
                        bbox_h=max(0.02, line_h * 0.9),
                        confidence=1.0,
                    )
                )
        pages.append(
            ExtractedPage(
                page_number=page_idx,
                width=width,
                height=height,
                text="\n".join(lines),
                blocks=blocks,
            )
        )
    return pages


def text_layer_is_weak(page: ExtractedPage, *, min_chars: int = 40) -> bool:
    return len(page.text.strip()) < min_chars
