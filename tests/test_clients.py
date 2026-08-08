import unittest
from unittest.mock import patch

from handlers import clients as clients_handler


def make_client(
    name="Иван",
    last_name="Иванов",
    phone="+372 5555 0000",
    instagram="@ivan",
    email="ivan@example.com",
    notes="Постоянный клиент",
):
    return {
        "name": name,
        "last_name": last_name,
        "phone": phone,
        "instagram": instagram,
        "email": email,
        "notes": notes,
    }


class ClientSerializationTests(unittest.TestCase):
    def test_create_client_from_current_six_field_format(self):
        line = (
            "Иван | Иванов | +372 5555 0000 | @ivan | "
            "ivan@example.com | Постоянный клиент"
        )

        client = clients_handler.create_client_from_line(line)

        self.assertEqual(client, make_client())

    def test_create_client_from_legacy_five_field_format(self):
        line = (
            "Иван | +372 5555 0000 | @ivan | "
            "ivan@example.com | Постоянный клиент"
        )

        client = clients_handler.create_client_from_line(line)

        self.assertEqual(
            client,
            make_client(last_name=""),
        )

    def test_create_client_from_nonstandard_line_uses_whole_line_as_name(self):
        line = "Иван | нестандартная строка"

        client = clients_handler.create_client_from_line(line)

        self.assertEqual(
            client,
            {
                "name": line,
                "last_name": "",
                "phone": "",
                "instagram": "",
                "email": "",
                "notes": "",
            },
        )

    def test_create_line_from_client_serializes_six_fields(self):
        client = make_client()

        line = clients_handler.create_line_from_client(client)

        self.assertEqual(
            line,
            (
                "Иван | Иванов | +372 5555 0000 | @ivan | "
                "ivan@example.com | Постоянный клиент"
            ),
        )


class ClientLookupTests(unittest.TestCase):
    def setUp(self):
        self.client = make_client()
        self.clients_patch = patch.object(
            clients_handler,
            "clients",
            [self.client],
        )
        self.clients_patch.start()
        self.addCleanup(self.clients_patch.stop)

    def test_find_client_by_full_name_is_case_insensitive(self):
        found_client = clients_handler.find_client_by_full_name(
            "иВаН",
            "иВаНоВ",
        )

        self.assertIs(found_client, self.client)

    def test_find_client_by_full_name_returns_none_without_match(self):
        found_client = clients_handler.find_client_by_full_name(
            "Пётр",
            "Петров",
        )

        self.assertIsNone(found_client)

    def test_client_exists_returns_true_for_existing_client(self):
        self.assertTrue(
            clients_handler.client_exists("ИВАН", "ИВАНОВ")
        )

    def test_client_exists_returns_false_for_missing_client(self):
        self.assertFalse(
            clients_handler.client_exists("Пётр", "Петров")
        )

    def test_get_field_key_returns_empty_string_for_unknown_field(self):
        self.assertEqual(
            clients_handler.get_field_key("Неизвестное поле"),
            "",
        )


if __name__ == "__main__":
    unittest.main()
