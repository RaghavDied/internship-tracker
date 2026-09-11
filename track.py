"""
Application tracker CLI.

Examples:
  python track.py list                          # everything, newest deadline first
  python track.py list --status not_applied      # only ones you haven't applied to
  python track.py search razorpay                # find an internship by keyword
  python track.py show ab12cd34ef                # full details for one id
  python track.py apply ab12cd34ef -n "used referral from senior"
  python track.py status ab12cd34ef interview -n "OA cleared, interview on Mon"
"""
import argparse
import textwrap

from storage import load_internships, load_applications, set_status, VALID_STATUSES


def cmd_list(args):
    internships = load_internships()
    applications = load_applications()

    rows = []
    for iid, rec in internships.items():
        status = applications.get(iid, {}).get("status", "not_applied")
        if args.status and status != args.status:
            continue
        rows.append((iid, rec, status))

    rows.sort(key=lambda r: r[1].get("apply_by") or "9999")

    if not rows:
        print("No matching internships.")
        return

    for iid, rec, status in rows:
        print(f"[{iid}] {rec['title']} @ {rec['company']}")
        print(f"    {rec.get('location','?')} | {rec.get('stipend_text','?')} | "
              f"apply by {rec.get('apply_by','?')} | status: {status} | source: {rec.get('source','?')}")


def cmd_search(args):
    internships = load_internships()
    q = args.query.lower()
    hits = [(iid, r) for iid, r in internships.items()
            if q in r.get("title", "").lower() or q in r.get("company", "").lower()]
    if not hits:
        print("No matches.")
        return
    for iid, r in hits:
        print(f"[{iid}] {r['title']} @ {r['company']} | {r.get('link','')}")


def cmd_show(args):
    internships = load_internships()
    applications = load_applications()
    rec = internships.get(args.id)
    if not rec:
        print(f"No internship with id {args.id}")
        return
    for k, v in rec.items():
        print(f"{k}: {textwrap.shorten(str(v), 200)}")
    app = applications.get(args.id)
    if app:
        print("--- application history ---")
        for h in app.get("history", []):
            print(f"{h['at']}: {h['status']}" + (f" - {h['note']}" if h.get("note") else ""))


def cmd_apply(args):
    rec = set_status(args.id, "applied", note=args.note or "")
    print(f"Marked {args.id} as applied. History entries: {len(rec['history'])}")


def cmd_status(args):
    rec = set_status(args.id, args.new_status, note=args.note or "")
    print(f"Updated {args.id} -> {args.new_status}")


def main():
    parser = argparse.ArgumentParser(description="Internship application tracker")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="List internships")
    p_list.add_argument("--status", choices=VALID_STATUSES)
    p_list.set_defaults(func=cmd_list)

    p_search = sub.add_parser("search", help="Search by title/company keyword")
    p_search.add_argument("query")
    p_search.set_defaults(func=cmd_search)

    p_show = sub.add_parser("show", help="Show full details + history for one id")
    p_show.add_argument("id")
    p_show.set_defaults(func=cmd_show)

    p_apply = sub.add_parser("apply", help="Mark an internship as applied")
    p_apply.add_argument("id")
    p_apply.add_argument("-n", "--note", default="")
    p_apply.set_defaults(func=cmd_apply)

    p_status = sub.add_parser("status", help="Set an arbitrary status")
    p_status.add_argument("id")
    p_status.add_argument("new_status", choices=VALID_STATUSES)
    p_status.add_argument("-n", "--note", default="")
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
