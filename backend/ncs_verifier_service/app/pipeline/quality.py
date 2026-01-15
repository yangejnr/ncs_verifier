from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class QualityResult:
    blur_score: float
    glare_ratio: float
    acceptable: bool


def assess_quality(image: np.ndarray) -> QualityResult:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    _, bright = cv2.threshold(gray, 245, 255, cv2.THRESH_BINARY)
    glare_ratio = float(np.sum(bright > 0) / bright.size)
    acceptable = blur_score > 120.0 and glare_ratio < 0.18
    return QualityResult(blur_score=blur_score, glare_ratio=glare_ratio, acceptable=acceptable)
