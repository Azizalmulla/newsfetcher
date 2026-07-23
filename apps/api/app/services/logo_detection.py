"""Cost-controlled logo detection cascade.

local_screen → fingerprint similarity → (optional) external verify
Never auto-finalizes matches; callers create proposed LogoMatch rows only.
"""

from __future__ import annotations

import hashlib
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class LogoCandidate:
    confidence: float
    bbox_x: float
    bbox_y: float
    bbox_w: float
    bbox_h: float
    stage: str
    evidence: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LogoDetectResult:
    provider: str
    model: str
    candidates: list[LogoCandidate]
    screened_out: int = 0


def image_fingerprint(image_bytes: bytes) -> str:
    """Cheap content fingerprint for local screening (not cryptographic identity)."""
    # Sample evenly spaced bytes + length to keep cost low.
    if not image_bytes:
        return hashlib.sha256(b"empty").hexdigest()
    step = max(1, len(image_bytes) // 64)
    sample = bytes(image_bytes[i] for i in range(0, len(image_bytes), step))
    return hashlib.sha256(sample + len(image_bytes).to_bytes(8, "big")).hexdigest()


def fingerprint_similarity(a: str, b: str) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    # Hex nibble Hamming → similarity in [0,1]
    mismatches = sum(1 for x, y in zip(a, b, strict=True) if x != y)
    return 1.0 - (mismatches / len(a))


class LogoDetector(ABC):
    name: str
    model: str

    @abstractmethod
    def detect(
        self,
        *,
        image_bytes: bytes,
        template_fingerprints: list[tuple[str, str, float]],
        # (template_id, fingerprint, min_confidence)
    ) -> LogoDetectResult:
        raise NotImplementedError


class LocalCascadeLogoDetector(LogoDetector):
    """Deterministic local cascade for tests/dev and cheap first-pass screening."""

    name = "local"
    model = "local-logo-cascade-v1"

    def detect(
        self,
        *,
        image_bytes: bytes,
        template_fingerprints: list[tuple[str, str, float]],
    ) -> LogoDetectResult:
        page_fp = image_fingerprint(image_bytes)
        candidates: list[LogoCandidate] = []
        screened_out = 0

        # Stage 1: if image is tiny / empty, screen out entirely.
        if len(image_bytes) < 32:
            return LogoDetectResult(
                provider=self.name,
                model=self.model,
                candidates=[],
                screened_out=len(template_fingerprints),
            )

        for template_id, template_fp, min_conf in template_fingerprints:
            sim = fingerprint_similarity(page_fp, template_fp)
            # Cheap screen: require some similarity; exact fixture match → high score.
            if sim < 0.35:
                screened_out += 1
                continue
            # Stage 2: map similarity into a candidate region (deterministic placement).
            digest = hashlib.sha256(f"{template_id}:{page_fp}".encode()).digest()
            x = (digest[0] / 255.0) * 0.7
            y = (digest[1] / 255.0) * 0.7
            confidence = min(0.99, 0.40 + sim * 0.60)
            stage = "embedding_similarity" if sim >= 0.55 else "local_screen"
            if confidence < min_conf:
                # Keep as weak candidate for audit but mark stage.
                stage = "local_screen_below_threshold"
            candidates.append(
                LogoCandidate(
                    confidence=confidence,
                    bbox_x=round(x, 4),
                    bbox_y=round(y, 4),
                    bbox_w=0.12,
                    bbox_h=0.08,
                    stage=stage,
                    evidence={
                        "template_id": template_id,
                        "page_fingerprint": page_fp[:16],
                        "template_fingerprint": template_fp[:16],
                        "similarity": round(sim, 4),
                        "min_confidence": min_conf,
                        "cascade": ["local_screen", stage],
                    },
                    raw={"similarity": sim},
                )
            )

        # Sort strongest first; cap to control cost of any later external verify.
        candidates.sort(key=lambda c: c.confidence, reverse=True)
        return LogoDetectResult(
            provider=self.name,
            model=self.model,
            candidates=candidates[:20],
            screened_out=screened_out,
        )


class ExternalLogoDetector(LogoDetector):
    """Optional external verifier hook. Requires pinned model + API key."""

    name = "external"

    def __init__(self, settings: Settings) -> None:
        self.model = settings.logo_external_model
        self._api_key = settings.logo_external_api_key
        self._endpoint = settings.logo_external_endpoint

    def detect(
        self,
        *,
        image_bytes: bytes,
        template_fingerprints: list[tuple[str, str, float]],
    ) -> LogoDetectResult:
        if not self._api_key or not self.model:
            raise ValueError(
                "LOGO_EXTERNAL_API_KEY and LOGO_EXTERNAL_MODEL must be set for external provider"
            )
        # Cost control: never call external without local pre-screen.
        local = LocalCascadeLogoDetector().detect(
            image_bytes=image_bytes, template_fingerprints=template_fingerprints
        )
        if not local.candidates:
            return LogoDetectResult(
                provider=self.name,
                model=self.model or "unset",
                candidates=[],
                screened_out=local.screened_out,
            )
        # Placeholder: re-tag top local candidates as externally verified-pending.
        # Real HTTP call stays behind config; no silent unpaid fan-out.
        verified: list[LogoCandidate] = []
        for cand in local.candidates[:5]:
            if cand.confidence < 0.55:
                continue
            verified.append(
                LogoCandidate(
                    confidence=min(0.99, cand.confidence + 0.05),
                    bbox_x=cand.bbox_x,
                    bbox_y=cand.bbox_y,
                    bbox_w=cand.bbox_w,
                    bbox_h=cand.bbox_h,
                    stage="external_verify",
                    evidence={
                        **cand.evidence,
                        "external_endpoint_configured": bool(self._endpoint),
                        "note": "external verify stub — wire live API after cost approval",
                    },
                    raw={**cand.raw, "external": True},
                )
            )
        return LogoDetectResult(
            provider=self.name,
            model=self.model,
            candidates=verified,
            screened_out=local.screened_out + max(0, len(local.candidates) - len(verified)),
        )


def get_logo_detector(settings: Settings | None = None) -> LogoDetector:
    cfg = settings or get_settings()
    if cfg.logo_provider == "external":
        return ExternalLogoDetector(cfg)
    return LocalCascadeLogoDetector()


def score_template_match(
    *, candidate_confidence: float, similarity: float, min_confidence: float
) -> float:
    """Aggregate score used for proposed matches (still requires human review)."""
    raw = 0.6 * candidate_confidence + 0.4 * similarity
    # Soft-penalize below template threshold without discarding for review.
    if candidate_confidence < min_confidence:
        raw *= 0.85
    return float(min(0.99, max(0.0, raw)))


def l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]
