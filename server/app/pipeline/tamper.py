from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim


@dataclass
class Finding:
    category: str
    severity: str
    message: str
    bbox: List[int]
    score: float


@dataclass
class TamperResult:
    findings: List[Finding]
    tamper_score: float


def _zone_to_bbox(zone: Dict[str, float], image_shape: Tuple[int, int]) -> List[int]:
    height, width = image_shape[:2]
    x = zone.get("x", 0.0)
    y = zone.get("y", 0.0)
    w = zone.get("w", 1.0)
    h = zone.get("h", 1.0)
    if x <= 1.0 and y <= 1.0 and w <= 1.0 and h <= 1.0:
        return [int(x * width), int(y * height), int(w * width), int(h * height)]
    return [int(x), int(y), int(w), int(h)]


def _ssim_region(image_a: np.ndarray, image_b: np.ndarray, bbox: List[int]) -> float:
    x, y, w, h = bbox
    patch_a = image_a[y : y + h, x : x + w]
    patch_b = image_b[y : y + h, x : x + w]
    if patch_a.size == 0 or patch_b.size == 0:
        return 1.0
    gray_a = cv2.cvtColor(patch_a, cv2.COLOR_BGR2GRAY)
    gray_b = cv2.cvtColor(patch_b, cv2.COLOR_BGR2GRAY)
    return float(ssim(gray_a, gray_b))


def analyze_tamper(
    image: np.ndarray,
    reference_image: np.ndarray,
    metadata: Dict[str, object],
    ocr_boxes: List[List[int]],
) -> TamperResult:
    findings: List[Finding] = []

    resized_ref = cv2.resize(reference_image, (image.shape[1], image.shape[0]))

    grid_rows = 6
    grid_cols = 8
    cell_w = image.shape[1] // grid_cols
    cell_h = image.shape[0] // grid_rows

    for row in range(grid_rows):
        for col in range(grid_cols):
            bbox = [col * cell_w, row * cell_h, cell_w, cell_h]
            score = _ssim_region(image, resized_ref, bbox)
            if score < 0.65:
                findings.append(
                    Finding(
                        category="layout",
                        severity="medium",
                        message="Region differs from reference pattern",
                        bbox=bbox,
                        score=float(1.0 - score),
                    )
                )

    watermark_zones = metadata.get("watermark_zones", []) if isinstance(metadata, dict) else []
    for zone in watermark_zones:
        bbox = _zone_to_bbox(zone, image.shape)
        score = _ssim_region(image, resized_ref, bbox)
        if score < 0.7:
            findings.append(
                Finding(
                    category="watermark",
                    severity="high",
                    message="Watermark zone texture mismatch",
                    bbox=bbox,
                    score=float(1.0 - score),
                )
            )

    if ocr_boxes:
        heights = [bbox[3] for bbox in ocr_boxes]
        median_height = float(np.median(heights)) if heights else 0.0
        if median_height > 0:
            variance = float(np.var(heights))
            if variance / median_height > 5.0:
                findings.append(
                    Finding(
                        category="typography",
                        severity="low",
                        message="Typography variance differs from expected",
                        bbox=ocr_boxes[0],
                        score=min(1.0, variance / (median_height * 10.0)),
                    )
                )

    tamper_score = min(100.0, float(len(findings) * 8))
    return TamperResult(findings=findings, tamper_score=tamper_score)
