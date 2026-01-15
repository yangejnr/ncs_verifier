from __future__ import annotations

import argparse
import json
import os
import sys
import uuid

import cv2

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SERVER_DIR = os.path.join(BASE_DIR, "server")
sys.path.append(SERVER_DIR)

from app.config import settings  # noqa: E402
from app.storage import add_reference, init_db  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a reference document")
    parser.add_argument("--ref", required=True, help="Path to reference image")
    parser.add_argument("--doc-type", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--metadata", default="{}", help="JSON metadata")
    args = parser.parse_args()

    if not os.path.exists(args.ref):
        raise SystemExit(f"Reference file not found: {args.ref}")

    init_db()
    ref_id = str(uuid.uuid4())
    ref_dir = os.path.join(settings.data_dir, "references", ref_id)
    os.makedirs(ref_dir, exist_ok=True)

    image = cv2.imread(args.ref)
    if image is None:
        raise SystemExit("Unable to read reference image")

    image_path = os.path.join(ref_dir, "original.jpg")
    cv2.imwrite(image_path, image)

    metadata = json.loads(args.metadata)
    add_reference(ref_id, args.doc_type, args.version, metadata, image_path)
    print(f"Seeded reference {ref_id} -> {image_path}")


if __name__ == "__main__":
    main()
