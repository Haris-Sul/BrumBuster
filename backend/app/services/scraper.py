from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Iterable

import requests
from bs4 import BeautifulSoup

from app.config import get_settings

logger = logging.getLogger(__name__)


class ScraperError(RuntimeError):
    pass


@dataclass(slots=True)
class ScrapeResult:
    source_url: str
    title: str | None
    image_url: str | None
    image_urls: list[str]
    image_index: int | None
    seller_location: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "source_url": self.source_url,
            "title": self.title,
            "image_url": self.image_url,
            "image_urls": self.image_urls,
            "image_index": self.image_index,
            "seller_location": self.seller_location,
        }


DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Referer": "https://www.ebay.co.uk/",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Sec-CH-UA": '"Chromium";v="124", "Not:A-Brand";v="99", "Google Chrome";v="124"',
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": '"Windows"',
    "DNT": "1",
}


def scrape_listing(url: str, image_index: int = 1) -> ScrapeResult:
    if not url.startswith("http"):
        raise ScraperError("invalid url")

    settings = get_settings()

    try:
        with requests.Session() as session:
            session.headers.update(DEFAULT_HEADERS)
            response = _fetch_listing(
                session,
                url,
                timeout=settings.request_timeout_seconds,
            )
    except requests.RequestException as exc:
        message = f"scraper request failed: {type(exc).__name__} {repr(exc)}"
        logger.error(message)
        print(message, flush=True)
        raise ScraperError("request failed") from exc

    if response.status_code >= 400:
        message = (
            "scraper request failed: "
            f"status={response.status_code} reason={response.reason} "
            f"url={response.url} content-type={response.headers.get('Content-Type')} "
            f"server={response.headers.get('Server')}"
        )
        logger.error(message)
        print(message, flush=True)
        raise ScraperError(f"request failed with status {response.status_code}")

    content_type = response.headers.get("Content-Type", "")
    if "text/html" not in content_type:
        message = (
            "scraper unexpected content type: "
            f"{content_type} url={response.url}"
        )
        logger.error(message)
        print(message, flush=True)
        raise ScraperError("unexpected content type")

    soup = BeautifulSoup(response.text, "html.parser")

    image_urls = _extract_gallery_images(soup)
    if not image_urls:
        primary_image = _extract_primary_image(soup)
        image_urls = [primary_image] if primary_image else []

    image_url, selected_index = _select_image_url(image_urls, image_index)
    title = _extract_title(soup)
    seller_location = _extract_seller_location(soup)

    return ScrapeResult(
        source_url=url,
        title=title,
        image_url=image_url,
        image_urls=image_urls,
        image_index=selected_index,
        seller_location=seller_location,
    )


def _extract_gallery_images(soup: BeautifulSoup) -> list[str]:
    candidates: list[str] = []

    candidates.extend(_extract_ld_images(soup))

    meta_image = _first_meta_content(
        soup,
        [
            ("property", "og:image"),
            ("property", "og:image:secure_url"),
            ("name", "twitter:image"),
            ("name", "twitter:image:src"),
        ],
    )
    if meta_image:
        candidates.append(meta_image)

    selectors = [
        "img[data-zoom-src]",
        "img[data-testid='ux-image-carousel-item']",
        "img[data-testid='ux-image-carousel-image']",
        "div[data-testid='ux-image-carousel'] img",
        "div[data-testid='x-main-image'] img",
        "div#vi_main_img_fs img",
        "img[src*='i.ebayimg.com']",
    ]

    for img in soup.select(", ".join(selectors)):
        url = _clean_text(
            img.get("data-zoom-src")
            or img.get("data-src")
            or img.get("src")
        )
        if url:
            candidates.append(url)

    return _dedupe_images(candidates)


def _select_image_url(
    image_urls: list[str], image_index: int
) -> tuple[str | None, int | None]:
    if not image_urls:
        return None, None

    normalized_index = _normalize_image_index(image_index)
    if normalized_index > len(image_urls):
        normalized_index = len(image_urls)

    return image_urls[normalized_index - 1], normalized_index


def _normalize_image_index(value: int) -> int:
    if isinstance(value, bool):
        return 1
    if not isinstance(value, int):
        return 1
    return value if value >= 1 else 1


def _extract_ld_images(soup: BeautifulSoup) -> list[str]:
    images: list[str] = []
    for data in _iter_ld_json_objects(soup):
        images.extend(_coerce_image_entries(data.get("image")))
    return images


def _coerce_image_entries(value: object) -> list[str]:
    images: list[str] = []
    if isinstance(value, str):
        images.append(value)
    elif isinstance(value, list):
        for entry in value:
            images.extend(_coerce_image_entries(entry))
    elif isinstance(value, dict):
        for key in ("url", "contentUrl", "thumbnailUrl"):
            url = value.get(key)
            if isinstance(url, str):
                images.append(url)
    return images


def _dedupe_images(candidates: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []

    for candidate in candidates:
        cleaned = _clean_text(candidate)
        if not cleaned or not _looks_like_listing_image(cleaned):
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        results.append(cleaned)

    return results


def _looks_like_listing_image(url: str) -> bool:
    lowered = url.lower()
    if not lowered.startswith("http"):
        return False
    if any(token in lowered for token in ("sprite", "logo", "icon", "placeholder")):
        return False
    if "ebayimg.com" in lowered or "ebaystatic.com" in lowered:
        return True
    return lowered.endswith((".jpg", ".jpeg", ".png", ".webp"))


def _extract_primary_image(soup: BeautifulSoup) -> str | None:
    meta_image = _first_meta_content(
        soup,
        [
            ("property", "og:image"),
            ("property", "og:image:secure_url"),
            ("name", "twitter:image"),
            ("name", "twitter:image:src"),
        ],
    )
    if meta_image:
        return meta_image

    ld_image = _extract_ld_value(soup, "image")
    if ld_image:
        return ld_image

    img_tag = soup.select_one(
        "img#icImg, img[data-zoom-src], img[data-testid='ux-image-carousel-item'], "
        "img[data-testid='ux-image-carousel-image']"
    )
    if img_tag:
        return _clean_text(
            img_tag.get("data-zoom-src")
            or img_tag.get("src")
            or img_tag.get("data-src")
        )

    fallback_img = soup.select_one("img[src*='i.ebayimg.com']")
    if fallback_img:
        return _clean_text(fallback_img.get("src") or fallback_img.get("data-src"))

    return None


def _fetch_listing(
    session: requests.Session, url: str, timeout: float
) -> requests.Response:
    response = session.get(url, timeout=timeout, allow_redirects=True)
    if response.status_code in {403, 429}:
        _attempt_warmup(session, timeout)
        response = session.get(url, timeout=timeout, allow_redirects=True)

    return response


def _attempt_warmup(session: requests.Session, timeout: float) -> None:
    try:
        session.get("https://www.ebay.co.uk/", timeout=timeout, allow_redirects=True)
    except requests.RequestException as exc:
        message = f"scraper warmup failed: {type(exc).__name__} {repr(exc)}"
        logger.warning(message)
        print(message, flush=True)


def _extract_title(soup: BeautifulSoup) -> str | None:
    meta_title = _first_meta_content(
        soup,
        [
            ("property", "og:title"),
            ("name", "twitter:title"),
        ],
    )
    if meta_title:
        return meta_title

    ld_title = _extract_ld_value(soup, "name")
    if ld_title:
        return ld_title

    title_tag = (
        soup.select_one("h1#itemTitle")
        or soup.select_one("h1[data-testid='x-item-title__mainTitle']")
        or soup.select_one("h1.x-item-title__mainTitle")
        or soup.find("h1")
    )
    if title_tag:
        text = _clean_text(title_tag.get_text(" ", strip=True))
        if text:
            return text.replace("Details about", "").strip()

    if soup.title:
        return _clean_text(soup.title.get_text(strip=True))

    return None


def _extract_seller_location(soup: BeautifulSoup) -> str | None:
    ld_location = _extract_location_from_ld_json(soup)
    if ld_location:
        return ld_location

    selectors = [
        "#itemLocation",
        "#itemLocation span",
        "#itemLocation strong",
        "#itemLocation div",
        "#delLoc",
        "[itemprop='availableAtOrFrom']",
        "[itemprop='location']",
        "#sh-loc",
        "[data-testid='x-item-location']",
    ]

    for selector in selectors:
        node = soup.select_one(selector)
        if not node:
            continue

        text = _clean_text(node.get_text(" ", strip=True))
        if not text:
            continue

        cleaned = re.sub(
            r"(?i)^(item location|location|located in)[:\s]+",
            "",
            text,
        ).strip()
        if cleaned:
            return cleaned

    label_match = soup.find(string=re.compile(r"(item location|located in)", re.I))
    if label_match:
        text = _clean_text(label_match.parent.get_text(" ", strip=True))
        if text:
            cleaned = re.sub(
                r"(?i)^(item location|location|located in)[:\s]+",
                "",
                text,
            ).strip()
            if cleaned:
                return cleaned

    return None


def _extract_ld_value(soup: BeautifulSoup, key: str) -> str | None:
    for data in _iter_ld_json_objects(soup):
        value = data.get(key)
        if isinstance(value, str):
            cleaned = _clean_text(value)
            if cleaned:
                return cleaned
        if isinstance(value, list):
            for entry in value:
                if isinstance(entry, str):
                    cleaned = _clean_text(entry)
                    if cleaned:
                        return cleaned
        if isinstance(value, dict):
            url_value = value.get("url")
            if isinstance(url_value, str):
                cleaned = _clean_text(url_value)
                if cleaned:
                    return cleaned

    return None


def _extract_location_from_ld_json(soup: BeautifulSoup) -> str | None:
    for data in _iter_ld_json_objects(soup):
        available = _extract_location_from_value(data.get("availableAtOrFrom"))
        if available:
            return available

        offers = data.get("offers")
        location = _extract_location_from_offers(offers)
        if location:
            return location

    return None


def _extract_location_from_offers(offers: object) -> str | None:
    if isinstance(offers, list):
        for offer in offers:
            location = _extract_location_from_offers(offer)
            if location:
                return location
        return None

    if isinstance(offers, dict):
        for key in ("availableAtOrFrom", "seller", "areaServed", "location"):
            location = _extract_location_from_value(offers.get(key))
            if location:
                return location

    return None


def _extract_location_from_value(value: object) -> str | None:
    if isinstance(value, str):
        return _clean_text(value)

    if isinstance(value, list):
        for entry in value:
            location = _extract_location_from_value(entry)
            if location:
                return location
        return None

    if isinstance(value, dict):
        address = value.get("address")
        formatted = _format_address(address)
        if formatted:
            return formatted

        name = value.get("name")
        if isinstance(name, str):
            cleaned = _clean_text(name)
            if cleaned:
                return cleaned

        nested_location = value.get("location")
        if nested_location:
            return _extract_location_from_value(nested_location)

    return None


def _format_address(address: object) -> str | None:
    if isinstance(address, str):
        return _clean_text(address)

    if not isinstance(address, dict):
        return None

    parts = [
        address.get("addressLocality"),
        address.get("addressRegion"),
        address.get("addressCountry"),
        address.get("postalCode"),
    ]
    text = ", ".join([part for part in parts if part])
    return _clean_text(text)


def _iter_ld_json_objects(soup: BeautifulSoup) -> Iterable[dict]:
    scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    for script in scripts:
        raw = script.string or script.get_text(strip=True)
        if not raw:
            continue

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue

        yield from _normalize_ld_json(data)


def _normalize_ld_json(data: object) -> Iterable[dict]:
    if isinstance(data, list):
        for entry in data:
            yield from _normalize_ld_json(entry)
        return

    if isinstance(data, dict):
        graph = data.get("@graph")
        if isinstance(graph, list):
            for entry in graph:
                yield from _normalize_ld_json(entry)
        yield data


def _first_meta_content(
    soup: BeautifulSoup, pairs: Iterable[tuple[str, str]]
) -> str | None:
    for attr, value in pairs:
        tag = soup.find("meta", attrs={attr: value})
        if not tag:
            continue

        content = tag.get("content")
        if content:
            return content.strip()

    return None


def _clean_text(text: str | None) -> str | None:
    if not text:
        return None
    stripped = text.strip()
    return stripped or None
