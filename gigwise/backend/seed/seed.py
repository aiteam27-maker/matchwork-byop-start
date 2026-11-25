"""Load the Gigwise demo data into Supabase.

Run from gigwise/backend (after running sql/schema.sql in Supabase):
    .venv/bin/python -m seed.seed

It deletes existing Gigwise data first, so you can re-run it any time to reset the demo.
"""
from __future__ import annotations

import sys

from app.db import NotConfigured, get_client
from seed.seed_data import build_rows

# Child tables first, so foreign keys don't block deletes.
DELETE_ORDER = ["match_events", "notifications", "saved_freelancers", "saved_jobs", "reviews", "milestones",
                "contracts", "offers", "messages", "threads", "proposals", "projects", "freelancers", "clients"]
# Tables keyed by an auto-number instead of a text id.
NUMERIC_ID = {"match_events", "notifications", "reviews", "milestones", "messages"}
COMPOSITE_KEY = {"saved_jobs": "freelancer_id", "saved_freelancers": "client_id"}


def main() -> int:
    try:
        sb = get_client()
    except NotConfigured as e:
        print(f"Can't connect: {e}")
        return 1

    print("Clearing existing Gigwise data...")
    for table in DELETE_ORDER:
        q = sb.table(table).delete()
        if table in NUMERIC_ID:
            q = q.gte("id", 0)
        elif table in COMPOSITE_KEY:
            q = q.neq(COMPOSITE_KEY[table], "")
        else:
            q = q.neq("id", "")
        q.execute()

    data = build_rows()
    for table, rows in data.items():
        if rows:
            # default_to_null=False: fields a row leaves out get the column's default, not NULL
            sb.table(table).insert(rows, default_to_null=False).execute()
        print(f"  {table:<14} {len(rows)} rows")
    print("Done. Demo data loaded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
