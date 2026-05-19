from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable
from urllib.parse import urlparse

import requests


class SerpApiError(RuntimeError):
    pass


@dataclass(slots=True)
class SerpApiClient:
    api_key: str | None
    base_url: str = "https://serpapi.com/search.json"
    timeout_seconds: float = 15.0

    @classmethod
    def from_env(cls) -> "SerpApiClient":
        timeout_value = os.getenv("SERPAPI_TIMEOUT_SECONDS")
        timeout_seconds = float(timeout_value) if timeout_value else 15.0
        return cls(
            api_key=os.getenv("SERPAPI_API_KEY"),
            timeout_seconds=timeout_seconds,
        )

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def status_snapshot(self) -> dict[str, bool | str | float]:
        return {
            "configured": self.is_configured(),
            "provider": "serpapi",
            "timeout_seconds": self.timeout_seconds,
        }

    def search_by_image(self, image_url: str) -> dict:
        if not self.api_key:
            raise SerpApiError("serpapi not configured")
        if not image_url:
            raise SerpApiError("image url is required")

        params = {
            "engine": "google_lens",
            "api_key": self.api_key,
            "url": image_url,
            "type": "exact_matches",
        }

        try:
            response = requests.get(
                self.base_url,
                params=params,
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise SerpApiError(
                f"serpapi request failed: {type(exc).__name__}"
            ) from exc

        if response.status_code >= 400:
            raise SerpApiError(f"serpapi status {response.status_code}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise SerpApiError("serpapi invalid json") from exc

        error = payload.get("error")
        if isinstance(error, str) and error:
            raise SerpApiError(error)

        metadata = payload.get("search_metadata") or {}
        status = metadata.get("status")
        if isinstance(status, str) and status.lower() == "error":
            message = metadata.get("error") or "serpapi error"
            raise SerpApiError(str(message))

        return payload

    def empty_signals(self) -> dict[str, list[dict[str, str | None]]]:
        return {
            "duplicates": [],
            "geographic_conflicts": [],
            "temporal_conflicts": [],
        }

    def extract_scam_signals(
        self, payload: dict, seller_location: str | None
    ) -> dict[str, list[dict[str, str | None]]]:
        exact_matches = payload.get("exact_matches")
        if not isinstance(exact_matches, list):
            return self.empty_signals()

        duplicates: list[dict[str, str | None]] = []
        geographic_conflicts: list[dict[str, str | None]] = []
        temporal_conflicts: list[dict[str, str | None]] = []

        seen_duplicates: set[str] = set()
        seen_geographic: set[str] = set()
        seen_temporal: set[str] = set()

        is_uk_seller = _is_uk_location(seller_location)
        current_year = datetime.utcnow().year

        for match in exact_matches:
            if not isinstance(match, dict):
                continue

            title = _safe_text(match.get("title"))
            link = _safe_text(match.get("link"))
            displayed_link = _safe_text(match.get("displayed_link"))
            host = _extract_host(link) or _extract_host(displayed_link)
            url_key = link or displayed_link or ""

            if link and _is_ebay_duplicate(host) and link not in seen_duplicates:
                duplicates.append({"title": title, "url": link})
                seen_duplicates.add(link)

            if is_uk_seller:
                tld = _extract_tld(host)
                if tld and _is_foreign_tld(tld) and url_key not in seen_geographic:
                    geographic_conflicts.append(
                        {
                            "title": title,
                            "url": link or displayed_link,
                            "host": host,
                            "tld": tld,
                        }
                    )
                    seen_geographic.add(url_key)

            texts = list(_iter_match_text(match))
            matched_text, matched_year = _detect_temporal_conflict(
                texts, current_year
            )
            if matched_text and url_key not in seen_temporal:
                temporal_conflicts.append(
                    {
                        "title": title,
                        "url": link or displayed_link,
                        "matched_text": matched_text,
                        "year": str(matched_year) if matched_year else None,
                    }
                )
                seen_temporal.add(url_key)

        return {
            "duplicates": duplicates,
            "geographic_conflicts": geographic_conflicts,
            "temporal_conflicts": temporal_conflicts,
        }


def _safe_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _iter_match_text(match: dict) -> Iterable[str]:
    for key in ("title", "snippet", "source", "displayed_link"):
        value = _safe_text(match.get(key))
        if value:
            yield value


def _extract_host(url: str | None) -> str | None:
    if not url:
        return None
    normalized = url if "://" in url else f"https://{url}"
    host = urlparse(normalized).netloc
    return host.lower() if host else None


def _extract_tld(host: str | None) -> str | None:
    if not host:
        return None
    parts = host.split(".")
    if len(parts) < 2:
        return None
    tld = parts[-1]
    if tld == "uk" and len(parts) >= 3 and parts[-2] in {"co", "org", "gov", "ac"}:
        return "uk"
    return tld


def _is_ebay_duplicate(host: str | None) -> bool:
    if not host:
        return False
    return host.endswith("ebay.co.uk") or host.endswith("ebay.com")


def _is_uk_location(location: str | None) -> bool:
    if not location:
        return False
    normalized = location.lower()
    tokens = {
        "uk",
        "united kingdom",
        "great britain",
        "gb",
        "england",
        "scotland",
        "wales",
        "northern ireland",
        "london",
        "birmingham",
        "manchester",
        "leeds",
        "bristol",
        "liverpool",
        "sheffield",
        "glasgow",
        "edinburgh",
        "cardiff",
        "belfast",
    }
    return any(token in normalized for token in tokens)


def _is_foreign_tld(tld: str) -> bool:
    foreign_tlds = {
        "pl",
        "de",
        "fr",
        "es",
        "it",
        "nl",
        "cz",
        "sk",
        "ro",
        "se",
        "no",
        "fi",
        "dk",
        "ie",
        "pt",
        "hu",
        "gr",
        "at",
        "be",
        "ch",
    }
    return tld in foreign_tlds


def _detect_temporal_conflict(
    texts: Iterable[str], current_year: int
) -> tuple[str | None, int | None]:
    year_pattern = re.compile(r"\b(19\d{2}|20\d{2})\b")
    years_ago_pattern = re.compile(r"\b(\d{1,2})\s+years?\s+ago\b", re.I)
    old_terms_pattern = re.compile(
        r"\b(archived|archive|old photo|stock photo|vintage|historical)\b",
        re.I,
    )

    for text in texts:
        years_ago = years_ago_pattern.search(text)
        if years_ago:
            years = int(years_ago.group(1))
            if years >= 3:
                return text, current_year - years

        for match in year_pattern.finditer(text):
            year = int(match.group(1))
            if year <= current_year - 3:
                return text, year

        if old_terms_pattern.search(text):
            return text, None

    return None, None
