#!/usr/bin/env python3
"""
Fetch CLIST contests for selected competitive programming platforms and export them as an .ics calendar file.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from urllib import error, parse, request

API_BASE = "https://clist.by/api/v2"
DEFAULT_RESOURCES = ["leetcode", "codeforces", "atcoder", "luogu", "nowcoder"]
RESOURCE_ALIASES = {
    "leetcode": "leetcode.com",
    "nowcoder": "ac.nowcoder.com",
    "nk": "ac.nowcoder.com",
    "lc": "leetcode.com",
    "codeforces": "codeforces.com",
    "cf": "codeforces.com",
    "atcoder": "atcoder.jp",
    "ac": "atcoder.jp",
    "luogu": "luogu.com.cn",
    "lg": "luogu.com.cn",
}
REQUEST_TIMEOUT = 30
PAGE_SIZE = 100


class ClistApiError(Exception):
    """Raised when the CLIST API returns an error."""


@dataclass(frozen=True)
class Contest:
    contest_id: int
    title: str
    start: dt.datetime
    end: dt.datetime
    url: str
    resource_id: int
    resource_name: str

    @property
    def duration(self) -> dt.timedelta:
        return self.end - self.start

    def summary(self) -> str:
        return f"{self.resource_name}: {self.title}"

    def description(self) -> str:
        duration_text = humanize_duration(self.duration)
        lines = [
            f"Title: {self.title}",
            f"Platform: {self.resource_name}",
            f"Duration: {duration_text}",
        ]
        if self.url:
            lines.append(f"URL: {self.url}")
        return "\n".join(lines)


def main() -> None:
    args = build_parser().parse_args()

    username = args.username or os.environ.get("CLIST_API_USERNAME")
    api_key = args.api_key or os.environ.get("CLIST_API_KEY")

    if not username or not api_key:
        sys.exit("CLIST credentials are required. Provide --username/--api-key or set CLIST_API_USERNAME/CLIST_API_KEY.")

    try:
        resource_filters = resolve_resource_filters(args.resources)
    except ClistApiError as exc:
        sys.exit(str(exc))

    starts_after = parse_cli_datetime(args.starts_after) if args.starts_after else None
    ends_before = parse_cli_datetime(args.ends_before) if args.ends_before else None
    if not starts_after and not args.include_ended:
        starts_after = dt.datetime.now(dt.timezone.utc)

    contests = fetch_contests_for_resources(
        resource_filters=resource_filters,
        username=username,
        api_key=api_key,
        starts_after=starts_after,
        ends_before=ends_before,
        per_resource_limit=args.per_resource_limit,
        include_ended=args.include_ended,
    )

    if not contests:
        sys.exit("No contests retrieved. Adjust filters or timeframe.")

    deduped = deduplicate_contests(contests)
    deduped.sort(key=lambda contest: contest.start)

    if args.max_contests and len(deduped) > args.max_contests:
        deduped = deduped[: args.max_contests]

    calendar_text = generate_ics(
        contests=deduped,
        calendar_name=args.calendar_name,
        product_id=args.product_id,
    )

    output_path = os.fspath(args.output)
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(calendar_text)

    print(f"Wrote {len(deduped)} contest(s) to {output_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch contests from clist.by for selected resources and emit an .ics calendar file.",
    )
    parser.add_argument(
        "--username",
        help="CLIST API username. Defaults to CLIST_API_USERNAME environment variable.",
    )
    parser.add_argument(
        "--api-key",
        help="CLIST API key. Defaults to CLIST_API_KEY environment variable.",
    )
    parser.add_argument(
        "--resources",
        nargs="+",
        default=DEFAULT_RESOURCES,
        help=(
            "Resource filters (alias, host, or numeric ID). Default: leetcode codeforces atcoder luogu nowcoder. "
            "Numeric values are treated as resource IDs."
        ),
    )
    parser.add_argument(
        "--starts-after",
        help="ISO timestamp (e.g. 2024-01-01T00:00:00+00:00). Filters contests starting on/after this moment.",
    )
    parser.add_argument(
        "--ends-before",
        help="ISO timestamp. Filters contests starting before this moment.",
    )
    parser.add_argument(
        "--include-ended",
        action="store_true",
        help="Include contests that have already ended.",
    )
    parser.add_argument(
        "--max-contests",
        type=int,
        default=0,
        help="Max contests to keep after merging all resources. 0 means unlimited.",
    )
    parser.add_argument(
        "--per-resource-limit",
        type=int,
        default=50,
        help="Max contests to fetch per resource. 0 means unlimited.",
    )
    parser.add_argument(
        "--calendar-name",
        default="CLIST Contests",
        help="Calendar name stored in the ICS (X-WR-CALNAME).",
    )
    parser.add_argument(
        "--product-id",
        default="-//CLIST Import//EN",
        help="Product identifier sent in the ICS PRODID field.",
    )
    parser.add_argument(
        "--output",
        default="contests.ics",
        help="Output .ics file path.",
    )
    return parser


def resolve_resource_filters(resources: Sequence[str]) -> List[Tuple[str, object]]:
    resolved: List[Tuple[str, object]] = []
    seen: set[Tuple[str, object]] = set()

    for raw in resources:
        value = raw.strip()
        if not value:
            continue

        alias = RESOURCE_ALIASES.get(value.lower())
        if alias:
            key_val = ("resource", alias)
        elif value.isdigit():
            key_val = ("resource_id", int(value))
        elif "." in value:
            key_val = ("resource", value)
        else:
            raise ClistApiError(
                f"Unknown resource '{value}'. Provide a known alias (leetcode/codeforces/atcoder/luogu), "
                "a host like codeforces.com, or a numeric resource ID."
            )

        if key_val not in seen:
            resolved.append(key_val)
            seen.add(key_val)

    if not resolved:
        raise ClistApiError("No valid resources resolved. Check the provided resource filters.")

    return resolved


def fetch_contests_for_resources(
    resource_filters: Sequence[Tuple[str, object]],
    username: str,
    api_key: str,
    starts_after: Optional[dt.datetime],
    ends_before: Optional[dt.datetime],
    per_resource_limit: int,
    include_ended: bool,
) -> List[Contest]:
    contests: List[Contest] = []
    for filter_key, filter_value in resource_filters:
        contests.extend(
            fetch_contests_for_resource(
                filter_key=filter_key,
                filter_value=filter_value,
                username=username,
                api_key=api_key,
                starts_after=starts_after,
                ends_before=ends_before,
                per_resource_limit=per_resource_limit,
                include_ended=include_ended,
            )
        )
    return contests


def fetch_contests_for_resource(
    filter_key: str,
    filter_value: object,
    username: str,
    api_key: str,
    starts_after: Optional[dt.datetime],
    ends_before: Optional[dt.datetime],
    per_resource_limit: int,
    include_ended: bool,
) -> List[Contest]:
    fetched: List[Contest] = []
    offset = 0

    while True:
        remaining = per_resource_limit - len(fetched) if per_resource_limit else PAGE_SIZE
        if per_resource_limit and remaining <= 0:
            break

        limit = PAGE_SIZE if not per_resource_limit else min(PAGE_SIZE, remaining)
        params: Dict[str, object] = {
            filter_key: filter_value,
            "order_by": "start",
            "offset": offset,
            "limit": limit,
        }
        if starts_after:
            params["start__gte"] = to_api_time(starts_after)
        if ends_before:
            params["start__lte"] = to_api_time(ends_before)
        if not include_ended:
            params["end__gte"] = to_api_time(dt.datetime.now(dt.timezone.utc))

        data = api_get("/contest/", params, username, api_key)
        objects = data.get("objects", [])
        if not objects:
            break

        for payload in objects:
            try:
                contest = parse_contest(payload)
            except ValueError as exc:
                print(f"Skipping contest due to parse error: {exc}", file=sys.stderr)
                continue
            fetched.append(contest)
            if per_resource_limit and len(fetched) >= per_resource_limit:
                return fetched

        offset += len(objects)

        if not data.get("meta", {}).get("next"):
            break

    return fetched


def parse_contest(payload: Dict[str, object]) -> Contest:
    contest_id = int(payload["id"])  # type: ignore[index]
    title = str(payload.get("event") or payload.get("title") or f"Contest {contest_id}")
    start = parse_iso_datetime(str(payload.get("start")))
    end = parse_iso_datetime(str(payload.get("end")))
    href = str(
        payload.get("href")
        or payload.get("event_url")
        or payload.get("url")
        or ""
    )

    resource_field = payload.get("resource")
    resource_info = resource_field if isinstance(resource_field, dict) else {}
    resource_id = int(
        payload.get("resource_id")
        or resource_info.get("id")
        or 0
    )
    resource_name = str(
        resource_info.get("name")
        or resource_info.get("short_name")
        or resource_info.get("host")
        or resource_field
        or f"Resource {resource_id}"
    )

    return Contest(
        contest_id=contest_id,
        title=title.strip(),
        start=start,
        end=end,
        url=href.strip(),
        resource_id=resource_id,
        resource_name=resource_name.strip(),
    )


def parse_iso_datetime(value: str) -> dt.datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        try:
            parsed = dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            raise ValueError(f"Unsupported datetime format: {value}") from exc
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def parse_cli_datetime(value: str) -> dt.datetime:
    parsed = parse_iso_datetime(value)
    return parsed


def to_api_time(value: dt.datetime) -> str:
    return ensure_utc(value).isoformat().replace("+00:00", "Z")


def ensure_utc(value: dt.datetime) -> dt.datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc)


def api_get(path: str, params: Dict[str, object], username: str, api_key: str) -> Dict[str, object]:
    query = parse.urlencode(params, doseq=True)
    url = f"{API_BASE}{path}?{query}" if query else f"{API_BASE}{path}"

    req = request.Request(url)
    req.add_header("Authorization", f"ApiKey {username}:{api_key}")
    req.add_header("Accept", "application/json")

    try:
        with request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
            payload = response.read()
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise ClistApiError(f"CLIST API error ({exc.code}) for {url}: {detail}") from exc
    except error.URLError as exc:
        raise ClistApiError(f"Failed to reach CLIST API: {exc.reason}") from exc

    try:
        return json.loads(payload.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ClistApiError("CLIST API response was not valid JSON") from exc


def deduplicate_contests(contests: Iterable[Contest]) -> List[Contest]:
    by_id: Dict[int, Contest] = {}
    for contest in contests:
        by_id[contest.contest_id] = contest
    return list(by_id.values())


def generate_ics(contests: Sequence[Contest], calendar_name: str, product_id: str) -> str:
    now_utc = dt.datetime.now(dt.timezone.utc)
    lines: List[str] = [
        "BEGIN:VCALENDAR",
        fold_ics_line(f"PRODID:{product_id}"),
        "VERSION:2.0",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    if calendar_name:
        lines.append(fold_ics_line(f"X-WR-CALNAME:{escape_ics_text(calendar_name)}"))

    for contest in contests:
        lines.append("BEGIN:VEVENT")
        lines.append(fold_ics_line(f"UID:{contest.contest_id}@clist.by"))
        lines.append(fold_ics_line(f"DTSTAMP:{format_ics_datetime(now_utc)}"))
        lines.append(fold_ics_line(f"DTSTART:{format_ics_datetime(contest.start)}"))
        lines.append(fold_ics_line(f"DTEND:{format_ics_datetime(contest.end)}"))
        lines.append(fold_ics_line(f"SUMMARY:{escape_ics_text(contest.summary())}"))
        lines.append(fold_ics_line(f"DESCRIPTION:{escape_ics_text(contest.description())}"))
        if contest.url:
            lines.append(fold_ics_line(f"URL:{escape_ics_text(contest.url)}"))
        lines.append(fold_ics_line(f"CATEGORIES:{escape_ics_text(contest.resource_name)}"))
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def format_ics_datetime(value: dt.datetime) -> str:
    return ensure_utc(value).strftime("%Y%m%dT%H%M%SZ")


def escape_ics_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def fold_ics_line(line: str) -> str:
    if len(line) <= 75:
        return line
    segments = [line[:75]]
    remainder = line[75:]
    while remainder:
        segments.append(" " + remainder[:74])
        remainder = remainder[74:]
    return "\r\n".join(segments)


def humanize_duration(delta: dt.timedelta) -> str:
    seconds = int(delta.total_seconds())
    if seconds < 0:
        seconds = 0
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    parts: List[str] = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs and not parts:
        parts.append(f"{secs}s")
    return " ".join(parts) or "0m"


if __name__ == "__main__":
    main()
