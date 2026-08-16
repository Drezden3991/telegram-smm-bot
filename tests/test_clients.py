import importlib
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import Mock, patch

from aiogram.fsm.state import State

from handlers import clients as clients_handler
from storage import clients as clients_storage


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


class FakeMessage:
    def __init__(self, text=""):
        self.text = text
        self.from_user = SimpleNamespace(id=None)
        self.answers = []

    async def answer(self, text, **kwargs):
        self.answers.append((text, kwargs))


class FakeState:
    def __init__(self, data=None, state=None):
        self.data = dict(data or {})
        self.state = state
        self.cleared = False

    async def get_data(self):
        return dict(self.data)

    async def update_data(self, data=None, **kwargs):
        if data:
            self.data.update(data)

        self.data.update(kwargs)
        return dict(self.data)

    async def get_state(self):
        if isinstance(self.state, State):
            return self.state.state

        return self.state

    async def set_state(self, state):
        self.state = state

    async def clear(self):
        self.data.clear()
        self.state = None
        self.cleared = True


class ClientSerializationTests(unittest.TestCase):
    def test_create_client_from_current_six_field_format(self):
        line = (
            "Иван | Иванов | +372 5555 0000 | @ivan | "
            "ivan@example.com | Постоянный клиент"
        )

        client = clients_storage.create_client_from_line(line)

        self.assertEqual(client, make_client())

    def test_create_client_from_legacy_five_field_format(self):
        line = (
            "Иван | +372 5555 0000 | @ivan | "
            "ivan@example.com | Постоянный клиент"
        )

        client = clients_storage.create_client_from_line(line)

        self.assertEqual(
            client,
            make_client(last_name=""),
        )

    def test_create_client_from_nonstandard_line_uses_whole_line_as_name(self):
        line = "Иван | нестандартная строка"

        client = clients_storage.create_client_from_line(line)

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

        line = clients_storage.create_line_from_client(client)

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
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)

        clients_file = Path(
            self.temporary_directory.name
        ) / "clients.txt"
        clients_database = Path(
            self.temporary_directory.name
        ) / "clients.db"
        self.file_patch = patch.object(
            clients_storage,
            "CLIENTS_FILE",
            str(clients_file),
        )
        self.file_patch.start()
        self.addCleanup(self.file_patch.stop)
        self.database_patch = patch.object(
            clients_storage,
            "CLIENTS_DATABASE",
            str(clients_database),
        )
        self.database_patch.start()
        self.addCleanup(self.database_patch.stop)

        clients_storage.save_clients([self.client])

    def test_find_client_by_full_name_is_case_insensitive(self):
        found_client = clients_handler.find_client_by_full_name(
            "иВаН",
            "иВаНоВ",
        )

        self.assertEqual(found_client, self.client)

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


class ClientCrudCharacterizationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)

        self.clients_file = Path(
            self.temporary_directory.name
        ) / "clients.txt"
        self.clients_database = Path(
            self.temporary_directory.name
        ) / "clients.db"
        self.file_patch = patch.object(
            clients_storage,
            "CLIENTS_FILE",
            str(self.clients_file),
        )
        self.file_patch.start()
        self.addCleanup(self.file_patch.stop)
        self.database_patch = patch.object(
            clients_storage,
            "CLIENTS_DATABASE",
            str(self.clients_database),
        )
        self.database_patch.start()
        self.addCleanup(self.database_patch.stop)

    async def _create_client_through_handler(self, client):
        state = FakeState()

        await clients_handler.ask_client_name(
            FakeMessage("➕ Добавить клиента"),
            state,
        )

        for field_name in (
            "name",
            "last_name",
            "phone",
            "instagram",
            "email",
            "notes",
        ):
            await clients_handler.handle_client_text(
                FakeMessage(client[field_name]),
                state,
            )

        return state

    async def _assert_successful_field_edit(
        self,
        field_name,
        new_value,
    ):
        target_client = make_client()
        untouched_client = make_client(
            name="Анна",
            last_name="Петрова",
            phone="+372 5555 1111",
            instagram="@anna",
            email="anna@example.com",
            notes="Другой клиент",
        )
        original_target = dict(target_client)
        original_untouched = dict(untouched_client)
        current_clients = [target_client, untouched_client]
        clients_storage.save_clients(current_clients)
        state = FakeState(
            data={
                "client_name": original_target["name"],
                "client_last_name": original_target["last_name"],
                "field_to_edit": field_name,
            },
            state=clients_handler.ClientFlow.waiting_for_edit_value,
        )
        message = FakeMessage(new_value)

        with patch.object(
            clients_storage,
            "update_client_field_by_full_name",
            wraps=clients_storage.update_client_field_by_full_name,
        ) as update_client:
            await clients_handler.handle_client_text(
                message,
                state,
            )

        expected_target = dict(original_target)
        expected_target[field_name] = new_value

        self.assertEqual(target_client, original_target)
        self.assertEqual(untouched_client, original_untouched)
        self.assertEqual(
            clients_storage.load_clients(),
            [expected_target, original_untouched],
        )
        update_client.assert_called_once_with(
            original_target["name"],
            original_target["last_name"],
            field_name,
            new_value,
        )
        self.assertTrue(state.cleared)
        self.assertEqual(
            message.answers[-1][0],
            "✅ Данные клиента обновлены.",
        )

    async def test_successful_creation_saves_all_six_fields_once(self):
        new_client = make_client(
            name="Анна",
            last_name="Петрова",
            phone="+372 5555 1111",
            instagram="@anna",
            email="anna@example.com",
            notes="Новый клиент",
        )
        with patch.object(
            clients_storage,
            "add_client",
            wraps=clients_storage.add_client,
        ) as add_client:
            state = await self._create_client_through_handler(
                new_client
            )

        self.assertEqual(
            clients_storage.load_clients(),
            [new_client],
        )
        add_client.assert_called_once_with(new_client)
        self.assertTrue(state.cleared)

    async def test_duplicate_client_is_not_added_or_saved(self):
        existing_client = make_client()
        clients_storage.save_clients([existing_client])
        state = FakeState(
            data={"new_client": {"name": "Иван"}},
            state=clients_handler.ClientFlow.waiting_for_last_name,
        )
        message = FakeMessage("Иванов")
        add_client = Mock()

        with patch.object(
            clients_storage,
            "add_client",
            add_client,
        ):
            await clients_handler.handle_client_text(
                message,
                state,
            )

        self.assertEqual(
            clients_storage.load_clients(),
            [existing_client],
        )
        add_client.assert_not_called()
        self.assertTrue(state.cleared)
        self.assertEqual(
            message.answers[-1][0],
            "Такой клиент уже существует.",
        )

    async def test_successful_deletion_removes_only_selected_client(self):
        selected_client = make_client()
        remaining_client = make_client(
            name="Анна",
            last_name="Петрова",
        )
        current_clients = [selected_client, remaining_client]
        clients_storage.save_clients(current_clients)
        state = FakeState(
            state=clients_handler.ClientFlow.waiting_for_delete,
        )
        message = FakeMessage("Иван Иванов")

        with patch.object(
            clients_storage,
            "delete_client_by_full_name",
            wraps=clients_storage.delete_client_by_full_name,
        ) as delete_client:
            await clients_handler.handle_client_text(
                message,
                state,
            )

        self.assertEqual(
            current_clients,
            [selected_client, remaining_client],
        )
        self.assertEqual(
            clients_storage.load_clients(),
            [remaining_client],
        )
        delete_client.assert_called_once_with("Иван", "Иванов")
        self.assertTrue(state.cleared)
        self.assertEqual(
            message.answers[-1][0],
            "✅ Клиент «Иван Иванов» удалён.",
        )

    async def test_missing_or_stale_client_does_not_delete_another(self):
        remaining_client = make_client(
            name="Анна",
            last_name="Петрова",
        )
        current_clients = [remaining_client]
        clients_storage.save_clients(current_clients)
        state = FakeState(
            state=clients_handler.ClientFlow.waiting_for_delete,
        )
        message = FakeMessage("Иван Иванов")
        delete_client = Mock()

        with patch.object(
            clients_storage,
            "delete_client_by_full_name",
            delete_client,
        ):
            await clients_handler.handle_client_text(
                message,
                state,
            )

        self.assertEqual(current_clients, [remaining_client])
        self.assertEqual(
            clients_storage.load_clients(),
            [remaining_client],
        )
        delete_client.assert_not_called()
        self.assertTrue(state.cleared)
        self.assertEqual(
            message.answers[-1][0],
            "Клиент «Иван Иванов» не найден.",
        )

    async def test_edit_name_changes_only_name_and_saves(self):
        await self._assert_successful_field_edit(
            "name",
            "Пётр",
        )

    async def test_edit_last_name_changes_only_last_name_and_saves(self):
        await self._assert_successful_field_edit(
            "last_name",
            "Петров",
        )

    async def test_edit_phone_changes_only_phone_and_saves(self):
        await self._assert_successful_field_edit(
            "phone",
            "+372 5555 2222",
        )

    async def test_edit_instagram_changes_only_instagram_and_saves(self):
        await self._assert_successful_field_edit(
            "instagram",
            "@new_ivan",
        )

    async def test_edit_email_changes_only_email_and_saves(self):
        await self._assert_successful_field_edit(
            "email",
            "new.ivan@example.com",
        )

    async def test_edit_notes_changes_only_notes_and_saves(self):
        await self._assert_successful_field_edit(
            "notes",
            "Обновлённые заметки",
        )

    async def test_unchanged_non_name_field_is_not_saved(self):
        existing_client = make_client()
        clients_storage.save_clients([existing_client])
        state = FakeState(
            data={
                "client_name": "Иван",
                "client_last_name": "Иванов",
                "field_to_edit": "phone",
            },
            state=clients_handler.ClientFlow.waiting_for_edit_value,
        )
        message = FakeMessage(existing_client["phone"])
        update_client = Mock()

        with patch.object(
            clients_storage,
            "update_client_field_by_full_name",
            update_client,
        ):
            await clients_handler.handle_client_text(
                message,
                state,
            )

        self.assertEqual(
            clients_storage.load_clients(),
            [existing_client],
        )
        update_client.assert_not_called()
        self.assertTrue(state.cleared)
        self.assertEqual(
            message.answers[-1][0],
            "✅ Данные клиента обновлены.",
        )

    async def test_duplicate_name_rename_is_not_saved(self):
        target_client = make_client()
        duplicate_client = make_client(name="Пётр")
        current_clients = [target_client, duplicate_client]
        original_clients = [dict(client) for client in current_clients]
        clients_storage.save_clients(current_clients)
        state = FakeState(
            data={
                "client_name": "Иван",
                "client_last_name": "Иванов",
                "field_to_edit": "name",
            },
            state=clients_handler.ClientFlow.waiting_for_edit_value,
        )
        message = FakeMessage("Пётр")
        update_client = Mock()

        with patch.object(
            clients_storage,
            "update_client_field_by_full_name",
            update_client,
        ):
            await clients_handler.handle_client_text(
                message,
                state,
            )

        self.assertEqual(current_clients, original_clients)
        update_client.assert_not_called()
        self.assertTrue(state.cleared)
        self.assertEqual(
            message.answers[-1][0],
            "Клиент «Пётр Иванов» уже существует.",
        )

    async def test_duplicate_last_name_rename_is_not_saved(self):
        target_client = make_client()
        duplicate_client = make_client(last_name="Петров")
        current_clients = [target_client, duplicate_client]
        original_clients = [dict(client) for client in current_clients]
        clients_storage.save_clients(current_clients)
        state = FakeState(
            data={
                "client_name": "Иван",
                "client_last_name": "Иванов",
                "field_to_edit": "last_name",
            },
            state=clients_handler.ClientFlow.waiting_for_edit_value,
        )
        message = FakeMessage("Петров")
        update_client = Mock()

        with patch.object(
            clients_storage,
            "update_client_field_by_full_name",
            update_client,
        ):
            await clients_handler.handle_client_text(
                message,
                state,
            )

        self.assertEqual(current_clients, original_clients)
        update_client.assert_not_called()
        self.assertTrue(state.cleared)
        self.assertEqual(
            message.answers[-1][0],
            "Клиент «Иван Петров» уже существует.",
        )

    async def test_disappeared_client_is_not_replaced_or_saved(self):
        remaining_client = make_client(
            name="Анна",
            last_name="Петрова",
        )
        current_clients = [remaining_client]
        clients_storage.save_clients(current_clients)
        state = FakeState(
            data={
                "client_name": "Иван",
                "client_last_name": "Иванов",
                "field_to_edit": "phone",
            },
            state=clients_handler.ClientFlow.waiting_for_edit_value,
        )
        message = FakeMessage("+372 5555 9999")
        update_client = Mock()

        with patch.object(
            clients_storage,
            "update_client_field_by_full_name",
            update_client,
        ):
            await clients_handler.handle_client_text(
                message,
                state,
            )

        self.assertEqual(current_clients, [remaining_client])
        update_client.assert_not_called()
        self.assertTrue(state.cleared)
        self.assertEqual(
            message.answers[-1][0],
            "Клиент не найден.",
        )

    async def test_search_exact_match_reads_storage_and_keeps_format(self):
        matching_client = make_client()
        other_client = make_client(
            name="Анна",
            last_name="Петрова",
        )
        state = FakeState(
            state=clients_handler.ClientFlow.waiting_for_search,
        )
        message = FakeMessage("иВаН иВаНоВ")
        clients_storage.save_clients(
            [matching_client, other_client]
        )

        await clients_handler.handle_client_text(
            message,
            state,
        )

        self.assertEqual(
            message.answers[-1][0],
            "🔎 Найденные клиенты:\n\n"
            "1. Иван Иванов\n"
            "   Телефон: +372 5555 0000\n"
            "   Instagram: @ivan\n"
            "   Email: ivan@example.com\n"
            "   Заметки: Постоянный клиент\n\n",
        )
        self.assertTrue(state.cleared)

    async def test_search_partial_match_reads_storage(self):
        matching_client = make_client()
        other_client = make_client(
            name="Анна",
            last_name="Петрова",
        )
        state = FakeState(
            state=clients_handler.ClientFlow.waiting_for_search,
        )
        message = FakeMessage("ВАНОВ")
        clients_storage.save_clients(
            [matching_client, other_client]
        )

        await clients_handler.handle_client_text(
            message,
            state,
        )

        self.assertEqual(
            message.answers[-1][0],
            "🔎 Найденные клиенты:\n\n"
            "1. Иван Иванов\n"
            "   Телефон: +372 5555 0000\n"
            "   Instagram: @ivan\n"
            "   Email: ivan@example.com\n"
            "   Заметки: Постоянный клиент\n\n",
        )
        self.assertTrue(state.cleared)

    async def test_search_without_match_preserves_current_message(self):
        state = FakeState(
            state=clients_handler.ClientFlow.waiting_for_search,
        )
        message = FakeMessage("Несуществующий")
        clients_storage.save_clients([make_client()])

        await clients_handler.handle_client_text(
            message,
            state,
        )

        self.assertEqual(
            message.answers[-1][0],
            "Клиенты не найдены.",
        )
        self.assertTrue(state.cleared)

    async def test_search_does_not_strip_query_whitespace(self):
        state = FakeState(
            state=clients_handler.ClientFlow.waiting_for_search,
        )
        message = FakeMessage(" Иван Иванов ")
        clients_storage.save_clients([make_client()])

        await clients_handler.handle_client_text(
            message,
            state,
        )

        self.assertEqual(
            message.answers[-1][0],
            "Клиенты не найдены.",
        )
        self.assertTrue(state.cleared)


class ClientArchitectureTests(unittest.TestCase):
    def test_handler_has_no_global_clients_list(self):
        self.assertFalse(hasattr(clients_handler, "clients"))

    def test_importing_handler_does_not_load_clients(self):
        with patch.object(
            clients_storage,
            "load_clients",
        ) as load_clients:
            importlib.reload(clients_handler)

        load_clients.assert_not_called()


if __name__ == "__main__":
    unittest.main()
