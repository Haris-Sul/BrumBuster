from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.services.scraper import ScraperError, scrape_listing
from app.services.serpapi_client import SerpApiClient, SerpApiError
from app.services.vision_guard import VisionGuardClient, VisionGuardError

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.post("/analyze")
def analyze():
    payload = request.get_json(silent=True) or {}
    url = (payload.get("url") or "").strip()
    if not url:
        return jsonify({"error": "url is required"}), 400

    try:
        scraped = scrape_listing(url)
    except ScraperError as exc:
        return jsonify({"error": str(exc)}), 502
    except Exception:
        return jsonify({"error": "unexpected error"}), 500

    serpapi_client = SerpApiClient.from_env()
    scam_signals = serpapi_client.empty_signals()
    serpapi_error: str | None = None

    if serpapi_client.is_configured() and scraped.image_url:
        try:
            serpapi_payload = serpapi_client.search_by_image(scraped.image_url)
            scam_signals = serpapi_client.extract_scam_signals(
                serpapi_payload,
                seller_location=scraped.seller_location,
            )
        except SerpApiError as exc:
            serpapi_error = str(exc)
        except Exception:
            serpapi_error = "serpapi error"

    vision_client = VisionGuardClient.from_env()
    identity_guard = None
    identity_guard_error: str | None = None

    if not vision_client.is_configured():
        identity_guard_error = "identity guard not configured"
    elif not scraped.image_url:
        identity_guard_error = "identity guard skipped: image url missing"
    elif not scraped.title:
        identity_guard_error = "identity guard skipped: listing title missing"
    else:
        try:
            identity_guard = vision_client.analyze(
                image_url=scraped.image_url,
                listing_title=scraped.title,
            ).to_dict()
        except VisionGuardError as exc:
            identity_guard_error = str(exc)
        except Exception as exc:
            identity_guard_error = (
                f"identity guard error: {type(exc).__name__}"
            )

    return jsonify(
        {
            "data": scraped.to_dict(),
            "serpapi": {
                **serpapi_client.status_snapshot(),
                "error": serpapi_error,
                "skipped": not serpapi_client.is_configured()
                or not scraped.image_url,
            },
            "scam_signals": scam_signals,
            "identity_guard": identity_guard,
            "identity_guard_error": identity_guard_error,
        }
    )
