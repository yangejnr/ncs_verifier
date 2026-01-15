from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ReferenceCreate(BaseModel):
    doc_type: str
    version: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReferenceRead(BaseModel):
    id: str
    doc_type: str
    version: str
    metadata: Dict[str, Any]
    created_at: datetime


class ReferenceList(BaseModel):
    items: List[ReferenceRead]


class QualityMetrics(BaseModel):
    blur_score: float
    glare_ratio: float
    acceptable: bool


class Finding(BaseModel):
    category: str
    severity: str
    message: str
    bbox: List[int]
    score: float


class AnalysisSummary(BaseModel):
    doc_type_guess: Optional[str]
    reference_id: Optional[str]
    match_score: float
    tamper_risk_score: float
    confidence_band: str
    disclaimer: str


class AnalysisMetrics(BaseModel):
    template_match_score: float
    ocr_quality_score: float
    tamper_risk_score: float
    quality_metrics: QualityMetrics


class AnalysisResult(BaseModel):
    summary: AnalysisSummary
    metrics: AnalysisMetrics
    extracted_fields: Dict[str, str]
    ocr_text: str
    findings: List[Finding]


class VerifyResponse(BaseModel):
    result: AnalysisResult
    audit_id: str
