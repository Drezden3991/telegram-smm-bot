import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from storage.clients import migrate_clients_from_txt


def main():
    result = migrate_clients_from_txt()

    if result.already_migrated:
        print("Миграция Clients уже была выполнена. Новых записей нет.")
        return

    source_status = "найден" if result.source_found else "не найден"
    print(
        "Миграция Clients завершена: "
        f"перенесено записей — {result.migrated_count}; "
        f"TXT-источник {source_status}."
    )


if __name__ == "__main__":
    main()
