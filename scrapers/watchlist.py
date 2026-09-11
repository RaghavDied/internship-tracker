"""
Watchlist scraper: for startups/companies that don't post to Internshala,
add their careers page to config/watchlist.json. This scraper can't parse
structured fields (every company site is different), so it does something
simpler and more robust: it fetches the page, looks for internship-related
keywords, and flags it as a "possible opening" for you to go check by hand.

It also diffs against the previous snapshot's text so you only get pinged
when something actually changed, not every single day for a static page.
"""
import hashlib
import json
import logging
import os
import re

from bs4 import BeautifulSoup

from config.settings import WATCHLIST_FILE, BASE_DIR
from scrapers.base import polite_get
from storage import make_id

logger = logging.getLogger("scraper.watchlist")

SOURCE_NAME = "watchlist"
SNAPSHOT_FILE = os.path.join(BASE_DIR, "data", "watchlist_snapshots.json")

INTERN_KEYWORDS = re.compile(r"\bintern(ship)?s?\b", re.IGNORECASE)


def _load_watchlist():
    if not os.path.exists(WATCHLIST_FILE):
        return []
    with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("companies", [])


def _load_snapshots():
    if not os.path.exists(SNAPSHOT_FILE):
        return {}
    with open(SNAPSHOT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_snapshots(snapshots):
    os.makedirs(os.path.dirname(SNAPSHOT_FILE), exist_ok=True)
    with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
        json.dump(snapshots, f, indent=2)


def _page_signature(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def scrape() -> list:
    companies = _load_watchlist()
    if not companies:
        logger.info("Watchlist is empty - add companies to config/watchlist.json")
        return []

    snapshots = _load_snapshots()
    results = []

    for entry in companies:
        name = entry.get("name", "Unknown company")
        url = entry.get("careers_url")
        if not url:
            continue

        resp = polite_get(url)
        if resp is None:
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        page_text = soup.get_text(separator=" ", strip=True)
        mentions_intern = bool(INTERN_KEYWORDS.search(page_text))
        sig = _page_signature(page_text)

        prev_sig = snapshots.get(url, {}).get("signature")
        changed = sig != prev_sig
        snapshots[url] = {"signature": sig}

        if mentions_intern:
            # Grab a short snippet around the first mention for context
            match = INTERN_KEYWORDS.search(page_text)
            start = max(0, match.start() - 80)
            end = min(len(page_text), match.end() + 80)
            snippet = page_text[start:end]

            results.append({
                "id": make_id(url + ("#changed" if changed else ""), name, "watchlist"),
                "title": f"Possible internship opening at {name}" + (" (page changed)" if changed else ""),
                "company": name,
                "location": "Check page",
                "stipend_text": "Unknown - check page",
                "stipend_amount": 0,
                "duration": "Unknown",
                "apply_by": "Unknown",
                "posted": "",
                "link": url,
                "description": snippet,
                "source": SOURCE_NAME,
            })

    _save_snapshots(snapshots)
    logger.info("Watchlist scrape complete: %d flagged pages out of %d watched", len(results), len(companies))
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    listings = scrape()
    print(f"Flagged {len(listings)} watchlist pages")
    for l in listings:
        print(" -", l["title"], "|", l["link"])
