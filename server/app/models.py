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


class SessionCreate(BaseModel):
    doc_type: Optional[str] = None


class SessionRead(BaseModel):
    id: str
    created_at: datetime
    doc_type: Optional[str]


class SessionStatus(BaseModel):
    session_id: str
    stage: str
    percent: int
    message: Optional[str] = None


class QualityMetrics(BaseModel):
    blur_score: float
    glare_ratio: float
    acceptable: bool


class MatchResult(BaseModel):
    reference_id: Optional[str]
    match_score: float


class OCRWord(BaseModel):
    text: str
    conf: float
    bbox: List[int]


class OCRResult(BaseModel):
    full_text: str
    words: List[OCRWord]
    extracted_fields: Dict[str, str]


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


class FrameResponse(BaseModel):
    session_id: str
    result: AnalysisResult
