"""
Simple JSON-file storage. Deliberately not a real database:
- Git-diffable, so `git log` on data/internships.json IS your history of
  every internship ever seen, and data/applications.json IS your history
  of every status change (with timestamps).
- No binary blobs to worry about in the repo.
- Trivial to inspect/edit by hand if something looks wrong.
"""
import json
import os
import hashlib
from datetime import datetime, timezone

from config.settings import INTERNSHIPS_FILE, APPLICATIONS_FILE, DATA_DIR


def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def make_id(link: str, title: str = "", company: str = "") -> str:
    """Stable ID for a listing. Prefer the apply link (most unique);
    fall back to title+company if a source doesn't give a clean link."""
    basis = link.strip().lower() if link else f"{title}|{company}".strip().lower()
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_internships() -> dict:
    """Returns {id: record} dict."""
    _ensure_data_dir()
    if not os.path.exists(INTERNSHIPS_FILE):
        return {}
    with open(INTERNSHIPS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_internships(records: dict):
    _ensure_data_dir()
    with open(INTERNSHIPS_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False, sort_keys=True)


def upsert_internships(new_listings: list) -> dict:
    """
    Merge freshly scraped listings into the store.
    - New listing -> added with first_seen_at = now.
    - Existing listing -> fields refreshed (stipend/deadline can change)
      but first_seen_at is preserved so "new today" stays accurate.
    Returns stats: {"new": n, "updated": n, "total": n}
    """
    existing = load_internships()
    new_count = 0
    updated_count = 0
    ts = now_iso()

    for listing in new_listings:
        rid = listing["id"]
        if rid in existing:
            preserved_first_seen = existing[rid].get("first_seen_at", ts)
            existing[rid].update(listing)
            existing[rid]["first_seen_at"] = preserved_first_seen
            existing[rid]["last_seen_at"] = ts
            updated_count += 1
        else:
            listing["first_seen_at"] = ts
            listing["last_seen_at"] = ts
            existing[rid] = listing
            new_count += 1

    save_internships(existing)
    return {"new": new_count, "updated": updated_count, "total": len(existing)}


def load_applications() -> dict:
    """Returns {internship_id: {status, notes, history: [...]}}"""
    _ensure_data_dir()
    if not os.path.exists(APPLICATIONS_FILE):
        return {}
    with open(APPLICATIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_applications(records: dict):
    _ensure_data_dir()
    with open(APPLICATIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False, sort_keys=True)


VALID_STATUSES = [
    "not_applied", "applied", "online_test", "interview",
    "offer", "rejected", "withdrawn",
]


def set_status(internship_id: str, status: str, note: str = ""):
    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {VALID_STATUSES}, got {status!r}")
    apps = load_applications()
    ts = now_iso()
    record = apps.get(internship_id, {"status": "not_applied", "history": []})
    record["status"] = status
    record["updated_at"] = ts
    record["history"].append({"status": status, "note": note, "at": ts})
    if note:
        record["latest_note"] = note
    apps[internship_id] = record
    save_applications(apps)
    return record
