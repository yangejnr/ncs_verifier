from __future__ import annotations

import json
import logging
from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pytesseract

from app.api import router
from app.config import settings
from app.storage import init_db


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def create_app() -> FastAPI:
    _configure_logging()

    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

    app = FastAPI(title=settings.app_name)
    origins: List[str]
    if settings.allowed_origins == "*":
        origins = ["*"]
    else:
        origins = [origin.strip() for origin in settings.allowed_origins.split(",") if origin.strip()]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"]
    )

    app.include_router(router)

    @app.on_event("startup")
    def _startup() -> None:
        init_db()
        logging.getLogger("ncs_verifier").info("startup %s", json.dumps({"status": "ready"}))

    return app


app = create_app()
