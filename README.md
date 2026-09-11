# Internship Radar

A daily-refreshing internship tracker for CSE internships in Bengaluru,
Hyderabad, Pune, Chennai, Gurgaon, Noida (+ remote). Scrapes Internshala,
watches startup career pages you add, stores everything, tracks what
you've applied to, and shows it all on one dashboard page.

## What this does NOT do (read this first)

This does **not** auto-submit applications for you. Real "apply for me"
bots break constantly (CAPTCHAs, logins, ATS portals that change weekly)
and most platforms' terms of service prohibit automated applications —
using one risks getting your account flagged. What it does instead:
finds everything relevant, remembers it, tells you what's new and what's
urgent, and tracks your progress — so the manual step (clicking apply,
tailoring your resume) is the only thing left for you to do, on the
listings that actually matter.

## What it does

- **Scrapes Internshala** daily for CS internships in your target cities
  + work-from-home.
- **Watches startup career pages** you list in `config/watchlist.json` —
  since most startups don't post to Internshala, this flags when a page
  starts mentioning "intern" or changes.
- **Stores every listing** in `data/internships.json`, forever — nothing
  gets lost even after the internship's own page disappears.
- **Tracks your applications** (`data/applications.json`) — status +
  notes + timestamped history per internship.
- **Builds a dashboard** (`docs/index.html`) — sortable/filterable,
  highlights new-today listings and deadlines within 3 days.
- **Runs itself** via GitHub Actions, daily, for free, even if your
  laptop is off.

## Setup (10 minutes)

1. **Create a GitHub repo** and push this folder to it:
   ```bash
   cd internship-tracker
   git add -A
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/<you>/internship-tracker.git
   git push -u origin main
   ```

2. **Enable GitHub Pages** so you get a browseable URL for the dashboard:
   Repo Settings → Pages → Source: "Deploy from a branch" → Branch:
   `main`, folder `/docs` → Save. You'll get a URL like
   `https://<you>.github.io/internship-tracker/`.

3. **Enable Actions** (usually on by default for a new repo): Settings →
   Actions → General → allow workflows to run.

4. **Give Actions push permission**: Settings → Actions → General →
   "Workflow permissions" → select "Read and write permissions". This is
   what lets the daily job commit new data back to your repo.

5. **Trigger the first run manually**: Actions tab → "Daily internship
   scrape" → "Run workflow". Don't wait for 8:30am tomorrow to see if it
   works.

6. **Check the run's logs.** If Internshala changed their HTML since
   this was written, you'll see `Parsed 0 relevant internships` warnings.
   See "Fixing a broken scraper" below — it's a 10-minute fix, not a
   rebuild.

## Using the tracker day-to-day

Pull the latest data locally (`git pull`), then:

```bash
python track.py list                       # everything, soonest deadline first
python track.py list --status not_applied   # what you haven't touched yet
python track.py search razorpay             # find something by name
python track.py show <id>                   # full detail + history
python track.py apply <id> -n "used referral from senior"
python track.py status <id> interview -n "OA cleared, interview Mon"
git add data/ && git commit -m "Applied to a few" && git push
```

Or just open `docs/index.html` (or your GitHub Pages URL) and read —
the dashboard is view-only; status changes happen through `track.py` so
there's a clean history in git of what you did and when.

## Adding startups to watch

Edit `config/watchlist.json`:
```json
{ "companies": [
  { "name": "YourFavoriteStartup", "careers_url": "https://example.com/careers" }
]}
```
Add as many as you want. The scraper doesn't parse structured details
from these (every company site is laid out differently) — it flags the
page as worth a manual look when it mentions "intern" or changes.

## Tuning what counts as relevant

Edit `config/settings.py`:
- `TARGET_CITIES` — add/remove cities (Internshala's own slug names).
- `KEYWORD_EXCLUDE` — e.g. keeps unpaid internships out by default.
- `MIN_STIPEND` — filter by minimum stipend.
- `INTERNSHALA_CATEGORIES` — add `"data-science"`,
  `"android-app-development"`, etc. for a wider net.

## Fixing a broken scraper

Scrapers break when a site changes its HTML — this isn't a bug in the
design, it's just what scraping is. When it happens:

```bash
python -m scrapers.internshala --debug-dump
```
This saves the raw HTML Internshala actually returned into
`data/debug/`. Open it, find the internship cards, and update the CSS
selectors in `scrapers/internshala.py` → `parse_listing_card()` and the
`cards = soup.select(...)` line in `scrape()`. Paste the relevant HTML
snippet to Claude if you want help fixing the selector.

## Extending to more sources

`scrapers/` is one file per source with a `scrape()` function returning
a list of dicts with the same shape (see `internshala.py` for the
field list). To add a new source, write a new file the same way and
register it in `run_all.py`'s `main()`. Good next candidates: Cutshort,
LinkedIn's own job-alert emails (parse the email instead of scraping the
site — much more reliable and ToS-safe), Naukri.

## Why JSON files instead of a real database

At the scale of "internships for one person," a database is overkill.
JSON files mean `git log data/internships.json` is a free audit trail
of every internship ever seen, and `git log data/applications.json` is
a free audit trail of every status change you've made — no separate
backup strategy needed.
