"""Explicitly assign unowned legacy SQLite rows to one Telegram user.

Run this only after confirming that the selected domain's legacy rows belong
to that one user. Normal bot startup never calls this script.
"""

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from storage.clients import assign_legacy_clients
from storage.content_plans import assign_legacy_content_plans
from storage.post_ideas import assign_legacy_post_ideas
from storage.posts import assign_legacy_posts


ASSIGNMENTS = {
    "clients": assign_legacy_clients,
    "post_ideas": assign_legacy_post_ideas,
    "posts": assign_legacy_posts,
    "content_plans": assign_legacy_content_plans,
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Assign unowned legacy data to one Telegram user."
    )
    parser.add_argument("telegram_user_id", type=int)
    parser.add_argument("--domain", choices=ASSIGNMENTS, required=True)
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required because this changes ownerless legacy rows.",
    )
    arguments = parser.parse_args()

    if not arguments.confirm:
        parser.error("Pass --confirm only after checking the legacy rows.")

    assigned_count = ASSIGNMENTS[arguments.domain](
        arguments.telegram_user_id
    )
    print(
        f"Assigned {assigned_count} legacy {arguments.domain} rows "
        f"to Telegram user {arguments.telegram_user_id}."
    )


if __name__ == "__main__":
    main()
