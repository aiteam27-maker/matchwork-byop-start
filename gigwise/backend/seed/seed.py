"""Load the Gigwise demo data into Supabase.

Run from gigwise/backend (after running sql/schema.sql in Supabase):
    .venv/bin/python -m seed.seed

It deletes the existing demo data first (never real accounts), so you can re-run it any time
to reset the demo. Run sql/002_login.sql once before using it.
"""
from __future__ import annotations

import sys

from app.db import NotConfigured, get_client
from seed.seed_data import build_rows

def _ids(sb, table, col, values, key="id"):
    if not values:
        return []
    return [r[key] for r in sb.table(table).select(key).in_(col, list(values)).execute().data or []]


def _delete_in(sb, table, col, values):
    values = list(values)
    for i in range(0, len(values), 200):  # keep each request short
        sb.table(table).delete().in_(col, values[i:i + 200]).execute()


def clear_demo(sb, log=print) -> None:
    """Delete only the investor-demo data (world = 'demo'). Real accounts and everything they
    created are never touched. Children go first, so foreign keys never block a delete."""
    world_ids = lambda t: [r["id"] for r in sb.table(t).select("id").eq("world", "demo").execute().data or []]
    clients, freelancers, projects = world_ids("clients"), world_ids("freelancers"), world_ids("projects")
    contracts = _ids(sb, "contracts", "project_id", projects)
    threads = _ids(sb, "threads", "project_id", projects)
    log(f"Clearing demo data: {len(clients)} clients, {len(freelancers)} freelancers, {len(projects)} projects...")
    _delete_in(sb, "notifications", "recipient_id", clients + freelancers)
    _delete_in(sb, "match_events", "project_id", projects)
    _delete_in(sb, "match_events", "freelancer_id", freelancers)
    _delete_in(sb, "saved_freelancers", "client_id", clients)
    _delete_in(sb, "saved_jobs", "freelancer_id", freelancers)
    _delete_in(sb, "reviews", "contract_id", contracts)
    _delete_in(sb, "milestones", "contract_id", contracts)
    _delete_in(sb, "contracts", "id", contracts)
    _delete_in(sb, "offers", "project_id", projects)
    _delete_in(sb, "messages", "thread_id", threads)
    _delete_in(sb, "threads", "id", threads)
    _delete_in(sb, "proposals", "project_id", projects)
    _delete_in(sb, "projects", "id", projects)
    _delete_in(sb, "freelancers", "id", freelancers)
    _delete_in(sb, "clients", "id", clients)


def reset_demo(sb, log=print) -> dict:
    """Replace the investor-demo data with a fresh copy. Returns row counts per table.
    Real accounts and their data are left alone."""
    clear_demo(sb, log)
    counts = {}
    for table, rows in build_rows().items():
        if rows:
            # default_to_null=False: fields a row leaves out get the column's default, not NULL
            sb.table(table).insert(rows, default_to_null=False).execute()
        counts[table] = len(rows)
        log(f"  {table:<14} {len(rows)} rows")
    return counts


def main() -> int:
    try:
        sb = get_client()
    except NotConfigured as e:
        print(f"Can't connect: {e}")
        return 1
    reset_demo(sb)
    print("Done. Demo data loaded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
