"""
Live scraping engine for humsafar-data-mcp.
Reads SOURCE_SITE_URL dynamically from the environment and extracts itineraries and regional coverage.
"""

import os
import re
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urljoin, quote_plus

import httpx
from bs4 import BeautifulSoup

from .cache import global_cache, SessionScopedCache

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10.0
USER_AGENT = "HumsafarBot/1.0 (+https://itp.7scribes.com; AI Travel Planner)"


def get_source_site_url() -> str:
    """
    Dynamically resolve the configured source site URL from environment.
    Never hardcode the domain inside scraping logic.
    """
    raw_url = os.getenv("SOURCE_SITE_URL", os.getenv("COMPANY_SITE_URL", "https://itp.7scribes.com")).strip()
    if not raw_url.startswith(("http://", "https://")):
        raw_url = f"https://{raw_url}"
    return raw_url.rstrip("/")


def extract_duration(text: str) -> Optional[str]:
    """
    Extract duration string like '14 Days', '7 Days / 6 Nights', '3 Weeks'.
    """
    patterns = [
        r"\b(\d+\s*(?:to\s*\d+\s*)?(?:days?|nights?|weeks?|hours?)(?:\s*/\s*\d+\s*nights?)?)\b",
        r"\bDuration\s*[:\-]\s*([^\n,;<]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def extract_price(text: str) -> Optional[str]:
    """
    Extract price information like 'PKR 195,000', 'USD 1,200', '$3,500', 'Rs. 45000'.
    """
    patterns = [
        r"\b((?:PKR|Rs\.?|USD|\$|EUR|€|GBP|£)\s*[\d,]+(?:\.\d{2})?(?:\s*(?:per\s*(?:person|couple|pax)|\/-\s*PKR|\/-\s*Rs|\/-\s*USD))?)",
        r"\bPrice\s*[:\-]\s*([^\n,;<]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


class SourceSiteScraper:
    """
    Scraper providing live itinerary extraction and region coverage verification.
    Uses session-scoped caching and fails gracefully on network errors.
    """

    def __init__(self, cache: Optional[SessionScopedCache] = None, timeout: float = DEFAULT_TIMEOUT):
        self.cache = cache or global_cache
        self.timeout = timeout

    def _fetch_html(
        self,
        url: str,
        client: Optional[httpx.Client] = None,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Safely fetch raw HTML from a target URL.
        Returns: (success: bool, html_or_none, error_message_or_none)
        """
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        try:
            if client is not None:
                resp = client.get(url, headers=headers, timeout=self.timeout, follow_redirects=True)
                resp.raise_for_status()
                return True, resp.text, None

            with httpx.Client(timeout=self.timeout, follow_redirects=True) as http:
                resp = http.get(url, headers=headers)
                resp.raise_for_status()
                return True, resp.text, None

        except httpx.TimeoutException:
            logger.warning("Scrape timeout while connecting to %s", url)
            return False, None, f"Connection timed out after {self.timeout}s"
        except httpx.HTTPStatusError as exc:
            logger.warning("HTTP status error %s while connecting to %s", exc.response.status_code, url)
            return False, None, f"Source site returned HTTP {exc.response.status_code}"
        except httpx.RequestError as exc:
            logger.warning("Request error while connecting to %s: %s", url, exc)
            return False, None, f"Network request error: {str(exc)}"
        except Exception as exc:
            logger.error("Unexpected scraping error for %s: %s", url, exc)
            return False, None, f"Scrape error: {str(exc)}"

    def parse_itineraries_html(self, html: str, source_url: str) -> List[Dict[str, Any]]:
        """
        Parse HTML from WordPress search or listing page into structured itinerary items.
        """
        soup = BeautifulSoup(html, "html.parser")
        itineraries: List[Dict[str, Any]] = []
        scraped_at = datetime.now(timezone.utc).isoformat()

        # Remove script and style elements
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()

        # WordPress articles / tour items (avoiding nested child content classes)
        candidate_blocks = soup.select(
            "article, .tour-item, .itinerary-item, .type-tour, .card"
        )

        if not candidate_blocks:
            candidate_blocks = soup.select(".post, .type-post")

        # Fallback to headings if no article blocks match
        if not candidate_blocks:
            candidate_blocks = soup.find_all(["h2", "h3"])

        seen_titles = set()

        for block in candidate_blocks:
            # Extract Title and Link
            title = None
            link = source_url

            heading_elem = block.find(["h1", "h2", "h3", "h4"])
            if heading_elem:
                title = heading_elem.get_text(strip=True)
                link_elem = heading_elem.find("a") or block.find("a")
            elif block.name in ["h1", "h2", "h3", "h4"]:
                title = block.get_text(strip=True)
                link_elem = block.find("a")
            else:
                link_elem = block.find("a")
                if link_elem:
                    title = link_elem.get_text(strip=True)

            if link_elem and link_elem.get("href"):
                link = urljoin(source_url, link_elem["href"])

            if not title or len(title) < 4 or title in seen_titles:
                continue

            block_text = block.get_text(separator=" ", strip=True)

            # Skip common non-itinerary navigational blocks
            if any(skip_word in title.lower() for skip_word in ["leave a reply", "recent posts", "search results", "categories", "archives"]):
                continue

            duration = extract_duration(block_text)
            price = extract_price(block_text)

            # Extract brief summary / route snippet
            snippet = ""
            p_tag = block.find("p")
            if p_tag:
                snippet = p_tag.get_text(strip=True)
            elif len(block_text) > len(title):
                snippet = block_text[len(title):].strip()[:240]

            itineraries.append({
                "title": title,
                "url": link,
                "duration": duration or "Contact for schedule",
                "price": price or "Pricing upon inquiry",
                "summary": snippet or "Verified itinerary from official company catalog.",
                "scraped_at": scraped_at,
                "source_url": source_url,
            })
            seen_titles.add(title)

        return itineraries

    def search_itineraries(
        self,
        query: str,
        session_id: str = "default",
        client: Optional[httpx.Client] = None,
    ) -> Dict[str, Any]:
        """
        Search and scrape live itinerary content for a destination or route.
        Caches results by (session_id, query).
        """
        query_clean = query.strip()
        cache_key = f"search:{query_clean}"

        # 1. Check Session Cache
        cached_result = self.cache.get(session_id, cache_key)
        if cached_result is not None:
            return {**cached_result, "cached": True}

        # 2. Build live target URL from configured SOURCE_SITE_URL
        base_url = get_source_site_url()
        search_url = f"{base_url}/?s={quote_plus(query_clean)}"
        scraped_at = datetime.now(timezone.utc).isoformat()

        # 3. Perform Live Scrape
        success, html, error_msg = self._fetch_html(search_url, client=client)

        if not success or not html:
            error_payload = {
                "success": False,
                "query": query_clean,
                "source_url": search_url,
                "scraped_at": scraped_at,
                "results": [],
                "error": error_msg or "Failed to retrieve live site data",
                "cached": False,
            }
            # Cache failure briefly (60s) to prevent spamming failing remote host
            self.cache.set(session_id, cache_key, error_payload, ttl_seconds=60)
            return error_payload

        # 4. Parse Itineraries
        results = self.parse_itineraries_html(html, search_url)

        response_payload = {
            "success": True,
            "query": query_clean,
            "source_url": search_url,
            "scraped_at": scraped_at,
            "count": len(results),
            "results": results,
            "cached": False,
        }

        # 5. Store in Session Cache (default 300s TTL)
        self.cache.set(session_id, cache_key, response_payload)
        return response_payload

    def check_region_coverage(
        self,
        destination: str,
        session_id: str = "default",
        client: Optional[httpx.Client] = None,
    ) -> Dict[str, Any]:
        """
        Determine whether a requested destination falls within a region the company serves,
        based on the source site's listed regions, destinations, or tour categories.
        """
        dest_clean = destination.strip()
        cache_key = f"region:{dest_clean}"

        # 1. Check Session Cache
        cached_result = self.cache.get(session_id, cache_key)
        if cached_result is not None:
            return {**cached_result, "cached": True}

        base_url = get_source_site_url()
        # Query destinations index or general search for the region name
        destinations_url = f"{base_url}/destinations/"
        scraped_at = datetime.now(timezone.utc).isoformat()

        # Try destinations page first, fallback to search query
        success, html, error_msg = self._fetch_html(destinations_url, client=client)
        active_url = destinations_url

        if not success or not html:
            # Fallback to WordPress search for the destination keyword
            active_url = f"{base_url}/?s={quote_plus(dest_clean)}"
            success, html, error_msg = self._fetch_html(active_url, client=client)

        if not success or not html:
            error_payload = {
                "success": False,
                "destination": dest_clean,
                "serviced": False,
                "matched_regions": [],
                "source_url": active_url,
                "scraped_at": scraped_at,
                "error": error_msg or "Failed to connect to source site destinations page",
                "cached": False,
            }
            self.cache.set(session_id, cache_key, error_payload, ttl_seconds=60)
            return error_payload

        soup = BeautifulSoup(html, "html.parser")
        page_text = soup.get_text(separator=" ", strip=True).lower()
        query_lower = dest_clean.lower()

        # Check for destination mention or related mountain region keywords
        is_covered = query_lower in page_text

        # Extract specific matched regions and landmarks
        known_pakistan_regions = [
            "karakoram", "himalaya", "hindukush", "baltistan", "skardu", "hunza",
            "nagar", "gilgit", "fairy meadows", "nanga parbat", "k2", "concordia",
            "deosai", "swat", "chitral", "kalash", "khunjerab", "passu", "shimshal",
            "ishkoman", "ghizer", "astore"
        ]

        matched_regions = [r.title() for r in known_pakistan_regions if r in page_text and (r in query_lower or query_lower in r or is_covered)]

        # If direct match or known region is present
        if not matched_regions and is_covered:
            matched_regions = [dest_clean.title()]

        serviced = is_covered or len(matched_regions) > 0

        response_payload = {
            "success": True,
            "destination": dest_clean,
            "serviced": serviced,
            "matched_regions": matched_regions,
            "coverage_details": (
                f"Destination '{dest_clean}' is verified as a serviced tour region on {base_url}."
                if serviced
                else f"Destination '{dest_clean}' was not directly located on the official listings of {base_url}."
            ),
            "source_url": active_url,
            "scraped_at": scraped_at,
            "cached": False,
        }

        self.cache.set(session_id, cache_key, response_payload)
        return response_payload


# Global scraper instance
scraper = SourceSiteScraper()
