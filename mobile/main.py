from __future__ import annotations

import io
import os
import threading
from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import requests
from PIL import Image as PilImage
from PIL import ImageDraw, ImageFilter

from kivy.app import App
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.lang import Builder
from kivy.properties import BooleanProperty, NumericProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.camera import Camera

KV = """
<RootView>:
    orientation: "vertical"
    padding: 8
    spacing: 8

    Camera:
        id: cam
        resolution: (640, 480)
        play: True

    Label:
        id: status_label
        text: root.status_text
        size_hint_y: None
        height: "32dp"

    ProgressBar:
        max: 100
        value: root.progress_value
        size_hint_y: None
        height: "12dp"

    Image:
        id: result_image
        size_hint_y: 0.35
        allow_stretch: True
        keep_ratio: True

    Label:
        id: result_label
        text: root.result_text
        text_size: self.width, None
        size_hint_y: 0.35
"""


@dataclass
class ScanResult:
    match_score: float
    tamper_risk: float
    confidence: str
    summary: str


class RootView(BoxLayout):
    status_text = StringProperty("Hold steady…")
    result_text = StringProperty("")
    progress_value = NumericProperty(0)
    busy = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._sharpness_values: List[float] = []
        self._stable_ticks = 0
        self._last_frame: Optional[PilImage.Image] = None
        Clock.schedule_interval(self._analyze_frame, 0.125)

    def _analyze_frame(self, _dt: float) -> None:
        if self.busy:
            return
        camera = self.ids.cam
        texture = camera.texture
        if not texture:
            return

        frame = self._texture_to_pil(texture)
        if frame is None:
            return

        self._last_frame = frame
        sharpness = self._sharpness(frame)
        self._sharpness_values.append(sharpness)
        if len(self._sharpness_values) > 15:
            self._sharpness_values.pop(0)

        if len(self._sharpness_values) >= 10:
            variance = float(np.var(self._sharpness_values))
            mean = float(np.mean(self._sharpness_values))
            if variance < 8.0 and mean > 12.0:
                self._stable_ticks += 1
                self.status_text = "Stable detected… analyzing"
            else:
                self._stable_ticks = 0
                self.status_text = "Hold steady…"

        if self._stable_ticks >= 8:
            self._stable_ticks = 0
            self._start_upload()

    def _start_upload(self) -> None:
        if self._last_frame is None:
            return
        self.busy = True
        self.progress_value = 10
        self.status_text = "Uploading frame…"
        self.result_text = ""
        threading.Thread(target=self._upload_frame, daemon=True).start()

    def _upload_frame(self) -> None:
        server_url = os.environ.get("NCS_SERVER_URL", "http://127.0.0.1:8000")
        doc_type = os.environ.get("NCS_DOC_TYPE", "NCS_ORIGIN")

        try:
            session_resp = requests.post(f"{server_url}/v1/sessions", json={"doc_type": doc_type}, timeout=10)
            session_resp.raise_for_status()
            session_id = session_resp.json()["id"]

            buffer = io.BytesIO()
            self._last_frame.save(buffer, format="JPEG", quality=85)
            buffer.seek(0)
            files = {"file": ("frame.jpg", buffer, "image/jpeg")}
            data = {"doc_type": doc_type}

            self._update_progress(40, "Analyzing…")
            resp = requests.post(
                f"{server_url}/v1/sessions/{session_id}/frame",
                files=files,
                data=data,
                timeout=30,
            )
            resp.raise_for_status()
            payload = resp.json()["result"]
            result = ScanResult(
                match_score=payload["summary"]["match_score"],
                tamper_risk=payload["summary"]["tamper_risk_score"],
                confidence=payload["summary"]["confidence_band"],
                summary=payload["summary"]["disclaimer"],
            )
            findings = payload.get("findings", [])
            self._apply_results(result, findings)
        except Exception as exc:
            self._update_progress(0, f"Error: {exc}")
        finally:
            self.busy = False

    def _apply_results(self, result: ScanResult, findings: List[dict]) -> None:
        display_image = self._draw_findings(findings)
        result_lines = [
            f"Template match: {result.match_score:.1f}%",
            f"Tamper risk: {result.tamper_risk:.1f}%",
            f"Confidence: {result.confidence}",
            result.summary,
        ]
        self._update_result("\n".join(result_lines), display_image)

    def _draw_findings(self, findings: List[dict]) -> Optional[Texture]:
        if self._last_frame is None:
            return None
        frame = self._last_frame.copy()
        draw = ImageDraw.Draw(frame)
        for finding in findings[:8]:
            bbox = finding.get("bbox", [])
            if len(bbox) == 4:
                x, y, w, h = bbox
                draw.rectangle([x, y, x + w, y + h], outline="red", width=3)
        return self._pil_to_texture(frame)

    def _update_progress(self, value: int, text: str) -> None:
        def _apply(_dt: float) -> None:
            self.progress_value = value
            self.status_text = text

        Clock.schedule_once(_apply)

    def _update_result(self, text: str, texture: Optional[Texture]) -> None:
        def _apply(_dt: float) -> None:
            self.progress_value = 100
            self.status_text = "Done"
            self.result_text = text
            if texture is not None:
                self.ids.result_image.texture = texture

        Clock.schedule_once(_apply)

    @staticmethod
    def _texture_to_pil(texture: Texture) -> Optional[PilImage.Image]:
        size = texture.size
        if not size or size[0] == 0 or size[1] == 0:
            return None
        pixels = texture.pixels
        image = PilImage.frombytes("RGBA", size, pixels)
        return image.convert("RGB")

    @staticmethod
    def _pil_to_texture(image: PilImage.Image) -> Texture:
        image = image.transpose(PilImage.FLIP_TOP_BOTTOM)
        data = image.tobytes()
        texture = Texture.create(size=image.size, colorfmt="rgb")
        texture.blit_buffer(data, colorfmt="rgb", bufferfmt="ubyte")
        return texture

    @staticmethod
    def _sharpness(image: PilImage.Image) -> float:
        edges = image.filter(ImageFilter.FIND_EDGES).convert("L")
        arr = np.asarray(edges, dtype=np.float32)
        return float(arr.var())


class NcsVerifierApp(App):
    def build(self) -> RootView:
        Builder.load_string(KV)
        return RootView()


if __name__ == "__main__":
    NcsVerifierApp().run()
