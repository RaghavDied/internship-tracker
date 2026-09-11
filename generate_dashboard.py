"""
Builds docs/index.html - a single self-contained static page (no server,
no build step) from data/internships.json + data/applications.json.
GitHub Pages serves /docs on the main branch directly, so once that's
enabled you just get a URL that's fresh every morning.
"""
import json
import os
import re
from datetime import datetime, timezone, date, timedelta

from dateutil import parser as dateutil_parser

from config.settings import DOCS_DIR, DEADLINE_WARNING_DAYS
from storage import load_internships, load_applications

STATUS_LABELS = {
    "not_applied": "Not applied",
    "applied": "Applied",
    "online_test": "Online test",
    "interview": "Interview",
    "offer": "Offer",
    "rejected": "Rejected",
    "withdrawn": "Withdrawn",
}

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Internship Radar</title>
<style>
  :root {
    --bg: #0E1A2B;
    --bg-panel: #142338;
    --bg-row: #17293F;
    --hairline: #28425F;
    --text: #E7EEF6;
    --text-dim: #8CA3BC;
    --amber: #F2B705;
    --teal: #4FBDA6;
    --red: #E2604F;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: 'Iowan Old Style', 'Georgia', serif;
    line-height: 1.45;
  }
  .mono { font-family: 'IBM Plex Mono', 'SFMono-Regular', Menlo, monospace; }
  header {
    padding: 40px 32px 28px;
    border-bottom: 1px solid var(--hairline);
  }
  header h1 {
    margin: 0 0 6px;
    font-size: 34px;
    font-weight: 500;
    letter-spacing: 0.2px;
  }
  header .sub {
    color: var(--text-dim);
    font-size: 15px;
    max-width: 640px;
  }
  .stat-row {
    display: flex;
    gap: 28px;
    margin-top: 22px;
    flex-wrap: wrap;
  }
  .stat { }
  .stat .num {
    font-family: 'IBM Plex Mono', Menlo, monospace;
    font-size: 26px;
    color: var(--amber);
  }
  .stat .label {
    color: var(--text-dim);
    font-size: 13px;
  }
  .controls {
    display: flex;
    gap: 10px;
    padding: 18px 32px;
    flex-wrap: wrap;
    border-bottom: 1px solid var(--hairline);
    background: var(--bg-panel);
  }
  .controls select, .controls input {
    background: var(--bg-row);
    color: var(--text);
    border: 1px solid var(--hairline);
    padding: 8px 12px;
    border-radius: 3px;
    font-family: inherit;
    font-size: 14px;
  }
  main { padding: 24px 32px 60px; }
  .board { border-top: 1px solid var(--hairline); }
  .row {
    display: grid;
    grid-template-columns: 2.2fr 1fr 1fr 1fr 1fr;
    gap: 16px;
    padding: 16px 14px;
    border-bottom: 1px solid var(--hairline);
    align-items: center;
    transition: background 0.15s ease;
  }
  .row:hover { background: var(--bg-row); }
  .row.header-row {
    font-family: 'IBM Plex Mono', Menlo, monospace;
    font-size: 11px;
    color: var(--text-dim);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding-top: 10px;
    padding-bottom: 10px;
  }
  .row .title { font-size: 16px; }
  .row .company { color: var(--text-dim); font-size: 14px; margin-top: 2px; }
  .badge-new {
    display: inline-block;
    margin-left: 8px;
    font-family: 'IBM Plex Mono', Menlo, monospace;
    font-size: 10px;
    color: var(--bg);
    background: var(--teal);
    padding: 2px 6px;
    border-radius: 2px;
    vertical-align: middle;
  }
  .deadline { font-family: 'IBM Plex Mono', Menlo, monospace; font-size: 14px; }
  .deadline.urgent { color: var(--amber); }
  .deadline.expired { color: var(--red); }
  .status-pill {
    font-family: 'IBM Plex Mono', Menlo, monospace;
    font-size: 12px;
    padding: 3px 8px;
    border-radius: 3px;
    border: 1px solid var(--hairline);
    display: inline-block;
  }
  .status-applied, .status-online_test, .status-interview { color: var(--teal); border-color: var(--teal); }
  .status-offer { color: var(--amber); border-color: var(--amber); }
  .status-rejected, .status-withdrawn { color: var(--text-dim); }
  a.apply-link {
    color: var(--teal);
    text-decoration: none;
    font-size: 13px;
    font-family: 'IBM Plex Mono', Menlo, monospace;
  }
  a.apply-link:hover { text-decoration: underline; }
  .empty-state {
    padding: 60px 20px;
    text-align: center;
    color: var(--text-dim);
  }
  .section-label {
    font-family: 'IBM Plex Mono', Menlo, monospace;
    font-size: 12px;
    color: var(--text-dim);
    letter-spacing: 0.05em;
    margin: 36px 0 8px;
  }
  footer {
    padding: 20px 32px 40px;
    color: var(--text-dim);
    font-size: 12px;
    font-family: 'IBM Plex Mono', Menlo, monospace;
  }
  @media (max-width: 720px) {
    .row { grid-template-columns: 1fr 1fr; }
    .row .col-location, .row .col-source { display: none; }
  }
</style>
</head>
<body>
<header>
  <h1>Internship Radar</h1>
  <div class="sub">CSE internships in Bengaluru, Hyderabad, Pune, Chennai, Gurgaon, Noida (+ remote), refreshed daily. Startups and big companies both tracked.</div>
  <div class="stat-row">
    <div class="stat"><div class="num" id="stat-total">-</div><div class="label">tracked</div></div>
    <div class="stat"><div class="num" id="stat-new">-</div><div class="label">new today</div></div>
    <div class="stat"><div class="num" id="stat-urgent">-</div><div class="label">deadline &le; __WARN_DAYS__ days</div></div>
    <div class="stat"><div class="num" id="stat-applied">-</div><div class="label">applied</div></div>
  </div>
</header>

<div class="controls">
  <select id="f-status">
    <option value="">All statuses</option>
  </select>
  <select id="f-source">
    <option value="">All sources</option>
  </select>
  <input id="f-search" type="text" placeholder="Search title or company...">
  <select id="f-sort">
    <option value="deadline">Sort: deadline soonest</option>
    <option value="new">Sort: newest first</option>
    <option value="stipend">Sort: stipend highest</option>
  </select>
</div>

<main>
  <div class="board" id="board">
    <div class="row header-row">
      <div>Role / Company</div>
      <div class="col-location">Location</div>
      <div>Stipend</div>
      <div>Apply by</div>
      <div>Status</div>
    </div>
    <div id="rows"></div>
  </div>
</main>

<footer>
  last updated __GENERATED_AT__ &middot; data lives in data/internships.json, tracker in data/applications.json &middot; edit config/settings.py to change cities/keywords
</footer>

<script type="application/json" id="data-blob">__DATA_JSON__</script>
<script>
const DATA = JSON.parse(document.getElementById('data-blob').textContent);
const WARN_DAYS = __WARN_DAYS__;

function daysUntil(dateStr) {
  if (!dateStr) return null;
  const parsed = Date.parse(dateStr);
  if (isNaN(parsed)) return null;
  const diff = (parsed - Date.now()) / (1000 * 60 * 60 * 24);
  return Math.ceil(diff);
}

function render() {
  const statusFilter = document.getElementById('f-status').value;
  const sourceFilter = document.getElementById('f-source').value;
  const search = document.getElementById('f-search').value.toLowerCase();
  const sortBy = document.getElementById('f-sort').value;

  let items = DATA.filter(item => {
    if (statusFilter && item.status !== statusFilter) return false;
    if (sourceFilter && item.source !== sourceFilter) return false;
    if (search && !(item.title.toLowerCase().includes(search) || item.company.toLowerCase().includes(search))) return false;
    return true;
  });

  if (sortBy === 'deadline') {
    items.sort((a, b) => {
      const da = daysUntil(a.apply_by_iso), db = daysUntil(b.apply_by_iso);
      if (da === null) return 1;
      if (db === null) return -1;
      return da - db;
    });
  } else if (sortBy === 'new') {
    items.sort((a, b) => (b.first_seen_at || '').localeCompare(a.first_seen_at || ''));
  } else if (sortBy === 'stipend') {
    items.sort((a, b) => (b.stipend_amount || 0) - (a.stipend_amount || 0));
  }

  const rowsEl = document.getElementById('rows');
  rowsEl.innerHTML = '';

  if (items.length === 0) {
    rowsEl.innerHTML = '<div class="empty-state">Nothing matches these filters. Widen the search, or wait for tomorrow\\'s run.</div>';
  }

  for (const item of items) {
    const row = document.createElement('div');
    row.className = 'row';
    const days = daysUntil(item.apply_by_iso);
    let deadlineClass = '';
    if (days !== null) {
      if (days < 0) deadlineClass = 'expired';
      else if (days <= WARN_DAYS) deadlineClass = 'urgent';
    }
    const newBadge = item.is_new_today ? '<span class="badge-new">NEW</span>' : '';
    row.innerHTML = `
      <div>
        <div class="title">${item.title}${newBadge}</div>
        <div class="company">${item.company} &middot; <a class="apply-link" href="${item.link}" target="_blank" rel="noopener">${item.source}</a></div>
      </div>
      <div class="col-location">${item.location}</div>
      <div class="mono">${item.stipend_text}</div>
      <div class="deadline ${deadlineClass}">${item.apply_by || 'Unknown'}</div>
      <div><span class="status-pill status-${item.status}">${item.status_label}</span></div>
    `;
    rowsEl.appendChild(row);
  }
}

function populateFilterOptions() {
  const statuses = [...new Set(DATA.map(d => d.status))];
  const statusSel = document.getElementById('f-status');
  for (const s of statuses) {
    const opt = document.createElement('option');
    opt.value = s;
    opt.textContent = DATA.find(d => d.status === s).status_label;
    statusSel.appendChild(opt);
  }
  const sources = [...new Set(DATA.map(d => d.source))];
  const sourceSel = document.getElementById('f-source');
  for (const s of sources) {
    const opt = document.createElement('option');
    opt.value = s;
    opt.textContent = s;
    sourceSel.appendChild(opt);
  }
}

document.getElementById('f-status').addEventListener('change', render);
document.getElementById('f-source').addEventListener('change', render);
document.getElementById('f-search').addEventListener('input', render);
document.getElementById('f-sort').addEventListener('change', render);

document.getElementById('stat-total').textContent = DATA.length;
document.getElementById('stat-new').textContent = DATA.filter(d => d.is_new_today).length;
document.getElementById('stat-urgent').textContent = DATA.filter(d => {
  const days = daysUntil(d.apply_by_iso);
  return days !== null && days >= 0 && days <= WARN_DAYS;
}).length;
document.getElementById('stat-applied').textContent = DATA.filter(d => d.status !== 'not_applied').length;

populateFilterOptions();
render();
</script>
</body>
</html>
"""


def _parse_deadline_to_iso(apply_by_text: str):
    """Deadlines come from free text like 'August 28', '28 Aug', or
    '28 Aug 2026' - dateutil's fuzzy parser handles all of these. When no
    year is given it defaults to the current year; if that lands more
    than a month in the past (meaning it actually meant next year), we
    roll forward one year."""
    if not apply_by_text or apply_by_text.strip().lower() in ("unknown", "not specified", ""):
        return None
    cleaned = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", apply_by_text, flags=re.IGNORECASE)
    try:
        parsed = dateutil_parser.parse(cleaned, fuzzy=True, default=datetime(date.today().year, 1, 1))
    except (ValueError, OverflowError):
        return None
    parsed_date = parsed.date()
    if parsed_date < date.today() - timedelta(days=30):
        parsed_date = parsed_date.replace(year=parsed_date.year + 1)
    return parsed_date.isoformat()


def build():
    internships = load_internships()
    applications = load_applications()
    today = date.today().isoformat()

    items = []
    for iid, rec in internships.items():
        app = applications.get(iid, {})
        status = app.get("status", "not_applied")
        first_seen = (rec.get("first_seen_at") or "")[:10]
        items.append({
            "id": iid,
            "title": rec.get("title", "Untitled"),
            "company": rec.get("company", "Unknown"),
            "location": rec.get("location", "Not specified"),
            "stipend_text": rec.get("stipend_text", "Not specified"),
            "stipend_amount": rec.get("stipend_amount", 0),
            "apply_by": rec.get("apply_by", ""),
            "apply_by_iso": _parse_deadline_to_iso(rec.get("apply_by", "")),
            "link": rec.get("link", "#"),
            "source": rec.get("source", "unknown"),
            "status": status,
            "status_label": STATUS_LABELS.get(status, status),
            "first_seen_at": rec.get("first_seen_at", ""),
            "is_new_today": first_seen == today,
        })

    os.makedirs(DOCS_DIR, exist_ok=True)
    html = TEMPLATE.replace("__DATA_JSON__", json.dumps(items, ensure_ascii=False))
    html = html.replace("__GENERATED_AT__", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
    html = html.replace("__WARN_DAYS__", str(DEADLINE_WARNING_DAYS))

    out_path = os.path.join(DOCS_DIR, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Dashboard written to {out_path} ({len(items)} listings)")


if __name__ == "__main__":
    build()
