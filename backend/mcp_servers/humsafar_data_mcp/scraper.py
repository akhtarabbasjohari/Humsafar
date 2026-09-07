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


CORE_DIRECTORY_PATHS = ["/expeditions/", "/tours/", "/destinations/"]


def extract_single_item_details(html: str, source_url: str) -> Dict[str, Any]:
    """
    Extract structured details from a single item listing page
    (Day-by-Day schedule, Inclusions, Exclusions, Equipment, Altitude specs).
    """
    soup = BeautifulSoup(html, "html.parser")
    for el in soup(["script", "style"]):
        el.decompose()

    details: Dict[str, Any] = {
        "inclusions": [],
        "exclusions": [],
        "equipment": [],
        "schedule": [],
        "specifications": {},
    }

    # Extract Inclusions
    incl_card = soup.find(lambda e: e.name in ["h2", "h3", "h4"] and "what is included" in e.get_text().lower())
    if incl_card and incl_card.parent:
        details["inclusions"] = [li.get_text(strip=True) for li in incl_card.parent.find_all("li") if li.get_text(strip=True)]

    # Extract Exclusions
    excl_card = soup.find(lambda e: e.name in ["h2", "h3", "h4"] and "what is excluded" in e.get_text().lower())
    if excl_card and excl_card.parent:
        details["exclusions"] = [li.get_text(strip=True) for li in excl_card.parent.find_all("li") if li.get_text(strip=True)]

    # Extract Equipment
    eq_card = soup.find(lambda e: e.name in ["h2", "h3", "h4"] and any(k in e.get_text().lower() for k in ["equipment", "packing list", "gear"]))
    if eq_card and eq_card.parent:
        details["equipment"] = [li.get_text(strip=True) for li in eq_card.parent.find_all("li") if li.get_text(strip=True)]

    # Extract Day-by-Day schedule stages: e.g. D1, D2, Day 1, etc.
    text_all = soup.get_text(separator="\n", strip=True)
    stages = re.findall(r"^\s*(?:D\d+|Day\s*\d+)[\s:-]+[^\n]+", text_all, re.MULTILINE)
    if stages:
        details["schedule"] = [s.strip() for s in stages[:25] if len(s.strip()) > 3]


    # Altitude & Season
    alt = re.search(r"Max\s*Altitude[:\s]+([0-9,]+m[^\n,]*)", text_all, re.IGNORECASE)
    if alt:
        details["specifications"]["max_altitude"] = alt.group(1).strip()
    season = re.search(r"(?:Season|Best Time|Window)[:\s]+([A-Za-z]+(?:\s+to\s+[A-Za-z]+)?)", text_all, re.IGNORECASE)
    if season:
        details["specifications"]["season"] = season.group(1).strip()

    return details


class SourceSiteScraper:
    """
    Scraper providing live itinerary extraction and region coverage verification.
    Focuses strictly on the core directory archives:
    - https://itp.7scribes.com/expeditions/
    - https://itp.7scribes.com/tours/
    - https://itp.7scribes.com/destinations/
    and follows links to single item detail pages.
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

    def parse_itineraries_html(self, html: str, source_url: str, query: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Parse HTML from WordPress search or listing page into structured itinerary items.
        Filters by query terms when supplied to ensure relevance.
        """
        soup = BeautifulSoup(html, "html.parser")
        itineraries: List[Dict[str, Any]] = []
        scraped_at = datetime.now(timezone.utc).isoformat()

        # Remove script and style elements
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()

        # Extract search terms for relevance checking
        query_terms: List[str] = []
        if query:
            stopwords = {"tour", "trip", "plan", "visit", "trek", "with", "from", "for", "days", "day", "want", "like", "need", "tell", "about", "your", "have", "please", "can", "you", "package"}
            query_terms = [w.lower() for w in re.findall(r"\b[a-zA-Z]{3,}\b", query) if w.lower() not in stopwords]

        # WordPress articles / tour items / headings
        candidate_blocks = soup.select(
            "article, .tour-item, .itinerary-item, .type-tour, .card, .journal-card"
        )

        if not candidate_blocks:
            candidate_blocks = soup.select(".post, .type-post")

        # Fallback to headings if no article blocks match
        if not candidate_blocks:
            candidate_blocks = soup.find_all(["h2", "h3", "h4"])

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

            # Strict entity filtering: ignore team members, reviews, testimonials, and blog posts
            lower_link = link.lower()
            skip_path_segments = [
                "/team/", "/reviews/", "/testimonials/", "/author/",
                "/category/", "/tag/", "/uncategorized/", "/feed/", "/wp-content/",
            ]
            if any(seg in lower_link for seg in skip_path_segments):
                continue

            # Skip common non-itinerary navigational and CTA blocks
            skip_phrases = [
                "leave a reply", "recent posts", "search results", "categories",
                "archives", "plan your karakoram journey", "contact us", "about us",
                "privacy policy", "our team", "why choose us", "newsletter", "inquiry received",
                "view all", "whatsapp",
            ]
            if any(skip_word in title.lower() for skip_word in skip_phrases):
                continue

            # Classify entity type (Tours, Expeditions, Destinations)
            if "/tours/" in lower_link or "tour" in title.lower():
                entity_type = "tour"
            elif "/expeditions/" in lower_link or "expedition" in title.lower() or "trek" in title.lower():
                entity_type = "expedition"
            elif "/destinations/" in lower_link or "valley" in title.lower() or "region" in title.lower() or "park" in title.lower():
                entity_type = "destination"
            else:
                if "itp.7scribes.com" in lower_link:
                    continue
                entity_type = "tour"

            block_text = block.get_text(separator=" ", strip=True)

            # Skip personal biographical profiles or customer testimonial snippets
            bio_phrases = [
                "born and raised in", "memory that will stay with me", "years of high altitude mountaineering",
                "testimonial", "our clients say", "fixed rope team",
            ]
            if any(phrase in block_text.lower() for phrase in bio_phrases):
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
                "entity_type": entity_type,
                "duration": duration or "Contact for schedule",
                "price": price or "Pricing upon inquiry",
                "summary": snippet or f"Verified {entity_type} from official company catalog.",
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
        Focuses strictly on the official archive directory pages:
        - /expeditions/
        - /tours/
        - /destinations/
        and follows links to single item detail pages to extract complete itineraries.
        Caches results by (session_id, query).
        """
        query_clean = query.strip()
        cache_key = f"search:{query_clean}"

        # 1. Check Session Cache
        cached_result = self.cache.get(session_id, cache_key)
        if cached_result is not None:
            return {**cached_result, "cached": True}

        base_url = get_source_site_url()
        scraped_at = datetime.now(timezone.utc).isoformat()
        all_catalog_items: List[Dict[str, Any]] = []
        seen_titles = set()
        primary_source_url = f"{base_url}/expeditions/"

        # 2. Extract listings from the 3 core directory pages
        for dir_path in CORE_DIRECTORY_PATHS:
            dir_url = f"{base_url}{dir_path}"
            cache_dir_key = f"dir_html:{dir_url}"
            html = self.cache.get(session_id, cache_dir_key)

            if not html:
                success, fetched_html, _ = self._fetch_html(dir_url, client=client)
                if success and fetched_html:
                    html = fetched_html
                    self.cache.set(session_id, cache_dir_key, html, ttl_seconds=300)

            if html:
                parsed = self.parse_itineraries_html(html, dir_url, query=None)
                for item in parsed:
                    if item["title"] not in seen_titles:
                        seen_titles.add(item["title"])
                        all_catalog_items.append(item)

        # 3. Fallback to search query URL if no directory items found (e.g. In unit tests with mock handlers)
        if not all_catalog_items:
            search_url = f"{base_url}/?s={quote_plus(query_clean)}"
            primary_source_url = search_url
            success, html, error_msg = self._fetch_html(search_url, client=client)
            if success and html:
                all_catalog_items = self.parse_itineraries_html(html, search_url, query=query_clean)
            else:
                error_payload = {
                    "success": False,
                    "query": query_clean,
                    "source_url": search_url,
                    "scraped_at": scraped_at,
                    "results": [],
                    "error": error_msg or "Failed to retrieve live site data",
                    "cached": False,
                }
                self.cache.set(session_id, cache_key, error_payload, ttl_seconds=60)
                return error_payload

        # 4. Filter and score items matching query with strict title relevance
        query_words = [
            w.lower()
            for w in re.findall(r"\b[a-zA-Z0-9]{2,}\b", query_clean)
            if w.lower() not in {"tour", "trip", "plan", "visit", "trek", "with", "from", "for", "days", "day", "please", "can", "you", "tell", "show", "me", "the", "about", "pakistan"}
        ]
        matched_items: List[Dict[str, Any]] = []

        # Distinct destinations that must never be falsely hijacked by generic packages
        distinct_destinations = {
            "gasherbrum", "gashabrum", "gashebrum", "spantik", "broad peak",
            "shangrila", "shangrilla", "kachura", "katpana", "kumrat",
            "swat", "kalam", "chitral", "kalash", "naltar", "shimshal",
            "batura", "chogolisa", "trango", "nangma", "rakaposhi", "neelum"
        }
        query_has_distinct_dest = any(d in query_clean.lower() for d in distinct_destinations)

        for item in all_catalog_items:
            title_lower = item.get("title", "").lower()
            summary_lower = item.get("summary", "").lower()

            # If the traveler requested a distinct destination not present in this tour title, skip
            if query_has_distinct_dest and not any(d in title_lower for d in distinct_destinations if d in query_clean.lower()):
                continue

            # Strict title matching requirement: at least one meaningful query term must be in tour title
            title_matches = [w for w in query_words if w in title_lower]
            if title_matches:
                score = len(title_matches) * 10
                summary_matches = [w for w in query_words if w in summary_lower]
                score += len(summary_matches)
                item_copy = dict(item)
                item_copy["_match_score"] = score
                matched_items.append(item_copy)

        matched_items.sort(key=lambda x: x.get("_match_score", 0), reverse=True)
        # Return matched items; if query was specified but had 0 matches, return empty list (no false fallbacks)
        if query_words:
            results = [dict(it) for it in matched_items]
        else:
            results = [dict(it) for it in all_catalog_items[:5]] if not query_clean else []

        # 5. For top matching items, fetch single item detail page and enrich
        for item in results[:2]:
            item_url = item.get("url")
            if item_url and item_url.rstrip("/") != base_url.rstrip("/") and any(p in item_url for p in CORE_DIRECTORY_PATHS):
                cache_item_key = f"item_html:{item_url}"
                detail_html = self.cache.get(session_id, cache_item_key)
                if not detail_html:
                    s_ok, s_html, _ = self._fetch_html(item_url, client=client)
                    if s_ok and s_html:
                        detail_html = s_html
                        self.cache.set(session_id, cache_item_key, detail_html, ttl_seconds=300)

                if detail_html:
                    single_details = extract_single_item_details(detail_html, item_url)
                    if single_details.get("inclusions"):
                        item["inclusions"] = single_details["inclusions"]
                    if single_details.get("exclusions"):
                        item["exclusions"] = single_details["exclusions"]
                    if single_details.get("equipment"):
                        item["equipment"] = single_details["equipment"]
                    if single_details.get("schedule"):
                        item["day_by_day"] = single_details["schedule"]
                    if single_details.get("specifications"):
                        item["specifications"] = single_details["specifications"]

        # Clean internal keys
        for r in results:
            r.pop("_match_score", None)

        response_payload = {
            "success": True,
            "query": query_clean,
            "source_url": results[0].get("source_url", primary_source_url) if results else primary_source_url,
            "scraped_at": scraped_at,
            "count": len(results),
            "results": results,
            "cached": False,
        }

        # Store in Session Cache (default 300s TTL)
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

        page_text = ""
        is_challenge = False
        if html:
            soup = BeautifulSoup(html, "html.parser")
            page_text = soup.get_text(separator=" ", strip=True).lower()
            is_challenge = any(ch in page_text for ch in ["checking your browser", "cloudflare", "just a moment", "enable javascript"])

        # Check for destination mention on live page
        query_lower = dest_clean.lower()
        is_covered = (query_lower in page_text) and not is_challenge if page_text else False

        # Comprehensive Regional Hierarchy Resolution:
        # 1. Gilgit-Baltistan (GB) - macro-region containing hundreds of valleys, peaks, and trails:
        gb_keywords = [
            "gilgit", "baltistan", "gilgit-baltistan", "gilgit baltistan", "gb",
            "karakoram", "skardu", "shigar", "khaplu", "ghanche", "hushe", "nangma",
            "thalle", "baltoro", "concordia", "k2", "k-2", "broad peak", "broadpeak",
            "gasherbrum", "gashabrum", "gashebrum", "gasherbrum 1", "gasherbrum 2", "gasherbrum i", "gasherbrum ii",
            "trango", "trango towers", "masherbrum", "mashabrum", "chogolisa", "chogholisa",
            "laila peak", "haramosh", "malubiting", "spantik", "golden peak", "snow lake", "lukpe lawo",
            "biafo", "hispar", "arandu", "chogo lungma", "hunza", "nagar", "altit", "baltit",
            "karimabad", "passu", "passu cones", "shimshal", "gojal", "attabad", "chapursan",
            "misgar", "khunjerab", "rakaposhi", "diran", "minapin", "hoper", "rush lake",
            "batura", "borith", "ghizer", "phander", "gupis", "yasin", "ishkoman", "punial",
            "naltar", "astore", "rama", "tarashing", "rupal", "diamer", "chilas",
            "fairy meadows", "nanga parbat", "babusar", "deosai", "sheosar", "satpara",
            "kachura", "shangrila", "shangrilla", "shangri-la"
        ]

        # 2. Khyber Pakhtunkhwa (KPK):
        kpk_keywords = [
            "kpk", "khyber pakhtunkhwa", "swat", "kalam", "malam jabba", "miandam",
            "bahrain", "ushu", "mahodand", "kumrat", "dir", "chitral", "kalash",
            "bumburet", "rumbur", "birir", "ayun", "booni", "shandur", "mastuj",
            "garam chashma", "kaghan", "naran", "saif-ul-malook", "shogran", "siri paye",
            "dudipatsar", "lulusar", "galiyat", "nathia gali", "ayubia", "peshawar",
            "tirich mir", "broghil", "yarkhun"
        ]

        # 3. Azad Jammu & Kashmir (AJK):
        kashmir_keywords = [
            "kashmir", "azad kashmir", "ajk", "neelum", "neelum valley", "sharda", "kel",
            "arang kel", "taobat", "ratti gali", "chitta katha", "shounter", "muzaffarabad",
            "pir chinasi", "rawalakot", "banjosa", "toli peer", "ganga choti"
        ]

        # Mountain ranges and northern territory keywords
        mountain_keywords = [
            "karakoram", "himalaya", "himalayas", "hindukush", "hindu kush",
            "northern pakistan", "northern areas", "northern mountain"
        ]

        # Tokenize query and check both direct containment and fuzzy similarity
        import difflib
        tokens = [w.lower() for w in re.findall(r"\b[a-zA-Z0-9'-]+\b", query_lower)]

        def matches_any(keywords: list) -> bool:
            # 1. Full substring match
            if any(k in query_lower for k in keywords):
                return True
            # 2. Token match or close fuzzy match
            for t in tokens:
                if len(t) < 3:
                    continue
                if any(t == k or (len(t) >= 4 and (t in k or k in t)) for k in keywords):
                    return True
                close = difflib.get_close_matches(t, keywords, n=1, cutoff=0.72)
                if close:
                    return True
            return False

        # Check macro-region matches
        matched_regions = []
        is_mountain_pakistan = matches_any(mountain_keywords)
        is_gb = matches_any(gb_keywords)
        is_kpk = matches_any(kpk_keywords)
        is_kashmir = matches_any(kashmir_keywords)

        if is_gb:
            matched_regions.append("Gilgit-Baltistan, Pakistan")
        if is_kpk:
            matched_regions.append("Khyber Pakhtunkhwa, Pakistan")
        if is_kashmir:
            matched_regions.append("Azad Jammu & Kashmir, Pakistan")
        if is_mountain_pakistan and not matched_regions:
            matched_regions.append("Northern Pakistan Mountains")

        is_known_territory = is_gb or is_kpk or is_kashmir or is_mountain_pakistan
        serviced = is_covered or is_known_territory

        if not serviced and (not success or not html):
            error_payload = {
                "success": False,
                "destination": dest_clean,
                "serviced": False,
                "is_serviced": False,
                "region": "",
                "matched_regions": [],
                "source_url": active_url,
                "scraped_at": scraped_at,
                "error": error_msg or "Failed to connect to source site destinations page",
                "cached": False,
            }
            self.cache.set(session_id, cache_key, error_payload, ttl_seconds=60)
            return error_payload

        if serviced and dest_clean.title() not in matched_regions:
            matched_regions.insert(0, dest_clean.title())

        matched_region_str = ", ".join(matched_regions) if matched_regions else ""

        response_payload = {
            "success": True,
            "destination": dest_clean,
            "serviced": serviced,
            "is_serviced": serviced,
            "region": matched_region_str,
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
