import json
import subprocess
import sys
from datetime import datetime
from getpass import getpass
from pathlib import Path
from typing import Dict, Optional

CREDENTIALS_PATH = Path("clist_credentials.json")


def main() -> None:
    print("CLIST contest calendar helper")
    print("--------------------------------\n")

    credentials = select_credentials()
    starts_after = prompt_datetime("Enter start time (ISO, blank for default now): ")
    ends_before = prompt_datetime("Enter end time (ISO, blank to skip): ")
    include_ended = prompt_yes_no("Include contests that already ended?", default=False)
    output_path = input("Output .ics path [contests.ics]: ").strip() or "contests.ics"

    cmd = [
        sys.executable,
        "clist_to_ics.py",
        "--username",
        credentials["username"],
        "--api-key",
        credentials["api_key"],
        "--output",
        output_path,
    ]

    if starts_after:
        cmd.extend(["--starts-after", starts_after])
    if ends_before:
        cmd.extend(["--ends-before", ends_before])
    if include_ended:
        cmd.append("--include-ended")

    print("\nRunning:")
    print(" ".join(cmd))
    print()

    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        sys.exit(result.returncode)


def select_credentials() -> Dict[str, str]:
    saved = load_saved_credentials()

    if saved:
        print("Saved credentials detected:")
        print(f"  Username: {saved['username']}")
        print("Select an option:")
        print("  1) Use the saved credentials")
        print("  2) Enter new credentials and delete saved data")
        choice = prompt_menu_choice(default="1", options={"1", "2"})

        if choice == "1":
            return saved
        delete_saved_credentials()
        print()

    else:
        print("No saved credentials found. Please enter them now.\n")

    credentials = prompt_new_credentials()
    save_credentials(credentials)
    return credentials


def prompt_new_credentials() -> Dict[str, str]:
    username = prompt_non_empty("CLIST username: ")
    print("(API key input is hidden; paste and press Enter.)")
    api_key = prompt_secret("CLIST API key: ")
    print()
    return {"username": username, "api_key": api_key}


def prompt_menu_choice(*, default: str, options: set[str]) -> str:
    while True:
        answer = input(f"Enter choice [{default}]: ").strip()
        if not answer:
            return default
        if answer in options:
            return answer
        print("Invalid choice, please try again.")


def load_saved_credentials() -> Optional[Dict[str, str]]:
    if not CREDENTIALS_PATH.exists():
        return None
    try:
        data = json.loads(CREDENTIALS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print("Saved credential file is corrupted; ignoring it.\n")
        return None

    if not isinstance(data, dict):
        return None
    username = data.get("username")
    api_key = data.get("api_key")
    if isinstance(username, str) and isinstance(api_key, str):
        return {"username": username, "api_key": api_key}
    return None


def save_credentials(data: Dict[str, str]) -> None:
    CREDENTIALS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print("Credentials saved.\n")


def delete_saved_credentials() -> None:
    try:
        CREDENTIALS_PATH.unlink()
        print("Saved credential file deleted.\n")
    except FileNotFoundError:
        pass


def prompt_non_empty(message: str) -> str:
    while True:
        value = input(message).strip()
        if value:
            return value
        print("Value cannot be empty. Please try again.")


def prompt_secret(message: str) -> str:
    while True:
        value = getpass(message)
        value = value.strip()
        if value:
            return value
        print("Value cannot be empty. Please try again.")


def prompt_yes_no(message: str, *, default: bool) -> bool:
    suffix = " [Y/n]" if default else " [y/N]"
    while True:
        answer = input(message + suffix + ": ").strip().lower()
        if not answer:
            return default
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("Please answer yes or no.")


def prompt_datetime(message: str) -> Optional[str]:
    while True:
        value = input(message).strip()
        if not value:
            return None
        if is_valid_iso_datetime(value):
            return canonicalize_iso(value)
        print("Invalid datetime. Use ISO format like 2025-01-01T00:00:00+00:00 or append 'Z'.")


def is_valid_iso_datetime(value: str) -> bool:
    try:
        datetime.fromisoformat(canonicalize_iso(value))
    except ValueError:
        return False
    return True


def canonicalize_iso(value: str) -> str:
    if value.endswith("Z"):
        return value[:-1] + "+00:00"
    return value


if __name__ == "__main__":
    main()
