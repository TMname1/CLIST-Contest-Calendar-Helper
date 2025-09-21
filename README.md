# CLIST Contest Calendar Helper

This repository contains a small Python utility that retrieves upcoming competitive programming contests from the CLIST API and exports them as an iCalendar (.ics) file that you can import into TickTick or any other calendar application.

## Features
- Fetches contests for popular platforms such as LeetCode, Codeforces, AtCoder, Luogu, and Nowcoder by default.
- Supports custom resource filters, per-resource limits, and date windows.
- Generates standards-compliant ICS events with rich descriptions and platform categories.
- Provides an interactive helper that stores credentials locally to streamline repeated exports.

## Requirements
- Python 3.9 or later.
- A CLIST account with API access (username and API key).
- Network access to https://clist.by/api/v2.

## Setup
- Clone or download this repository.
- (Optional) Create and activate a virtual environment for isolation.
- No third-party dependencies are required; the Python standard library is sufficient.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python --version
```

## Obtain CLIST API credentials
- Sign in at https://clist.by/ and open your profile settings.
- Generate an API key (or reuse an existing key) and note your CLIST username.
- Keep these values available for the helper prompts or set them as environment variables.

## Usage

### Interactive helper (`clist_helper.py`)
Run the helper to be guided through credential entry, time window selection, and output path.

```powershell
python clist_helper.py
```

Key behavior:
- Saved credentials are stored in `clist_credentials.json`. You can reuse, replace, or delete them from within the helper.
- The script can filter contests that start after or end before an ISO timestamp (for example `2025-01-01T00:00:00+00:00`).
- Output defaults to `contests.ics`; provide any writable path to change it.

### Direct CLI (`clist_to_ics.py`)
Use the lower-level script if you prefer full control or want to automate exports.

```powershell
python clist_to_ics.py --username YOUR_USERNAME --api-key YOUR_API_KEY --resources codeforces atcoder --starts-after 2025-01-01T00:00:00+00:00 --output contests.ics
```

You may also set `CLIST_API_USERNAME` and `CLIST_API_KEY` environment variables instead of passing the flags.

Common options:
- `--resources`: Aliases, hosts, or numeric resource IDs. Defaults to `leetcode codeforces atcoder luogu nowcoder`.
- `--starts-after` / `--ends-before`: ISO timestamps used to bound the contest start times.
- `--include-ended`: Include contests that have already finished (off by default).
- `--per-resource-limit`: Limit contests fetched per platform (default 50, 0 means unlimited).
- `--max-contests`: Trim the merged result to the first N contests.
- `--calendar-name`: Override the calendar display name in the ICS output.
- `--product-id`: Customize the ICS `PRODID` header.
- `--output`: Destination path for the generated file.

## Resource aliases
The helper understands these shortcuts in addition to full hostnames:
- `leetcode`, `lc` -> `leetcode.com`
- `codeforces`, `cf` -> `codeforces.com`
- `atcoder`, `ac` -> `atcoder.jp`
- `luogu`, `lg` -> `luogu.com.cn`
- `nowcoder`, `nk` -> `ac.nowcoder.com`

Use numeric IDs if you need a platform that is not listed above.

## Saved credentials
The helper writes `clist_credentials.json` in the repository root so you can skip re-entering your username and API key. Delete the file manually or choose the helper option to remove it if you want to purge stored data.

## Importing the calendar
The generated `.ics` file can be imported into TickTick, Google Calendar, Outlook, or any other iCalendar-compatible client. Each event includes:
- A summary of the platform and contest title.
- Start and end timestamps in UTC.
- A rich description with the contest URL and duration.
- A category set to the platform name for filtering.

## Troubleshooting
- **No contests retrieved**: Broaden the time window, add `--include-ended`, or remove restrictive resource filters.
- **CLIST API error**: Confirm your username/API key combination and verify that your account has API access. Temporary network issues can also cause failures.
- **Time parsing errors**: Provide ISO 8601 timestamps such as `2025-01-10T12:00:00+00:00` or append `Z` for UTC.

## License
This project is distributed under the MIT License. See `LICENSE` for details.
