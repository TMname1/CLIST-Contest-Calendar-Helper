#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import clist_to_ics

OUTPUT_PATH = Path(__file__).resolve().parent / "contests.ics"
PER_RESOURCE_LIMIT = 50
CALENDAR_NAME = "CLIST Contests"
PRODUCT_ID = "-//CLIST Import//EN"


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"Environment variable {name} is required")
    return value


def main() -> None:
    username = require_env("CLIST_API_USERNAME")
    api_key = require_env("CLIST_API_KEY")

    now_utc = datetime.now(timezone.utc)
    ends_before = now_utc + timedelta(days=3)

    resource_filters = clist_to_ics.resolve_resource_filters(clist_to_ics.DEFAULT_RESOURCES)

    contests = clist_to_ics.fetch_contests_for_resources(
        resource_filters=resource_filters,
        username=username,
        api_key=api_key,
        starts_after=now_utc,
        ends_before=ends_before,
        per_resource_limit=PER_RESOURCE_LIMIT,
        include_ended=False,
    )

    if not contests:
        print("No contests found in the next three days.")
        return

    deduped = clist_to_ics.deduplicate_contests(contests)
    deduped.sort(key=lambda contest: contest.start)

    calendar_text = clist_to_ics.generate_ics(
        contests=deduped,
        calendar_name=CALENDAR_NAME,
        product_id=PRODUCT_ID,
    )

    OUTPUT_PATH.write_text(calendar_text, encoding="utf-8")
    print(f"Wrote {len(deduped)} contest(s) to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
