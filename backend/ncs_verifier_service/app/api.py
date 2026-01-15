from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime

import cv2
import numpy as np
import pytesseract
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.config import settings
from app.models import (
    AnalysisMetrics,
    AnalysisResult,
    AnalysisSummary,
    ReferenceList,
    ReferenceRead,
    VerifyResponse,
)
from app.pipeline.match import match_reference
from app.pipeline.ocr import run_ocr
from app.pipeline.quality import assess_quality
from app.pipeline.rectify import rectify_document
from app.pipeline.score import compute_scores
from app.pipeline.tamper import analyze_tamper
from app.storage.db import add_audit_log, add_reference, get_reference, list_references

logger = logging.getLogger("ncs_verifier")
router = APIRouter()


def _load_image(file: UploadFile) -> np.ndarray:
    data = file.file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty image upload")
    image_array = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=400, detail="Unsupported image format")
    return image


def _reference_dir(ref_id: str) -> str:
    return os.path.join(settings.data_dir, "references", ref_id)


@router.post("/v1/references", response_model=ReferenceRead)
async def create_reference(
    doc_type: str = Form(...),
    version: str = Form(...),
    metadata: str = Form("{}"),
    file: UploadFile = File(...),
) -> ReferenceRead:
    ref_id = str(uuid.uuid4())
    try:
        meta_dict = json.loads(metadata)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="metadata must be valid JSON") from exc

    ref_dir = _reference_dir(ref_id)
    os.makedirs(ref_dir, exist_ok=True)
    image_path = os.path.join(ref_dir, "original.jpg")

    image = _load_image(file)
    cv2.imwrite(image_path, image)

    add_reference(ref_id, doc_type, version, meta_dict, image_path)
    logger.info("reference_created %s", json.dumps({"reference_id": ref_id}))

    row = get_reference(ref_id)
    created_at = row["created_at"] if row else datetime.utcnow().isoformat()
    return ReferenceRead(
        id=ref_id,
        doc_type=doc_type,
        version=version,
        metadata=meta_dict,
        created_at=created_at,
    )


@router.get("/v1/references", response_model=ReferenceList)
async def list_reference() -> ReferenceList:
    items = []
    for row in list_references():
        items.append(
            ReferenceRead(
                id=row["id"],
                doc_type=row["doc_type"],
                version=row["version"],
                metadata=json.loads(row["metadata"]),
                created_at=row["created_at"],
            )
        )
    return ReferenceList(items=items)


@router.get("/v1/references/{ref_id}", response_model=ReferenceRead)
async def get_reference_by_id(ref_id: str) -> ReferenceRead:
    row = get_reference(ref_id)
    if not row:
        raise HTTPException(status_code=404, detail="Reference not found")
    return ReferenceRead(
        id=row["id"],
        doc_type=row["doc_type"],
        version=row["version"],
        metadata=json.loads(row["metadata"]),
        created_at=row["created_at"],
    )


@router.post("/v1/verify", response_model=VerifyResponse)
async def verify_document(
    file: UploadFile = File(...),
    doc_type: str | None = Form(None),
) -> VerifyResponse:
    image = _load_image(file)
    quality = assess_quality(image)

    rectified = rectify_document(image)
    if not rectified.success:
        raise HTTPException(status_code=422, detail="Unable to detect document boundary; please hold steady")

    references = []
    for row in list_references():
        ref_image = cv2.imread(row["image_path"])
        if ref_image is not None:
            references.append((row["id"], ref_image))

    match_candidate = match_reference(rectified.image, references) if references else None
    match_score = match_candidate.score if match_candidate else 0.0
    reference_id = match_candidate.reference_id if match_candidate else None

    try:
        ocr_result = run_ocr(rectified.image)
    except pytesseract.pytesseract.TesseractNotFoundError as exc:
        raise HTTPException(status_code=500, detail="Tesseract OCR not installed") from exc

    ocr_quality_score = float(min(100.0, len(ocr_result.words) * 1.5))

    reference_image = None
    reference_metadata: dict = {}
    if reference_id:
        row = get_reference(reference_id)
        if row:
            reference_image = cv2.imread(row["image_path"])
            reference_metadata = json.loads(row["metadata"])

    if reference_image is None:
        reference_image = rectified.image
    tamper = analyze_tamper(
        rectified.image,
        reference_image,
        reference_metadata,
        [word.bbox for word in ocr_result.words],
    )

    scores = compute_scores(match_score, ocr_quality_score, tamper.tamper_score, quality)

    summary = AnalysisSummary(
        doc_type_guess=doc_type,
        reference_id=reference_id,
        match_score=scores.template_match_score,
        tamper_risk_score=scores.tamper_risk_score,
        confidence_band=scores.confidence_band,
        disclaimer=(
            "Offline verification against reference templates provides a risk assessment, "
            "not proof of official issuance."
        ),
    )

    metrics = AnalysisMetrics(
        template_match_score=scores.template_match_score,
        ocr_quality_score=scores.ocr_quality_score,
        tamper_risk_score=scores.tamper_risk_score,
        quality_metrics={
            "blur_score": quality.blur_score,
            "glare_ratio": quality.glare_ratio,
            "acceptable": quality.acceptable,
        },
    )

    result = AnalysisResult(
        summary=summary,
        metrics=metrics,
        extracted_fields=ocr_result.extracted_fields,
        ocr_text=ocr_result.full_text,
        findings=[finding.__dict__ for finding in tamper.findings],
    )

    audit_id = str(uuid.uuid4())
    add_audit_log(audit_id, doc_type, reference_id, result.model_dump())
    logger.info("verification_completed %s", json.dumps({"audit_id": audit_id, "reference_id": reference_id}))

    return VerifyResponse(result=result, audit_id=audit_id)
