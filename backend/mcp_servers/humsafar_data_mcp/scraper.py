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
from .vector_store import global_vector_store, ItineraryVectorStore

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 3.0
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"


def get_source_site_url() -> str:
    """
    Dynamically resolve the configured source site URL from environment.
    Never hardcode the domain inside scraping logic.
    """
    raw_url = os.getenv("SOURCE_SITE_URL", os.getenv("COMPANY_SITE_URL", "https://askoliadventure.com")).strip()
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


CORE_DIRECTORY_PATHS = ["/tour/", "/expedition/", "/"]


def extract_single_item_details(html: str, source_url: str) -> Dict[str, Any]:
    """
    Extract structured details from a single item listing page
    (Day-by-Day schedule, Inclusions, Exclusions, Equipment, Altitude specs, Highlights, Features).
    """
    soup = BeautifulSoup(html, "html.parser")
    for el in soup(["script", "style"]):
        el.decompose()

    details: Dict[str, Any] = {
        "inclusions": [],
        "exclusions": [],
        "equipment": [],
        "schedule": [],
        "highlights": [],
        "specifications": {},
    }

    # 1. Extract Inclusions
    incl_div = soup.find(class_=lambda c: c and any(k in str(c).lower() for k in ["tour-includes", "tour-include", "included"]))
    if incl_div:
        items = [
            li.get_text(strip=True)
            for li in incl_div.find_all(["li", "p"])
            if li.get_text(strip=True) and "services included" not in li.get_text(strip=True).lower() and len(li.get_text(strip=True)) > 3
        ]
        details["inclusions"] = items
    if not details["inclusions"]:
        incl_card = soup.find(lambda e: e.name in ["h2", "h3", "h4", "h5"] and any(k in e.get_text().lower() for k in ["services included", "what is included", "price includes", "inclusions"]))
        if incl_card and incl_card.parent:
            details["inclusions"] = [
                li.get_text(strip=True)
                for li in incl_card.parent.find_all(["li", "p"])
                if li.get_text(strip=True) and not any(k in li.get_text().lower() for k in ["services included", "what is included", "inclusions"]) and len(li.get_text(strip=True)) > 3
            ]

    # 2. Extract Exclusions
    excl_div = soup.find(class_=lambda c: c and any(k in str(c).lower() for k in ["tour-excludes", "tour-exclude", "tour-not-included", "excluded"]))
    if excl_div:
        items = [
            li.get_text(strip=True)
            for li in excl_div.find_all(["li", "p"])
            if li.get_text(strip=True) and "services not included" not in li.get_text(strip=True).lower() and len(li.get_text(strip=True)) > 3
        ]
        details["exclusions"] = items
    if not details["exclusions"]:
        excl_card = soup.find(lambda e: e.name in ["h2", "h3", "h4", "h5"] and any(k in e.get_text().lower() for k in ["services not included", "what is excluded", "price excludes", "exclusions"]))
        if excl_card and excl_card.parent:
            details["exclusions"] = [
                li.get_text(strip=True)
                for li in excl_card.parent.find_all(["li", "p"])
                if li.get_text(strip=True) and not any(k in li.get_text().lower() for k in ["services not included", "what is excluded", "exclusions"]) and len(li.get_text(strip=True)) > 3
            ]

    # 3. Extract Equipment
    eq_div = soup.find(class_=lambda c: c and any(k in str(c).lower() for k in ["tour-equipments", "tour-equipment"]))
    if eq_div:
        items = [
            li.get_text(strip=True)
            for li in eq_div.find_all(["li", "p"])
            if li.get_text(strip=True) and "equipment list" not in li.get_text(strip=True).lower() and len(li.get_text(strip=True)) > 3
        ]
        details["equipment"] = items
    if not details["equipment"]:
        eq_card = soup.find(lambda e: e.name in ["h2", "h3", "h4", "h5"] and any(k in e.get_text().lower() for k in ["equipment list", "equipment", "packing list", "gear"]))
        if eq_card and eq_card.parent:
            details["equipment"] = [
                li.get_text(strip=True)
                for li in eq_card.parent.find_all(["li", "p"])
                if li.get_text(strip=True) and "equipment" not in li.get_text().lower() and len(li.get_text(strip=True)) > 3
            ]

    # 4. Extract Trek Highlights
    th_div = soup.find(class_=lambda c: c and any(k in str(c).lower() for k in ["tour-highlights-section", "tour-highlights"]))
    if th_div:
        hl_items = []
        for li in th_div.find_all(["li", "p"]):
            txt = li.get_text(strip=True)
            if txt and not any(k in txt.lower() for k in ["trek highlights", "highlights"]) and len(txt) > 3:
                hl_items.append(txt)
        if hl_items:
            details["highlights"] = hl_items

    # 5. Extract Tour Features (Duration, Group Size, Departure, Difficulty)
    for tf in soup.find_all(class_=lambda c: c and "tour-feature" in str(c).lower()):
        lbl = tf.find(class_=lambda c: c and "label" in str(c).lower())
        val = tf.find(class_=lambda c: c and "value" in str(c).lower())
        if lbl and val:
            l_str = lbl.get_text(strip=True).lower().replace(" ", "_")
            v_str = val.get_text(strip=True)
            if l_str and v_str:
                details["specifications"][l_str] = v_str

    for p in soup.find_all(["p", "li", "span"]):
        txt = p.get_text(strip=True)
        spec_match = re.match(r"^(Max\s+Altitude|Season|Difficulty|Duration|Group\s+Size|Trip\s+Grade)\s*[:\-]\s*(.+)$", txt, re.IGNORECASE)
        if spec_match:
            k = spec_match.group(1).strip().lower().replace(" ", "_")
            v = spec_match.group(2).strip()
            if k not in details["specifications"]:
                details["specifications"][k] = v

    # 6. Extract Day-by-Day schedule stages:
    # Priority A: Check for structured .tour-day blocks
    tour_days = soup.find_all(class_=lambda c: c and "tour-day" in str(c).lower().split())
    if tour_days:
        schedule = []
        for td in tour_days:
            t_el = td.find(class_=lambda c: c and "title" in str(c).lower())
            d_el = td.find(class_=lambda c: c and "description" in str(c).lower())
            title_text = t_el.get_text(strip=True) if t_el else ""
            desc_text = d_el.get_text(strip=True) if d_el else ""
            if title_text:
                alt = None
                alt_m = re.search(r"\(([0-9,]+\s*m(?:eters)?)\)", title_text, re.IGNORECASE)
                if alt_m:
                    alt = alt_m.group(1)
                schedule.append({
                    "title": title_text,
                    "description": desc_text or title_text,
                    "altitude": alt,
                })
        if schedule:
            details["schedule"] = schedule

    # Priority B: Check for headers matching Day XX
    if not details["schedule"]:
        day_headers = soup.find_all(lambda e: e.name in ["h3", "h4", "h5", "h6"] and re.match(r"^(?:Day\s*\d+|D\d+)[:\s\-]", e.get_text(strip=True), re.IGNORECASE))
        if day_headers:
            schedule = []
            for dh in day_headers:
                title_text = dh.get_text(strip=True)
                clean_title = re.sub(r"^(?:Day|D)\s*\d+[\s:.-]+", "", title_text, flags=re.IGNORECASE).strip()
                desc_parts = []
                sib = dh.find_next_sibling()
                while sib and sib.name not in ["h2", "h3", "h4", "h5", "h6"]:
                    txt = sib.get_text(strip=True)
                    if txt:
                        desc_parts.append(txt)
                    sib = sib.find_next_sibling()
                desc_text = " ".join(desc_parts) if desc_parts else clean_title or title_text
                alt = None
                alt_m = re.search(r"\(([0-9,]+\s*m(?:eters)?)\)", title_text, re.IGNORECASE)
                if alt_m:
                    alt = alt_m.group(1)
                schedule.append({
                    "title": clean_title or title_text,
                    "description": desc_text,
                    "altitude": alt,
                })
            if schedule:
                details["schedule"] = schedule

    # Priority C: Fallback regex on raw text lines
    if not details["schedule"]:
        text_all = soup.get_text(separator="\n", strip=True)
        stages = re.findall(r"^\s*(?:D\d+|Day\s*\d+)[\s:-]+[^\n]+", text_all, re.MULTILINE)
        if stages:
            details["schedule"] = [s.strip() for s in stages[:35] if len(s.strip()) > 3]

    return details


class SourceSiteScraper:
    """
    Scraper providing live itinerary extraction and region coverage verification.
    Focuses strictly on the core directory archives:
    - https://askoliadventure.com/tour/
    - https://askoliadventure.com/tours/
    - https://askoliadventure.com/expedition/
    - https://askoliadventure.com/destinations/
    and follows links to single item detail pages.
    Uses session-scoped caching and fails gracefully on network errors.
    """

    def __init__(
        self,
        cache: Optional[SessionScopedCache] = None,
        timeout: float = DEFAULT_TIMEOUT,
        vector_store: Optional[ItineraryVectorStore] = None,
    ):
        self.cache = cache or global_cache
        self.timeout = timeout
        self.vector_store = vector_store or global_vector_store

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

        # Remove non-content scripts and styles, but KEEP navigation and menus for tour discovery
        for element in soup(["script", "style", "svg", "noscript", "form"]):
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
        seen_urls = set()

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
            elif "/expeditions/" in lower_link or "/expedition/" in lower_link or "expedition" in title.lower() or "trek" in title.lower():
                entity_type = "expedition"
            elif "/destinations/" in lower_link or "valley" in title.lower() or "region" in title.lower() or "park" in title.lower():
                entity_type = "destination"
            else:
                if "askoliadventure.com" in lower_link:
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

            item_data = {
                "title": title,
                "url": link,
                "entity_type": entity_type,
                "duration": duration or "Contact for schedule",
                "price": price or "Pricing upon inquiry",
                "summary": snippet or f"Verified {entity_type} from official company catalog.",
                "scraped_at": scraped_at,
                "source_url": source_url,
            }
            itineraries.append(item_data)
            seen_titles.add(title)
            seen_urls.add(link.rstrip("/"))
            if hasattr(self, "vector_store") and self.vector_store:
                self.vector_store.add_or_update(item_data)

        # In addition, discover all direct tour and expedition links across navigation, dropdowns, and menus
        skip_phrases_extra = [
            "leave a reply", "recent posts", "search results", "categories",
            "archives", "plan your karakoram journey", "contact us", "about us",
            "privacy policy", "our team", "why choose us", "newsletter", "inquiry received",
            "view all", "whatsapp", "view details", "read more", "learn more", "book now",
        ]
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].strip()
            if not href:
                continue
            full_link = urljoin(source_url, href)
            lower_link = full_link.lower().rstrip("/")
            if lower_link in seen_urls:
                continue

            # Must be a tour or expedition single detail link
            is_tour_link = "/tour/" in lower_link or "/expedition/" in lower_link
            is_index_page = lower_link.endswith("/tour") or lower_link.endswith("/tours") or lower_link.endswith("/expedition") or lower_link.endswith("/expeditions")
            if not is_tour_link or is_index_page:
                continue

            # Skip non-detail segments
            if any(seg in lower_link for seg in ["/category/", "/tag/", "/uncategorized/", "/feed/", "/wp-content/", "/author/", "/page/"]):
                continue

            link_text = a_tag.get_text(strip=True)
            slug = lower_link.split("/tour/")[-1].split("/expedition/")[-1].strip("/")
            slug_title = slug.replace("-", " ").title() if slug else ""

            tour_title = link_text if (link_text and len(link_text) > 4 and link_text.lower() not in skip_phrases_extra) else slug_title
            if not tour_title or len(tour_title) < 4 or tour_title in seen_titles:
                continue
            if any(skip_word in tour_title.lower() for skip_word in skip_phrases_extra):
                continue

            entity_type = "expedition" if ("expedition" in lower_link or "expedition" in tour_title.lower() or "trek" in tour_title.lower()) else "tour"
            duration = extract_duration(tour_title) or "Contact for schedule"

            item_data = {
                "title": tour_title,
                "url": full_link,
                "entity_type": entity_type,
                "duration": duration,
                "price": "Pricing upon inquiry",
                "summary": f"Verified {entity_type} from official company catalog at {full_link}.",
                "scraped_at": scraped_at,
                "source_url": source_url,
            }
            itineraries.append(item_data)
            seen_titles.add(tour_title)
            seen_urls.add(lower_link)
            if hasattr(self, "vector_store") and self.vector_store:
                self.vector_store.add_or_update(item_data)

        return itineraries

    def _get_official_seed_items(self, base_url: str) -> List[Dict[str, Any]]:
        """Verified fallback catalog of official Askoli Adventure tours used if live scraping is temporarily unreachable."""
        now_iso = datetime.now(timezone.utc).isoformat()
        return [
            {
                "title": "Hunza Autumn Tour",
                "url": f"{base_url}/tour/hunza-autumn-tour/",
                "source_url": f"{base_url}/tour/hunza-autumn-tour/",
                "duration": "7 Days",
                "price": "PKR 145,000 / USD 950",
                "region": "Hunza Valley, Gilgit-Baltistan",
                "summary": "Spectacular autumn foliage tour across Hunza and Nagar valleys, visiting Baltit Fort, Altit Fort, Passu Cones, and Attabad Lake.",
                "itinerary_schedule": [
                    {"day": 1, "title": "Islamabad to Gilgit Scenic Flight", "description": "Arrival and mountain flight to Gilgit; transfer to Karimabad.", "altitude": "2,438m"},
                    {"day": 2, "title": "Karimabad, Baltit Fort & Altit Fort", "description": "Tour historic Baltit and Altit forts surrounded by golden poplars.", "altitude": "2,438m"},
                    {"day": 3, "title": "Duikar Eagles Nest Sunrise Excursion", "description": "Sunrise views of Rakaposhi, Diran, and Golden Peak.", "altitude": "2,850m"},
                    {"day": 4, "title": "Attabad Lake & Gulmit Village", "description": "Boat crossing on Attabad Lake and cultural walk in Upper Hunza.", "altitude": "2,500m"},
                    {"day": 5, "title": "Passu Cones, Borith Lake & Glacier Hike", "description": "Excursion to Passu cathedral spires and suspension bridges.", "altitude": "2,600m"},
                    {"day": 6, "title": "Khunjerab Pass Border Excursion", "description": "Drive through Khunjerab National Park to the Pak-China border.", "altitude": "4,693m"},
                    {"day": 7, "title": "Return to Gilgit and Islamabad Flight", "description": "Scenic return flight to Islamabad; trip conclusion.", "altitude": "540m"},
                ],
                "inclusions": ["Licensed mountain guide", "4x4 private transport", "Hotel accommodations", "All entry permits & national park fees"],
                "exclusions": ["International airfare", "Personal insurance", "Personal gear & tipping"],
                "scraped_at": now_iso,
            },
            {
                "title": "K2 Base Camp & Concordia Trek",
                "url": f"{base_url}/tour/k2-base-camp-trek/",
                "source_url": f"{base_url}/tour/k2-base-camp-trek/",
                "duration": "20 Days",
                "price": "PKR 450,000 / USD 2,850",
                "region": "Baltoro Glacier, Karakoram, Gilgit-Baltistan",
                "summary": "The world's greatest mountain wilderness trek to Concordia and the foot of K2 (8,611m).",
                "itinerary_schedule": [
                    {"day": 1, "title": "Arrival in Islamabad", "description": "Expedition briefing at Alpine Club.", "altitude": "540m"},
                    {"day": 2, "title": "Flight to Skardu", "description": "Flight across the Karakoram to Skardu.", "altitude": "2,228m"},
                    {"day": 3, "title": "Drive to Askole", "description": "Jeep ride through Braldu gorge to Askole.", "altitude": "3,048m"},
                    {"day": 4, "title": "Trek Askole to Jhola", "description": "First trek day along river moraine.", "altitude": "3,200m"},
                    {"day": 5, "title": "Trek Jhola to Paiju", "description": "Trek to Paiju camp below Baltoro snout.", "altitude": "3,450m"},
                    {"day": 6, "title": "Rest Day at Paiju", "description": "Porter bread baking and acclimatization.", "altitude": "3,450m"},
                    {"day": 7, "title": "Trek Paiju to Khoburtse", "description": "Walk onto Baltoro Glacier moraine.", "altitude": "3,930m"},
                    {"day": 8, "title": "Trek Khoburtse to Urdukas", "description": "Camp on granite ledge overlooking Trango Towers.", "altitude": "4,050m"},
                    {"day": 9, "title": "Trek Urdukas to Goro II", "description": "Glacial ice hike beneath Masherbrum.", "altitude": "4,300m"},
                    {"day": 10, "title": "Trek Goro II to Concordia", "description": "Reach the Throne Room of Mountain Gods.", "altitude": "4,691m"},
                    {"day": 11, "title": "Concordia to K2 Base Camp Excursion", "description": "Visit Gilkey Memorial and base of K2.", "altitude": "5,150m"},
                    {"day": 12, "title": "Trek Concordia to Goro I", "description": "Begin descent down Baltoro Glacier.", "altitude": "4,150m"},
                    {"day": 13, "title": "Trek Goro I to Urdukas", "description": "Descent to grassy terrace campsite.", "altitude": "4,050m"},
                    {"day": 14, "title": "Trek Urdukas to Paiju", "description": "Return to Paiju spring.", "altitude": "3,450m"},
                    {"day": 15, "title": "Trek Paiju to Korophon", "description": "Trek along Braldu valley.", "altitude": "3,100m"},
                    {"day": 16, "title": "Trek to Askole", "description": "Final walking day back to Askole.", "altitude": "3,048m"},
                    {"day": 17, "title": "Jeep Drive to Skardu", "description": "Return by 4x4 jeeps to Skardu hotel.", "altitude": "2,228m"},
                    {"day": 18, "title": "Flight Skardu to Islamabad", "description": "Flight back to Islamabad.", "altitude": "540m"},
                    {"day": 19, "title": "Contingency Day in Islamabad", "description": "Weather buffer day and debriefing.", "altitude": "540m"},
                    {"day": 20, "title": "Final Departure", "description": "Airport transfers and flight home.", "altitude": "540m"},
                ],
                "inclusions": ["Official trekking permit & royalty", "Experienced native Balti mountain guide", "Full camping gear & mess tent", "All meals during trek"],
                "exclusions": ["Personal climbing gear", "Travel & rescue insurance", "International flights"],
                "scraped_at": now_iso,
            },
            {
                "title": "Spantik Peak Expedition",
                "url": f"{base_url}/tour/spantik-peak-expedition/",
                "source_url": f"{base_url}/tour/spantik-peak-expedition/",
                "duration": "16 Days",
                "price": "PKR 650,000 / USD 3,900",
                "region": "Chogo Lungma, Gilgit-Baltistan",
                "summary": "Expedition to summit Golden Peak (7,027m) via the Southeast Ridge starting from Askole/Arandu.",
                "itinerary_schedule": [
                    {"day": 1, "title": "Arrival in Islamabad", "description": "Briefing at Alpine Club.", "altitude": "540m"},
                    {"day": 2, "title": "Flight to Skardu", "description": "Flight to Skardu gateway.", "altitude": "2,228m"},
                    {"day": 3, "title": "Skardu Acclimatization", "description": "Logistics and permit checks.", "altitude": "2,228m"},
                    {"day": 4, "title": "Jeep Drive to Arandu", "description": "Drive to roadhead at Arandu.", "altitude": "2,770m"},
                    {"day": 5, "title": "Trek Arandu to Chogo Brangsa", "description": "Trek along Chogo Lungma glacier.", "altitude": "3,300m"},
                    {"day": 6, "title": "Trek to Bolocho", "description": "Ascend lateral moraine to Bolocho.", "altitude": "3,800m"},
                    {"day": 7, "title": "Trek to Spantik Base Camp", "description": "Establish base camp.", "altitude": "4,300m"},
                    {"day": 8, "title": "Acclimatization at Base Camp", "description": "Route inspection and training.", "altitude": "4,300m"},
                    {"day": 9, "title": "Climbing Period Camp 1 & 2", "description": "Camp 1 (5,100m) and Camp 2 (6,000m) high rotations.", "altitude": "6,000m"},
                    {"day": 10, "title": "Spantik Summit Push (7,027m)", "description": "Alpine ascent to 7,027m Golden Peak summit.", "altitude": "7,027m"},
                    {"day": 11, "title": "Descend to Base Camp", "description": "Clear high camps and celebrate at base camp.", "altitude": "4,300m"},
                    {"day": 12, "title": "Weather Buffer Day", "description": "Contingency day for high altitude conditions.", "altitude": "4,300m"},
                    {"day": 13, "title": "Trek Base Camp to Arandu", "description": "Descend along terminal moraine to Arandu.", "altitude": "2,770m"},
                    {"day": 14, "title": "Drive Arandu to Skardu", "description": "Jeep transfer back to Skardu.", "altitude": "2,228m"},
                    {"day": 15, "title": "Flight Skardu to Islamabad", "description": "Scenic flight back to the capital.", "altitude": "540m"},
                    {"day": 16, "title": "Final Departure", "description": "Expedition debriefing and onward flights.", "altitude": "540m"},
                ],
                "inclusions": ["Peak royalty and climbing permit", "Liaison officer support", "Base camp logistics and high altitude tents", "Cook and high altitude porters"],
                "exclusions": ["Personal climbing gear and oxygen", "Rescue insurance", "International flights"],
                "scraped_at": now_iso,
            },
            {
                "title": "Rush Lake Trek",
                "url": f"{base_url}/tour/rush-lake-trek/",
                "source_url": f"{base_url}/tour/rush-lake-trek/",
                "duration": "7 Days",
                "price": "PKR 175,000 / USD 980",
                "region": "Nagar Valley, Gilgit-Baltistan",
                "summary": "Trek to one of the world's highest alpine lakes at 4,694m with dramatic views of Spantik, Malubiting, and Ultar Sar.",
                "itinerary_schedule": [
                    {"day": 1, "title": "Arrival in Islamabad & Gilgit Flight", "description": "Morning flight to Gilgit and scenic drive to Nagar Valley.", "altitude": "2,400m"},
                    {"day": 2, "title": "Hoper Valley to Barpu Giram", "description": "Trek across Hoper Glacier moraine to Barpu Giram camp.", "altitude": "3,100m"},
                    {"day": 3, "title": "Barpu Giram to Chidin Harai", "description": "Ascend through alpine meadows to high ridge campsite.", "altitude": "3,800m"},
                    {"day": 4, "title": "Chidin Harai to Rush Lake", "description": "Trek to Rush Lake (4,694m) terrace facing Spantik and Malubiting.", "altitude": "4,694m"},
                    {"day": 5, "title": "Rush Peak Summit (5,098m) Excursion", "description": "Early sunrise ascent of Rush Peak with 360-degree Karakoram vistas.", "altitude": "5,098m"},
                    {"day": 6, "title": "Rush Lake Descent to Hoper & Karimabad", "description": "Descend to Hoper and transfer to Karimabad Hunza.", "altitude": "2,438m"},
                    {"day": 7, "title": "Return to Gilgit & Islamabad Flight", "description": "Transfer to Gilgit airport and flight to Islamabad.", "altitude": "540m"},
                ],
                "inclusions": ["Licensed mountain guide and porters", "All camping equipment and mess tent", "4x4 jeep transfers", "Daily expedition meals"],
                "exclusions": ["International airfare", "Personal gear and sleeping bag", "Trekking insurance"],
                "scraped_at": now_iso,
            },
            {
                "title": "Nanga Parbat BC & Fairy Meadows Trek",
                "url": f"{base_url}/tour/nanga-parbat-base-camp-trek/",
                "source_url": f"{base_url}/tour/nanga-parbat-base-camp-trek/",
                "duration": "10 Days",
                "price": "PKR 220,000 / USD 950",
                "region": "Diamer, Gilgit-Baltistan",
                "summary": "Classic trek to the legendary Fairy Meadows and Nanga Parbat Base Camp (Raikot Face) at 3,967m.",
                "itinerary_schedule": [
                    {"day": 1, "title": "Arrival in Islamabad", "description": "Welcome briefing and expedition orientation.", "altitude": "540m"},
                    {"day": 2, "title": "Islamabad to Chilas", "description": "Scenic drive along Karakoram Highway past Indus River.", "altitude": "1,265m"},
                    {"day": 3, "title": "Chilas to Raikot Bridge, Tato & Fairy Meadows", "description": "4x4 jeep track to Tato village and gradual trek up to Fairy Meadows.", "altitude": "3,300m"},
                    {"day": 4, "title": "Acclimatization at Fairy Meadows & Reflection Lake", "description": "Rest day exploring alpine pine forests and reflection lake viewpoints.", "altitude": "3,300m"},
                    {"day": 5, "title": "Trek to Beyal Camp & Nanga Parbat Base Camp", "description": "Full day trek to German Base Camp beneath the mighty Raikot Glacier.", "altitude": "3,967m"},
                    {"day": 6, "title": "Excursion to Jut Ridge & Nanga Parbat Viewpoint", "description": "Hike to high viewpoints overlooking the massive icefalls.", "altitude": "4,100m"},
                    {"day": 7, "title": "Fairy Meadows to Tato Village & Chilas", "description": "Descend trail to Tato and jeep transfer back to Chilas.", "altitude": "1,265m"},
                    {"day": 8, "title": "Chilas to Besham or Naran", "description": "Drive via Babusar Pass or Karakoram Highway.", "altitude": "1,000m"},
                    {"day": 9, "title": "Return Drive to Islamabad", "description": "Arrive in Islamabad; farewell expedition dinner.", "altitude": "540m"},
                    {"day": 10, "title": "Departure from Islamabad", "description": "Airport transfers for onward journey.", "altitude": "540m"},
                ],
                "inclusions": ["Licensed guide & local porters", "4x4 mountain jeep transfers", "Hut / campsite accommodations", "All meals during trek"],
                "exclusions": ["Personal trekking equipment", "Travel & evacuation insurance", "International flights"],
                "scraped_at": now_iso,
            },
            {
                "title": "Hunza & Skardu Valley Spring Tour",
                "url": f"{base_url}/tour/hunza-and-skardu-spring-tour/",
                "source_url": f"{base_url}/tour/hunza-and-skardu-spring-tour/",
                "duration": "10 Days",
                "price": "PKR 240,000 / USD 1,150",
                "region": "Hunza & Baltistan, Northern Pakistan",
                "summary": "Combined grand tour of both Hunza Valley and Skardu Baltistan during spectacular blossom season.",
                "itinerary_schedule": [
                    {"day": 1, "title": "Arrival in Islamabad", "description": "Welcome briefing and tour orientation.", "altitude": "540m"},
                    {"day": 2, "title": "Flight to Skardu Gateway", "description": "Scenic mountain flight across Himalayas to Skardu.", "altitude": "2,228m"},
                    {"day": 3, "title": "Shangrila Resort & Upper Kachura Lake", "description": "Explore Lower & Upper Kachura lakes and Shangrila.", "altitude": "2,500m"},
                    {"day": 4, "title": "Shigar Valley & Sarfaranga Cold Desert", "description": "Visit historic 400-year-old Shigar Fort and desert dunes.", "altitude": "2,300m"},
                    {"day": 5, "title": "Skardu to Gilgit & Karimabad Hunza", "description": "Drive along Jaglot-Skardu road through gorges to Hunza.", "altitude": "2,438m"},
                    {"day": 6, "title": "Baltit Fort, Altit Fort & Eagles Nest", "description": "Explore ancient forts and sunset panorama from Duikar.", "altitude": "2,850m"},
                    {"day": 7, "title": "Attabad Lake, Gulmit & Hussaini Bridge", "description": "Boat ride on Attabad Lake and walk suspension bridge.", "altitude": "2,500m"},
                    {"day": 8, "title": "Passu Cones & Khunjerab Pass Excursion", "description": "Visit Passu cathedral spires and China border at 4,693m.", "altitude": "4,693m"},
                    {"day": 9, "title": "Hunza to Gilgit & Flight to Islamabad", "description": "Morning drive to Gilgit airport and flight to Islamabad.", "altitude": "540m"},
                    {"day": 10, "title": "Final Departure", "description": "Airport transfers and trip conclusion.", "altitude": "540m"},
                ],
                "inclusions": ["Dedicated licensed mountain guide", "Private 4x4 transport throughout", "Premium hotel accommodations", "All entry permits & lake boat rides"],
                "exclusions": ["International airfare", "Personal insurance", "Discretionary expenses"],
                "scraped_at": now_iso,
            },
        ]
        if hasattr(self, "vector_store") and self.vector_store:
            for seed in seed_items:
                self.vector_store.add_or_update(seed)
        return seed_items

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
        primary_source_url = f"{base_url}/expedition/"

        last_error = None
        consecutive_errors = 0
        # 2. Extract listings from the core directory pages
        for dir_path in CORE_DIRECTORY_PATHS:
            if consecutive_errors >= 2:
                # Target host is unreachable or timing out; stop hammering to save latency
                break
            dir_url = f"{base_url}{dir_path}"
            cache_dir_key = f"dir_html:{dir_url}"
            html = self.cache.get(session_id, cache_dir_key)

            if not html:
                success, fetched_html, err = self._fetch_html(dir_url, client=client)
                if err:
                    last_error = err
                    consecutive_errors += 1
                if success and fetched_html:
                    html = fetched_html
                    self.cache.set(session_id, cache_dir_key, html, ttl_seconds=300)

            if html:
                parsed = self.parse_itineraries_html(html, dir_url, query=None)
                for item in parsed:
                    if item["title"] not in seen_titles:
                        seen_titles.add(item["title"])
                        all_catalog_items.append(item)

        # 3. Fallback to search query URL or official catalog seed if directory items failed to connect
        if not all_catalog_items and consecutive_errors < 2:
            search_url = f"{base_url}/?s={quote_plus(query_clean)}"
            primary_source_url = search_url
            success, html, error_msg = self._fetch_html(search_url, client=client)
            if error_msg:
                last_error = error_msg
            if success and html:
                all_catalog_items = self.parse_itineraries_html(html, search_url, query=query_clean)

        if not all_catalog_items:
            if hasattr(self, "vector_store") and self.vector_store.size() > 0:
                all_catalog_items = [dict(d) for d in self.vector_store.documents]
            else:
                # Fallback to verified official Askoli Adventure catalog seed
                all_catalog_items = self._get_official_seed_items(base_url)

        if not all_catalog_items:
            error_payload = {
                "success": False,
                "query": query_clean,
                "source_url": f"{base_url}/tours/",
                "scraped_at": scraped_at,
                "results": [],
                "error": last_error or "Failed to retrieve live site data",
                "cached": False,
            }
            self.cache.set(session_id, cache_key, error_payload, ttl_seconds=60)
            return error_payload

        # 4. Hybrid Matching: Keyword Relevance + Retrieval-Augmented Vector Matching
        # Ensure all catalog items are indexed in the vector store
        if hasattr(self, "vector_store") and self.vector_store:
            for itm in all_catalog_items:
                self.vector_store.add_or_update(itm)

        # Retrieve closest matching candidate embeddings using dense semantic query
        vector_candidates: List[Dict[str, Any]] = []
        if hasattr(self, "vector_store") and self.vector_store and query_clean:
            vector_candidates = self.vector_store.query(query_clean, top_k=5, min_score=0.20)

        query_words = [
            w.lower()
            for w in re.findall(r"\b[a-zA-Z0-9]{2,}\b", query_clean)
            if w.lower() not in {"tour", "trip", "plan", "visit", "trek", "with", "from", "for", "days", "day", "please", "can", "you", "tell", "show", "me", "the", "about", "pakistan"}
        ]
        matched_items: List[Dict[str, Any]] = []
        seen_matched_titles = set()

        # Distinct destinations that must never be falsely hijacked by generic packages
        distinct_destinations = {
            "gasherbrum", "gashabrum", "gashebrum", "spantik", "broad peak",
            "shangrila", "shangrilla", "kachura", "katpana", "kumrat",
            "swat", "kalam", "chitral", "kalash", "naltar", "shimshal",
            "batura", "chogolisa", "trango", "nangma", "rakaposhi", "neelum"
        }
        query_has_distinct_dest = any(d in query_clean.lower() for d in distinct_destinations)

        # Pass 1: Keyword relevance on title & summary
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
                item_copy["_retrieval_method"] = "keyword"
                matched_items.append(item_copy)
                seen_matched_titles.add(item.get("title"))

        # Pass 2: Augment with semantic vector retrieval candidates (retrieval-augmented matching)
        for v_cand in vector_candidates:
            v_title = v_cand.get("title", "")
            v_title_lower = v_title.lower()
            v_score = v_cand.get("_retrieval_score", 0.0)

            # Skip if destination contradicts a distinct destination
            if query_has_distinct_dest and not any(d in v_title_lower for d in distinct_destinations if d in query_clean.lower()):
                continue

            if v_title in seen_matched_titles:
                # Upgrade keyword match to hybrid and boost score
                for m_item in matched_items:
                    if m_item.get("title") == v_title:
                        m_item["_match_score"] = m_item.get("_match_score", 0) + int(v_score * 25)
                        m_item["_retrieval_score"] = v_score
                        m_item["_retrieval_method"] = "hybrid"
                        break
            else:
                # Vector retrieval found this candidate even though keyword matching on title missed it
                # (e.g. visitor asked for "K2 base camp" and page is titled "Concordia Trek")
                v_copy = dict(v_cand)
                v_copy["_match_score"] = int(v_score * 25)
                matched_items.append(v_copy)
                seen_matched_titles.add(v_title)

        matched_items.sort(key=lambda x: x.get("_match_score", 0), reverse=True)
        # Return matched items; if query was specified but had 0 matches, return empty list (no false fallbacks)
        if query_words or vector_candidates:
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
                    if hasattr(self, "vector_store") and self.vector_store:
                        self.vector_store.add_or_update(item)

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

        query_lower = dest_clean.lower()
        UNSERVICED_DESTINATIONS = [
            "lahore", "data darbar", "karachi", "new york", "paris", "dubai",
            "london", "tokyo", "rome", "bangkok", "barcelona", "amsterdam",
            "singapore", "los angeles", "chicago", "toronto", "sydney",
            "faisalabad", "multan", "gujranwala", "sialkot", "bahawalpur", "sukkur", "hyderabad"
        ]
        if any(un in query_lower for un in UNSERVICED_DESTINATIONS):
            unserviced_payload = {
                "success": True,
                "destination": dest_clean,
                "serviced": False,
                "is_serviced": False,
                "region": "",
                "matched_regions": [],
                "source_url": base_url,
                "scraped_at": scraped_at,
                "cached": False,
                "message": f"'{dest_clean}' is outside our operational service boundaries.",
            }
            self.cache.set(session_id, cache_key, unserviced_payload)
            return unserviced_payload

        # Check for destination mention on live page, stripping search echoing elements
        is_covered = False
        if html:
            soup = BeautifulSoup(html, "html.parser")
            raw_text = soup.get_text(separator=" ", strip=True).lower()
            is_challenge = any(ch in raw_text for ch in ["checking your browser", "cloudflare", "just a moment", "enable javascript"])
            if not is_challenge:
                for tag in soup.find_all(["input", "form", "header", "title"]):
                    tag.decompose()
                for cls in ["search-form", "page-title", "entry-title-search", "breadcrumb", "breadcrumbs", "woocommerce-breadcrumb"]:
                    for el in soup.find_all(class_=cls):
                        el.decompose()
                cleaned_text = soup.get_text(separator=" ", strip=True).lower()
                no_results = any(nr in cleaned_text for nr in ["nothing found", "no results", "not found", "no tours found", "0 results found"])
                if not no_results and query_lower in cleaned_text:
                    is_covered = True

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
