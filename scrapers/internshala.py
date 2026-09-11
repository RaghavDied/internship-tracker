"""
Internshala scraper.

Selectors below were fixed against REAL live HTML pulled by a user (this
sandbox can't reach internshala.com itself). If Internshala changes their
markup again in future:
  1. Check the Action's log for "parsed 0 internships" warnings.
  2. Run `python inspect_card.py` after `python -m scrapers.internshala --debug-dump`
     to see one real card's HTML, and adjust `parse_listing_card()` below.

Known quirk: the search-results cards do NOT carry a labelled deadline
field. Internshala only surfaces "apply by <date>" as free text inside a
listing's own detail page. So deadlines are fetched via a second request,
per NEW listing only (see fetch_deadline_from_detail below), capped by
MAX_DETAIL_FETCHES_PER_RUN so a big backlog doesn't blow up run time.
"""
import argparse
import logging
import os
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from config.settings import (
    TARGET_CITIES, INCLUDE_WORK_FROM_HOME, INTERNSHALA_CATEGORIES, BASE_DIR,
    FETCH_DEADLINE_DETAIL, MAX_DETAIL_FETCHES_PER_RUN,
)
from scrapers.base import polite_get, extract_stipend_number, passes_filters
from storage import make_id, load_internships

logger = logging.getLogger("scraper.internshala")

SOURCE_NAME = "internshala"
ROOT = "https://internshala.com"

# Stage 1: find the neighbourhood of text right after an "apply by" style
# phrase (wide window - trailing words like "for this role" are common).
DEADLINE_CONTEXT_PATTERNS = [
    re.compile(r"apply\s+by\s+(.{3,40})", re.IGNORECASE),
    re.compile(r"last\s+date\s+to\s+apply\s*[:\-]?\s*(.{3,40})", re.IGNORECASE),
]
# Stage 2: pull just the date token out of that window, either ordering
# ('28 Aug 2026' / '28th Aug' or 'August 28' / 'Aug 28, 2026').
DATE_TOKEN_PATTERN = re.compile(
    r"(\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+(?:['\s]*\d{2,4})?"
    r"|[A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s*\d{2,4})?)"
)

DEADLINE_PATTERNS = DEADLINE_CONTEXT_PATTERNS  # kept for import compatibility


def build_search_urls():
    """One combined-city URL per category, plus a work-from-home variant."""
    urls = []
    city_slug = ",".join(TARGET_CITIES)
    for cat in INTERNSHALA_CATEGORIES:
        urls.append(f"{ROOT}/internships/{cat}-internship-in-{city_slug}/")
        if INCLUDE_WORK_FROM_HOME:
            urls.append(f"{ROOT}/internships/{cat}-internship-work-from-home/")
    return urls


def _text(el):
    return el.get_text(strip=True) if el else ""


def _shorten_location(raw: str, max_cities: int = 2) -> str:
    """'Chennai, Coimbatore, Erode, ... (Hybrid)' -> 'Chennai, Coimbatore +13 more (Hybrid)'"""
    if not raw:
        return "Not specified"
    suffix = ""
    for tag in ("(Hybrid)", "(Remote)", "(Work From Home)"):
        if tag in raw:
            suffix = f" {tag}"
            raw = raw.replace(tag, "")
            break
    cities = [c.strip() for c in raw.split(",") if c.strip()]
    if len(cities) <= max_cities:
        return ", ".join(cities) + suffix
    shown = ", ".join(cities[:max_cities])
    return f"{shown} +{len(cities) - max_cities} more{suffix}"


def parse_listing_card(card) -> dict | None:
    """Pull fields out of one internship card. Returns None if the card
    doesn't look like a real listing."""
    try:
        title_el = card.select_one("a.job-title-href, h2.job-internship-name a")
        if not title_el:
            return None
        title = _text(title_el)
        if not title:
            return None

        link = title_el.get("href", "")
        link = urljoin(ROOT, link) if link else ""

        # Company name specifically - NOT the wrapping div, which also
        # contains the "Actively hiring" badge with no separating space.
        company_el = card.select_one("p.company-name")
        company = _text(company_el) or "Unknown"

        location_el = card.select_one(".row-1-item.locations, .locations")
        location_raw = _text(location_el)
        location = _shorten_location(location_raw)

        stipend_el = card.select_one("span.stipend")
        stipend_text = _text(stipend_el) or "Not specified"

        # Duration has no dedicated class - it's the span sibling of the
        # calendar icon. Fall back to a plain .duration class in case
        # Internshala uses it on some page variants.
        duration_el = (card.select_one("i.ic-16-calendar ~ span")
                        or card.select_one(".duration"))
        duration = _text(duration_el) or "Not specified"

        posted_el = card.select_one(".status-info span, .posted_by_container")
        posted = _text(posted_el)

        desc_el = card.select_one(".about_job .text")
        description = _text(desc_el)

        return {
            "title": title,
            "company": company,
            "location": location,
            "stipend_text": stipend_text,
            "stipend_amount": extract_stipend_number(stipend_text),
            "duration": duration,
            "apply_by": "",  # filled in later for new listings only, see scrape()
            "posted": posted,
            "link": link,
            "description": description,
            "source": SOURCE_NAME,
        }
    except Exception as e:
        logger.warning("Failed to parse a card: %s", e)
        return None


def fetch_deadline_from_detail(link: str, debug_dump=False) -> str:
    """Fetch a listing's own page and search its text for an 'apply by'
    style phrase. Returns '' if nothing matched - the dashboard will show
    'Unknown' rather than a wrong guess."""
    resp = polite_get(link)
    if resp is None:
        return ""

    if debug_dump:
        os.makedirs(os.path.join(BASE_DIR, "data", "debug"), exist_ok=True)
        fname = "detail_sample_" + re.sub(r"[^a-zA-Z0-9]+", "_", link)[-80:] + ".html"
        with open(os.path.join(BASE_DIR, "data", "debug", fname), "w", encoding="utf-8") as f:
            f.write(resp.text)

    text = BeautifulSoup(resp.text, "html.parser").get_text(separator="\n")
    for pattern in DEADLINE_CONTEXT_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        window = m.group(1)
        date_match = DATE_TOKEN_PATTERN.search(window)
        if date_match:
            return date_match.group(1).strip()
    return ""


def scrape(debug_dump=False, max_pages_per_url=5) -> list:
    results = []
    os.makedirs(os.path.join(BASE_DIR, "data", "debug"), exist_ok=True)

    for base_url in build_search_urls():
        for page in range(1, max_pages_per_url + 1):
            url = base_url if page == 1 else urljoin(base_url, f"page-{page}/")
            resp = polite_get(url)
            if resp is None:
                break

            if debug_dump:
                fname = re.sub(r"[^a-zA-Z0-9]+", "_", url)[:120] + ".html"
                with open(os.path.join(BASE_DIR, "data", "debug", fname), "w", encoding="utf-8") as f:
                    f.write(resp.text)

            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.select("[id^=individual_internship]")

            if not cards:
                logger.info("No cards found on %s (page %d) - stopping pagination for this URL", url, page)
                break

            page_count = 0
            for card in cards:
                parsed = parse_listing_card(card)
                if not parsed:
                    continue
                if not passes_filters(parsed["title"], parsed["description"], parsed["stipend_amount"]):
                    continue
                parsed["id"] = make_id(parsed["link"], parsed["title"], parsed["company"])
                results.append(parsed)
                page_count += 1

            logger.info("Parsed %d relevant internships from %s (page %d)", page_count, base_url, page)

            if page_count == 0:
                break  # likely ran out of pages

    logger.info("Internshala listing scrape complete: %d listings collected", len(results))

    if FETCH_DEADLINE_DETAIL and results:
        existing_ids = set(load_internships().keys())
        new_results = [r for r in results if r["id"] not in existing_ids]
        to_fetch = new_results[:MAX_DETAIL_FETCHES_PER_RUN]
        logger.info("Fetching deadlines for %d/%d new listings (capped at %d)",
                     len(to_fetch), len(new_results), MAX_DETAIL_FETCHES_PER_RUN)
        for i, r in enumerate(to_fetch):
            r["apply_by"] = fetch_deadline_from_detail(r["link"], debug_dump=(debug_dump and i == 0))
        if len(new_results) > MAX_DETAIL_FETCHES_PER_RUN:
            logger.info("%d new listings left without a fetched deadline this run - "
                         "they'll be picked up automatically over the next few days "
                         "as MAX_DETAIL_FETCHES_PER_RUN allows.",
                         len(new_results) - MAX_DETAIL_FETCHES_PER_RUN)

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug-dump", action="store_true",
                         help="Save raw HTML of each fetched page to data/debug/ for selector debugging")
    args = parser.parse_args()
    listings = scrape(debug_dump=args.debug_dump)
    print(f"Collected {len(listings)} listings")
    for l in listings[:8]:
        print(" -", l["title"], "@", l["company"], "|", l["location"], "|",
              l["stipend_text"], "|", l["duration"], "| apply by:", l["apply_by"] or "(not found)")
