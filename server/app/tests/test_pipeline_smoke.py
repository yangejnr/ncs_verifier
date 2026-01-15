import os

import cv2
import numpy as np

from app.pipeline.match import compute_match_score
from app.pipeline.quality import assess_quality
from app.pipeline.rectify import rectify_document


TEST_IMAGE_PATH = os.environ.get("NCS_TEST_IMAGE", "server/data/sample.jpg")


def test_pipeline_smoke() -> None:
    if not os.path.exists(TEST_IMAGE_PATH):
        return

    image = cv2.imread(TEST_IMAGE_PATH)
    if image is None:
        return

    quality = assess_quality(image)
    rectified = rectify_document(image)
    score = compute_match_score(rectified.image, rectified.image)

    assert quality.blur_score >= 0
    assert score >= 90.0
