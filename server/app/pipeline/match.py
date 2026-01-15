from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim


@dataclass
class MatchCandidate:
    reference_id: str
    score: float


def _resize_for_match(image: np.ndarray, width: int = 800) -> np.ndarray:
    scale = width / float(image.shape[1])
    return cv2.resize(image, (width, int(image.shape[0] * scale)))


def compute_match_score(image: np.ndarray, reference_image: np.ndarray) -> float:
    image_resized = _resize_for_match(image)
    reference_resized = _resize_for_match(reference_image)
    min_height = min(image_resized.shape[0], reference_resized.shape[0])
    image_resized = image_resized[:min_height, :]
    reference_resized = reference_resized[:min_height, :]
    gray_a = cv2.cvtColor(image_resized, cv2.COLOR_BGR2GRAY)
    gray_b = cv2.cvtColor(reference_resized, cv2.COLOR_BGR2GRAY)
    score = ssim(gray_a, gray_b)
    return float(score * 100.0)


def match_reference(
    image: np.ndarray,
    references: Iterable[Tuple[str, np.ndarray]],
) -> Optional[MatchCandidate]:
    best: Optional[MatchCandidate] = None
    for ref_id, ref_image in references:
        score = compute_match_score(image, ref_image)
        if best is None or score > best.score:
            best = MatchCandidate(reference_id=ref_id, score=score)
    return best
