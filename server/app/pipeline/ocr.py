from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List

import pytesseract
from pytesseract import Output
import numpy as np


@dataclass
class OCRWord:
    text: str
    conf: float
    bbox: List[int]


@dataclass
class OCRResult:
    full_text: str
    words: List[OCRWord]
    extracted_fields: Dict[str, str]


def _extract_fields(text: str) -> Dict[str, str]:
    fields: Dict[str, str] = {}
    doc_matches = re.findall(r"[A-Z0-9]{6,}", text)
    if doc_matches:
        fields["document_number"] = doc_matches[0]

    date_matches = re.findall(r"\b\d{2}/\d{2}/\d{4}\b|\b\d{4}-\d{2}-\d{2}\b", text)
    if date_matches:
        fields["dates"] = ", ".join(date_matches[:3])

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for idx, line in enumerate(lines):
        if "exporter" in line.lower() and idx + 1 < len(lines):
            fields["exporter"] = lines[idx + 1]
        if "importer" in line.lower() and idx + 1 < len(lines):
            fields["importer"] = lines[idx + 1]

    return fields


def run_ocr(image: np.ndarray) -> OCRResult:
    data = pytesseract.image_to_data(image, output_type=Output.DICT)
    words: List[OCRWord] = []
    for i in range(len(data["text"])):
        text = data["text"][i].strip()
        conf = float(data["conf"][i]) if data["conf"][i] != "-1" else 0.0
        if text:
            bbox = [
                int(data["left"][i]),
                int(data["top"][i]),
                int(data["width"][i]),
                int(data["height"][i]),
            ]
            words.append(OCRWord(text=text, conf=conf, bbox=bbox))
    full_text = "\n".join([word.text for word in words])
    extracted_fields = _extract_fields(full_text)
    return OCRResult(full_text=full_text, words=words, extracted_fields=extracted_fields)
