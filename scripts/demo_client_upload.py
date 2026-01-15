from __future__ import annotations

import argparse
import os

import requests


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload a document image to the verifier")
    parser.add_argument("--image", required=True)
    parser.add_argument("--server", default=os.environ.get("NCS_SERVER_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--doc-type", default="NCS_ORIGIN")
    args = parser.parse_args()

    with open(args.image, "rb") as handle:
        session = requests.post(f"{args.server}/v1/sessions", json={"doc_type": args.doc_type}, timeout=10)
        session.raise_for_status()
        session_id = session.json()["id"]

        files = {"file": (os.path.basename(args.image), handle, "image/jpeg")}
        data = {"doc_type": args.doc_type}
        resp = requests.post(f"{args.server}/v1/sessions/{session_id}/frame", files=files, data=data, timeout=30)
        resp.raise_for_status()
        print(resp.json())


if __name__ == "__main__":
    main()
