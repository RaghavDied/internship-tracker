"""
Runs every scraper and merges results into data/internships.json.
This is the single entry point GitHub Actions (and you, locally) calls daily.
"""
import logging
import sys

from scrapers import internshala, watchlist
from storage import upsert_internships

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("run_all")


def main():
    all_listings = []
    failures = []

    for name, fn in [("internshala", internshala.scrape), ("watchlist", watchlist.scrape)]:
        try:
            listings = fn()
            all_listings.extend(listings)
        except Exception as e:
            logger.exception("Scraper %s crashed", name)
            failures.append(name)

    if not all_listings:
        logger.warning("No listings collected this run. Nothing to merge.")
    else:
        stats = upsert_internships(all_listings)
        logger.info("Merge complete: %d new, %d updated, %d total in store",
                     stats["new"], stats["updated"], stats["total"])

    if failures:
        logger.error("These scrapers failed and were skipped: %s", ", ".join(failures))
        # Don't hard-fail the whole run over one broken scraper - partial
        # data beats no data. But exit non-zero so Actions shows a warning.
        sys.exit(1)


if __name__ == "__main__":
    main()
