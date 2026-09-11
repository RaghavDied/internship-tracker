import time
import logging
import requests

from config.settings import (
    REQUEST_HEADERS, REQUEST_TIMEOUT, REQUEST_DELAY,
    KEYWORD_INCLUDE, KEYWORD_EXCLUDE, MIN_STIPEND,
)

logger = logging.getLogger("scraper")


def polite_get(url, session=None, retries=3):
    """GET a URL with a browser-like header, retrying on transient failure."""
    sess = session or requests
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            resp = sess.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                time.sleep(REQUEST_DELAY)
                return resp
            logger.warning("GET %s -> HTTP %s (attempt %d/%d)", url, resp.status_code, attempt, retries)
            last_err = f"HTTP {resp.status_code}"
        except requests.RequestException as e:
            logger.warning("GET %s failed (attempt %d/%d): %s", url, attempt, retries, e)
            last_err = str(e)
        time.sleep(REQUEST_DELAY * attempt)  # back off
    logger.error("Giving up on %s: %s", url, last_err)
    return None


def extract_stipend_number(stipend_text: str) -> int:
    """'₹ 10,000-15,000 /month' -> 10000 (take the lower bound). Unpaid/Negotiable -> 0."""
    if not stipend_text:
        return 0
    digits = ""
    numbers = []
    for ch in stipend_text:
        if ch.isdigit():
            digits += ch
        elif digits:
            numbers.append(int(digits))
            digits = ""
    if digits:
        numbers.append(int(digits))
    return numbers[0] if numbers else 0


def passes_filters(title: str, description: str, stipend_amount: int) -> bool:
    text = f"{title} {description}".lower()

    if KEYWORD_INCLUDE and not any(kw.lower() in text for kw in KEYWORD_INCLUDE):
        return False

    if any(kw.lower() in text for kw in KEYWORD_EXCLUDE):
        return False

    if MIN_STIPEND and stipend_amount and stipend_amount < MIN_STIPEND:
        return False

    return True
