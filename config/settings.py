"""
Central configuration. Edit this file to tune what counts as a relevant
internship for you — no need to touch scraper code for these changes.
"""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DOCS_DIR = os.path.join(BASE_DIR, "docs")

INTERNSHIPS_FILE = os.path.join(DATA_DIR, "internships.json")
APPLICATIONS_FILE = os.path.join(DATA_DIR, "applications.json")
WATCHLIST_FILE = os.path.join(BASE_DIR, "config", "watchlist.json")

# Cities you're targeting (used to build Internshala search URLs and to
# score/filter results). Internshala's own slug format is lowercase,
# hyphenated, comma-joined.
TARGET_CITIES = [
    "bangalore",   # Internshala's slug for Bengaluru
    "hyderabad",
    "pune",
    "chennai",
    "gurgaon",
    "noida",
]

# Also fetch remote / work-from-home CS internships — huge chunk of
# startup postings are WFH and shouldn't be filtered out.
INCLUDE_WORK_FROM_HOME = True

# Internshala category slugs to pull. computer-science covers most SWE/dev
# roles; add more (e.g. "data-science", "android-app-development") if you
# want a wider net.
INTERNSHALA_CATEGORIES = [
    "computer-science",
]

# Keywords that must appear (case-insensitive) in title/description for a
# listing to be kept. Empty list = keep everything in the category.
KEYWORD_INCLUDE = []

# Keywords that auto-reject a listing even if it matched a category.
KEYWORD_EXCLUDE = [
    "unpaid",  # flip this off if you're fine with unpaid internships
]

# Minimum stipend in INR/month to keep (0 = don't filter by stipend).
# Internships explicitly marked "Unpaid" are handled by KEYWORD_EXCLUDE above.
MIN_STIPEND = 0

# How many days out counts as "deadline approaching" (red badge in dashboard)
DEADLINE_WARNING_DAYS = 3

# Standard headers so we look like a real browser, not a bot.
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

REQUEST_TIMEOUT = 20  # seconds
REQUEST_DELAY = 1.5   # seconds between requests, be polite to the site
