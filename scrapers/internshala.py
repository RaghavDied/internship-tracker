"""
Internshala scraper.

IMPORTANT - read this before your first real run:
Internshala's HTML markup can change without notice, and this code was
written without being able to load the live site from the build sandbox
(network-restricted environment). The selectors below are based on
Internshala's well-documented, long-standing card structure, but you
should verify on the FIRST real GitHub Actions run:
  1. Check the Action's log for "parsed 0 internships" warnings.
  2. If selectors are stale, run `python -m scrapers.internshala --debug-dump`
     locally/in Actions to save raw HTML into data/debug/, inspect it,
     and fix the CSS selectors in `parse_listing_card()` below.
This is normal maintenance for any scraper - sites change, scrapers get
one small patch. Budget 10 minutes for this the first time.
"""
import argparse
import logging
import os
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from config.settings import (
    TARGET_CITIES, INCLUDE_WORK_FROM_HOME, INTERNSHALA_CATEGORIES, BASE_DIR,
)
from scrapers.base import polite_get, extract_stipend_number, passes_filters
from storage import make_id

logger = logging.getLogger("scraper.internshala")

SOURCE_NAME = "internshala"
ROOT = "https://internshala.com"


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


def parse_listing_card(card) -> dict | None:
    """Pull fields out of one internship card. Returns None if the card
    doesn't look like a real listing (ads/promo cards slip in sometimes)."""
    try:
        title_el = card.select_one("a.job-title-href, .job-internship-name a, h3 a")
        company_el = card.select_one(".company-name, .company_name")
        location_el = card.select_one(".locations, .location_link, #location_names")
        stipend_el = card.select_one(".stipend, [id^=stipend_container]")
        duration_el = card.select_one(".duration")
        apply_by_el = card.select_one(".apply_by, [id^=apply_by]")
        posted_el = card.select_one(".status-success, .posted_by_container")

        title = _text(title_el)
        if not title:
            return None

        link = title_el.get("href", "") if title_el else ""
        link = urljoin(ROOT, link) if link else ""

        stipend_text = _text(stipend_el)

        return {
            "title": title,
            "company": _text(company_el) or "Unknown",
            "location": _text(location_el) or "Not specified",
            "stipend_text": stipend_text or "Not specified",
            "stipend_amount": extract_stipend_number(stipend_text),
            "duration": _text(duration_el) or "Not specified",
            "apply_by": _text(apply_by_el).replace("Apply by", "").strip(),
            "posted": _text(posted_el),
            "link": link,
            "description": "",  # detail page not fetched by default (keeps run fast/polite)
            "source": SOURCE_NAME,
        }
    except Exception as e:
        logger.warning("Failed to parse a card: %s", e)
        return None


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
            cards = soup.select("#internship_list_container_particular .individual_internship, "
                                 ".internship_list_container .individual_internship, "
                                 "[id^=individual_internship]")

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

    logger.info("Internshala scrape complete: %d listings collected", len(results))
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug-dump", action="store_true",
                         help="Save raw HTML of each fetched page to data/debug/ for selector debugging")
    args = parser.parse_args()
    listings = scrape(debug_dump=args.debug_dump)
    print(f"Collected {len(listings)} listings")
    for l in listings[:5]:
        print(" -", l["title"], "@", l["company"], "|", l["stipend_text"], "|", l["apply_by"])
