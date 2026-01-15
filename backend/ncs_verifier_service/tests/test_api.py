import io

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
import pytesseract

from app.main import create_app


def _tesseract_available() -> bool:
    try:
        _ = pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _tesseract_available(), reason="tesseract not installed")
def test_verify_endpoint() -> None:
    app = create_app()
    client = TestClient(app)

    image = np.full((480, 640, 3), 255, dtype=np.uint8)
    cv2.putText(image, "NCS TEST", (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
    _, buffer = cv2.imencode(".jpg", image)
    files = {"file": ("frame.jpg", io.BytesIO(buffer.tobytes()), "image/jpeg")}

    response = client.post("/v1/verify", files=files)
    assert response.status_code in (200, 422)
    if response.status_code == 200:
        payload = response.json()
        assert "result" in payload
        assert "summary" in payload["result"]
