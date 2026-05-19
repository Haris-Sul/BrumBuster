from __future__ import annotations

import io
import json
import os
from dataclasses import dataclass

import requests
from google import genai
from google.genai import types
from PIL import Image


class VisionGuardError(RuntimeError):
    pass


ALLOWED_CLASSIFICATIONS = {
    "exact_match",
    "generic_stock_photo",
    "misidentified_part",
    "mismatched_condition",
}


@dataclass(slots=True)
class IdentityGuardResult:
    match_confidence: float
    classification: str
    forensic_notes: str

    def to_dict(self) -> dict[str, str | float]:
        return {
            "match_confidence": self.match_confidence,
            "classification": self.classification,
            "forensic_notes": self.forensic_notes,
        }


@dataclass(slots=True)
class VisionGuardClient:
    api_key: str | None
    model: str = "gemini-3-flash-preview"
    timeout_seconds: float = 20.0

    @classmethod
    def from_env(cls) -> "VisionGuardClient":
        timeout_value = os.getenv("GEMINI_TIMEOUT_SECONDS")
        timeout_seconds = float(timeout_value) if timeout_value else 20.0
        return cls(
            api_key=os.getenv("GEMINI_API_KEY"),
            timeout_seconds=timeout_seconds,
        )

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def analyze(self, image_url: str, listing_title: str) -> IdentityGuardResult:
        if not self.api_key:
            raise VisionGuardError("gemini not configured")
        if not listing_title:
            raise VisionGuardError("listing title is required")
        if not image_url:
            raise VisionGuardError("image url is required")
        try:
            image_bytes, mime_type = _download_image(
                image_url,
                timeout_seconds=self.timeout_seconds,
            )
            client = genai.Client(api_key=self.api_key)

            system_instruction = (
                "you are an automotive forensic expert running match verification. judge whether "
                "the part shown in the image matches the listing title. evaluate mechanical "
                "identity, structural layout, and whether the image looks like a generic "
                "stock illustration versus a unique item photo. use these confidence bands: "
                "0.90 to 1.00 for clear unique item photos that match part, condition, and parameters; "
                "0.75 to 0.85 for clean catalog or stock graphics where the part looks correct; "
                "0.50 to 0.70 for correct component type but visible wear or engineering mismatches; "
                "below 0.40 for critical mismatch or wrong object type. respond only with json."
            )

            prompt = (
                "listing title: "
                f"{listing_title}\n"
                "classification meanings:\n"
                "exact_match: the photo shows the exact part described in the title\n"
                "generic_stock_photo: the photo looks like a clean catalog image or render\n"
                "misidentified_part: the photo shows a different part than the title\n"
                "mismatched_condition: the title claims new but the photo shows wear\n"
                "return a json object with keys match_confidence, classification, "
                "forensic_notes. classification must be one of exact_match, "
                "generic_stock_photo, misidentified_part, mismatched_condition. "
                "match_confidence is a float between 0 and 1."
            )

            schema = _build_response_schema()
            image_part = _build_image_part(image_bytes, mime_type)
            contents = [types.Part.from_text(text=prompt), image_part]

            response = _generate_with_fallback(
                client=client,
                model=self.model,
                contents=contents,
                system_instruction=system_instruction,
                schema=schema,
            )

            response_text = _extract_response_text(response)
            return _parse_identity_result(response_text)
        except VisionGuardError:
            raise
        except Exception as exc:
            raise VisionGuardError(
                f"gemini request failed: {type(exc).__name__} {repr(exc)}"
            ) from exc


def _download_image(url: str, timeout_seconds: float) -> tuple[bytes, str]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Referer": "https://www.ebay.co.uk/",
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=timeout_seconds,
        )
    except requests.RequestException as exc:
        raise VisionGuardError(
            f"image download failed: {type(exc).__name__}"
        ) from exc

    if response.status_code >= 400:
        raise VisionGuardError(f"image download status {response.status_code}")

    raw_bytes = response.content
    try:
        image = Image.open(io.BytesIO(raw_bytes))
    except OSError as exc:
        raise VisionGuardError("image decode failed") from exc

    output = io.BytesIO()
    image = image.convert("RGB")
    image.save(output, format="JPEG", quality=92)
    return output.getvalue(), "image/jpeg"


def _parse_identity_result(text: str) -> IdentityGuardResult:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise VisionGuardError("gemini invalid json") from exc

    if not isinstance(payload, dict):
        raise VisionGuardError("gemini invalid payload")

    match_confidence = _coerce_confidence(payload.get("match_confidence"))
    classification = payload.get("classification")
    forensic_notes = payload.get("forensic_notes")

    if classification not in ALLOWED_CLASSIFICATIONS:
        raise VisionGuardError("gemini invalid classification")
    if not isinstance(forensic_notes, str) or not forensic_notes.strip():
        raise VisionGuardError("gemini invalid notes")

    return IdentityGuardResult(
        match_confidence=match_confidence,
        classification=classification,
        forensic_notes=forensic_notes.strip(),
    )


def _coerce_confidence(value: object) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        raise VisionGuardError("gemini invalid confidence")

    if confidence < 0:
        return 0.0
    if confidence > 1:
        return 1.0
    return confidence


def _build_image_part(image_bytes: bytes, mime_type: str) -> types.Part:
    if hasattr(types.Part, "from_bytes"):
        try:
            return types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        except TypeError:
            pass

    try:
        return types.Part(
            inline_data=types.Blob(mime_type=mime_type, data=image_bytes)
        )
    except TypeError:
        return {
            "inline_data": {
                "mime_type": mime_type,
                "data": image_bytes,
            }
        }


def _build_response_schema() -> types.Schema | None:
    try:
        return types.Schema(
            type="object",
            properties={
                "match_confidence": types.Schema(type="number"),
                "classification": types.Schema(
                    type="string",
                    enum=sorted(ALLOWED_CLASSIFICATIONS),
                ),
                "forensic_notes": types.Schema(type="string"),
            },
            required=["match_confidence", "classification", "forensic_notes"],
        )
    except TypeError:
        return None


def _generate_with_fallback(
    *,
    client: genai.Client,
    model: str,
    contents: list,
    system_instruction: str,
    schema: types.Schema | None,
) -> object:
    try:
        return client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0.2,
            ),
        )
    except TypeError:
        return client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )


def _extract_response_text(response: object) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text

    candidates = getattr(response, "candidates", None)
    if isinstance(candidates, list):
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None)
            if not isinstance(parts, list):
                continue
            for part in parts:
                part_text = getattr(part, "text", None)
                if isinstance(part_text, str) and part_text.strip():
                    return part_text

    raise VisionGuardError("gemini empty response")
