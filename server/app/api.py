from __future__ import annotations

import json
import logging
import os
import uuid
from typing import List

import cv2
import numpy as np
import pytesseract
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.config import settings
from app.models import (
    AnalysisMetrics,
    AnalysisResult,
    AnalysisSummary,
    FrameResponse,
    ReferenceList,
    ReferenceRead,
    SessionCreate,
    SessionRead,
    SessionStatus,
)
from app.pipeline.match import match_reference
from app.pipeline.ocr import run_ocr
from app.pipeline.quality import assess_quality
from app.pipeline.rectify import rectify_document
from app.pipeline.score import compute_scores
from app.pipeline.tamper import analyze_tamper
from app.storage import (
    add_reference,
    create_session,
    get_reference,
    get_session,
    list_references,
    update_session_result,
    update_session_status,
)

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

    return ReferenceRead(
        id=ref_id,
        doc_type=doc_type,
        version=version,
        metadata=meta_dict,
        created_at=get_reference(ref_id)["created_at"],
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


@router.post("/v1/sessions", response_model=SessionRead)
async def create_session_endpoint(payload: SessionCreate) -> SessionRead:
    session_id = str(uuid.uuid4())
    create_session(session_id, payload.doc_type)
    return SessionRead(id=session_id, created_at=get_session(session_id)["created_at"], doc_type=payload.doc_type)


@router.get("/v1/sessions/{session_id}/status", response_model=SessionStatus)
async def get_session_status(session_id: str) -> SessionStatus:
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionStatus(
        session_id=session_id,
        stage=session["stage"],
        percent=session["percent"],
        message=session["message"],
    )


@router.get("/v1/sessions/{session_id}/result", response_model=AnalysisResult)
async def get_session_result(session_id: str) -> AnalysisResult:
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session["result"]:
        raise HTTPException(status_code=404, detail="Result not ready")
    result = json.loads(session["result"])
    return AnalysisResult.model_validate(result)


@router.post("/v1/sessions/{session_id}/frame", response_model=FrameResponse)
async def submit_frame(
    session_id: str,
    file: UploadFile = File(...),
    doc_type: str | None = Form(None),
) -> FrameResponse:
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    update_session_status(session_id, "rectifying", 15)
    image = _load_image(file)
    quality = assess_quality(image)

    rectified = rectify_document(image)
    if not rectified.success:
        update_session_status(session_id, "error", 100, "Could not detect document edges")
        raise HTTPException(status_code=422, detail="Unable to detect document boundary; please hold steady")

    update_session_status(session_id, "matching", 35)
    references = []
    for row in list_references():
        ref_image = cv2.imread(row["image_path"])
        if ref_image is not None:
            references.append((row["id"], ref_image))

    match_candidate = match_reference(rectified.image, references) if references else None
    match_score = match_candidate.score if match_candidate else 0.0
    reference_id = match_candidate.reference_id if match_candidate else None

    update_session_status(session_id, "ocr", 55)
    try:
        ocr_result = run_ocr(rectified.image)
    except pytesseract.pytesseract.TesseractNotFoundError as exc:
        update_session_status(session_id, "error", 100, "Tesseract OCR not installed")
        raise HTTPException(status_code=500, detail="Tesseract OCR not installed") from exc
    ocr_quality_score = float(min(100.0, len(ocr_result.words) * 1.5))

    update_session_status(session_id, "tamper", 75)
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

    update_session_status(session_id, "scoring", 90)
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

    update_session_result(session_id, result.model_dump())
    logger.info("session_completed %s", json.dumps({"session_id": session_id}))

    return FrameResponse(session_id=session_id, result=result)
