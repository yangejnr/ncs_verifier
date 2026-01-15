from __future__ import annotations

from dataclasses import dataclass

from app.pipeline.quality import QualityResult


@dataclass
class ScoreResult:
    template_match_score: float
    ocr_quality_score: float
    tamper_risk_score: float
    confidence_band: str


def compute_scores(
    match_score: float,
    ocr_quality_score: float,
    tamper_risk_score: float,
    quality: QualityResult,
) -> ScoreResult:
    if quality.acceptable and match_score > 75:
        confidence_band = "high"
    elif match_score > 55:
        confidence_band = "medium"
    else:
        confidence_band = "low"

    return ScoreResult(
        template_match_score=match_score,
        ocr_quality_score=ocr_quality_score,
        tamper_risk_score=tamper_risk_score,
        confidence_band=confidence_band,
    )
