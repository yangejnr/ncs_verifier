# NCS Document Verifier (MVP)

Offline document verification against stored genuine references. The system provides a risk assessment, not proof of official issuance.

## Repo structure

```
ncs_verifier/
  README.md
  Makefile
  .env.example
  server/
    app/
      main.py
      api.py
      config.py
      models.py
      storage.py
      pipeline/
        quality.py
        rectify.py
        ocr.py
        match.py
        tamper.py
        score.py
      tests/
        test_api.py
        test_pipeline_smoke.py
    requirements.txt
  mobile/
    main.py
    requirements.txt
  scripts/
    seed_references.py
    demo_client_upload.py
```

## Prerequisites

- Python 3.10+
- Tesseract OCR
- A webcam for the mobile preview

Ubuntu install:

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr libgl1
```

## Setup (server)

```bash
cd /home/henry/ncs_verifier
cp .env.example .env
make venv
```

Run the server:

```bash
make server-dev
```

Open Swagger UI: `http://127.0.0.1:8000/docs`

## Seed a reference image

```bash
make seed-reference REF=/path/to/reference.jpg DOC_TYPE="NCS_ORIGIN" VERSION="v1" METADATA='{"watermark_zones":[{"x":0.1,"y":0.1,"w":0.2,"h":0.2}]}'
```

## Verify via CLI upload

```bash
. .venv/bin/activate
python scripts/demo_client_upload.py --image /path/to/document.jpg --server http://127.0.0.1:8000 --doc-type NCS_ORIGIN
```

## Run the mobile client (Linux)

```bash
export NCS_SERVER_URL="http://127.0.0.1:8000"
make mobile-run
```

The client opens the camera preview, detects stability automatically, uploads a frame, shows progress, and displays results. The Linux MVP uses Kivy's built-in `Camera` widget; `camera4kivy` is included in requirements for Android packaging.

## API contract (mobile)

### Create session

`POST /v1/sessions`

```json
{"doc_type": "NCS_ORIGIN"}
```

### Upload frame

`POST /v1/sessions/{session_id}/frame`

- multipart/form-data
- fields:
  - `file`: image file
  - `doc_type`: optional

### Check status

`GET /v1/sessions/{session_id}/status`

```json
{"session_id":"...","stage":"done","percent":100,"message":null}
```

### Result payload (excerpt)

```json
{
  "summary": {
    "doc_type_guess": "NCS_ORIGIN",
    "reference_id": "...",
    "match_score": 82.1,
    "tamper_risk_score": 16.0,
    "confidence_band": "high",
    "disclaimer": "Offline verification against reference templates provides a risk assessment, not proof of official issuance."
  },
  "metrics": {
    "template_match_score": 82.1,
    "ocr_quality_score": 45.0,
    "tamper_risk_score": 16.0,
    "quality_metrics": {"blur_score": 210.4,"glare_ratio": 0.04,"acceptable": true}
  },
  "extracted_fields": {
    "document_number": "AB123456",
    "dates": "2024-01-10"
  },
  "ocr_text": "...",
  "findings": [
    {"category":"layout","severity":"medium","message":"Region differs from reference pattern","bbox":[10,20,100,50],"score":0.3}
  ]
}
```

## MVP pipeline notes

- Quality gating uses blur variance and glare ratio.
- Rectification uses contour detection; returns an error if boundaries are not found.
- Template matching uses SSIM on resized images.
- Tamper signals are deterministic: grid SSIM, optional watermark zones, and OCR typography variance.
- Storage uses SQLite and filesystem under `server/data/`.
- Upgrade paths: Postgres for database, S3/MinIO for image storage, Celery/Redis for background processing.

## Android packaging (guidance)

Install buildozer and create a spec file:

```bash
pip install buildozer
buildozer init
```

In `buildozer.spec`, include `kivy`, `camera4kivy`, `requests`, `pillow`, `numpy` in requirements, then:

```bash
buildozer -v android debug
```
