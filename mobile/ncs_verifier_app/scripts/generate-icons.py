#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from PIL import Image

BASE_DIR = Path(__file__).resolve().parents[1]
LOGO_PATH = BASE_DIR / "assets" / "branding" / "ncs_logo.png"
OUTPUT_DIR = BASE_DIR / "android" / "app" / "src" / "main" / "res"

ICON_SIZE = 1024
LOGO_SCALE = 0.6

MIPMAP_SIZES = {
    "mipmap-mdpi": 48,
    "mipmap-hdpi": 72,
    "mipmap-xhdpi": 96,
    "mipmap-xxhdpi": 144,
    "mipmap-xxxhdpi": 192,
}

FOREGROUND_SIZES = {
    "mipmap-mdpi": 108,
    "mipmap-hdpi": 162,
    "mipmap-xhdpi": 216,
    "mipmap-xxhdpi": 324,
    "mipmap-xxxhdpi": 432,
}


def _create_canvas(background: tuple[int, int, int, int]) -> Image.Image:
    return Image.new("RGBA", (ICON_SIZE, ICON_SIZE), background)


def _center_logo(canvas: Image.Image, logo: Image.Image) -> Image.Image:
    logo = logo.copy()
    max_size = int(ICON_SIZE * LOGO_SCALE)
    logo.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    x = (ICON_SIZE - logo.width) // 2
    y = (ICON_SIZE - logo.height) // 2
    canvas.paste(logo, (x, y), logo if logo.mode == "RGBA" else None)
    return canvas


def _save_resized(image: Image.Image, out_path: Path, size: int) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    resized = image.resize((size, size), Image.Resampling.LANCZOS)
    resized.save(out_path, format="PNG")


def main() -> None:
    if not LOGO_PATH.exists():
        raise SystemExit(f"Logo not found: {LOGO_PATH}")

    logo = Image.open(LOGO_PATH).convert("RGBA")

    foreground = _center_logo(_create_canvas((0, 0, 0, 0)), logo)
    icon = _center_logo(_create_canvas((255, 255, 255, 255)), logo)

    for folder, size in MIPMAP_SIZES.items():
        _save_resized(icon, OUTPUT_DIR / folder / "ic_launcher.png", size)
        _save_resized(icon, OUTPUT_DIR / folder / "ic_launcher_round.png", size)

    for folder, size in FOREGROUND_SIZES.items():
        _save_resized(foreground, OUTPUT_DIR / folder / "ic_launcher_foreground.png", size)

    print("Updated Android launcher icons.")


if __name__ == "__main__":
    main()
