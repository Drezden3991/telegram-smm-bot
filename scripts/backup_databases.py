"""Create explicit local backups of the four production SQLite databases."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from storage.backups import BackupError, DEFAULT_BACKUP_DIRECTORY, backup_all_databases


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    os.chdir(PROJECT_ROOT)
    backup_directory = os.getenv("BACKUP_DIRECTORY", DEFAULT_BACKUP_DIRECTORY)

    try:
        results = backup_all_databases(backup_directory)
    except BackupError as error:
        print(f"Backup failed: {type(error).__name__}")
        return 1

    for result in results:
        if result.status == "created":
            print(f"{result.database_name}: backup created")
        else:
            print(f"{result.database_name}: skipped (database not found)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
