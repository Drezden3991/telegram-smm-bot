import unittest
from unittest.mock import AsyncMock, Mock, patch

from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from handlers import clients, content_plan, post_ideas
from handlers import start as start_handler


class FakeMessage:
    def __init__(self, text=""):
        self.text = text
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


def get_state_filters(router, callback):
    return [
        filter_object.callback
        for handler in router.message.handlers
        if handler.callback is callback
        for filter_object in handler.filters
        if isinstance(filter_object.callback, StateFilter)
    ]


class PostIdeasBackTests(unittest.IsolatedAsyncioTestCase):
    async def test_back_cancels_single_step_idea_scenarios(self):
        states = (
            post_ideas.AddPostIdea.waiting_for_idea,
            post_ideas.DeletePostIdea.waiting_for_idea_number,
            post_ideas.SearchPostIdea.waiting_for_search_text,
            post_ideas.EditPostIdea.waiting_for_idea_number,
        )

        for active_state in states:
            with self.subTest(state=active_state.state):
                message = FakeMessage("⬅️ Назад")
                state = FakeState(state=active_state)

                await post_ideas.cancel_post_idea_action(
                    message,
                    state,
                )

                self.assertTrue(state.cleared)
                self.assertIs(
                    message.answers[-1][1]["reply_markup"],
                    post_ideas.post_ideas_menu,
                )

    async def test_back_from_new_text_returns_to_number_selection(self):
        message = FakeMessage("⬅️ Назад")
        state = FakeState(
            data={
                "idea_number": 1,
                "selected_idea": "💡 Первая идея",
            },
            state=post_ideas.EditPostIdea.waiting_for_new_idea_text,
        )

        with patch.object(
            post_ideas,
            "load_post_ideas",
            return_value=["💡 Первая идея"],
        ):
            await post_ideas.back_to_post_idea_number(
                message,
                state,
            )

        self.assertEqual(
            state.state,
            post_ideas.EditPostIdea.waiting_for_idea_number,
        )
        self.assertIn("1. 💡 Первая идея", message.answers[-1][0])

    async def test_stale_edit_number_refreshes_list_without_writing(self):
        message = FakeMessage("Новый текст")
        state = FakeState(
            data={
                "idea_number": 2,
                "selected_idea": "💡 Удалённая идея",
            },
            state=post_ideas.EditPostIdea.waiting_for_new_idea_text,
        )
        save_all_post_ideas = Mock()

        with (
            patch.object(
                post_ideas,
                "load_post_ideas",
                return_value=["💡 Оставшаяся идея"],
            ),
            patch.object(
                post_ideas,
                "save_all_post_ideas",
                save_all_post_ideas,
            ),
        ):
            await post_ideas.save_edited_post_idea(
                message,
                state,
            )

        save_all_post_ideas.assert_not_called()
        self.assertEqual(
            state.state,
            post_ideas.EditPostIdea.waiting_for_idea_number,
        )
        self.assertIn("Список идей изменился", message.answers[-1][0])

    async def test_replaced_idea_at_same_number_is_not_modified(self):
        message = FakeMessage("Новый текст")
        state = FakeState(
            data={
                "idea_number": 1,
                "selected_idea": "💡 Изначальная идея",
            },
            state=post_ideas.EditPostIdea.waiting_for_new_idea_text,
        )
        save_all_post_ideas = Mock()

        with (
            patch.object(
                post_ideas,
                "load_post_ideas",
                return_value=["💡 Другая идея"],
            ),
            patch.object(
                post_ideas,
                "save_all_post_ideas",
                save_all_post_ideas,
            ),
        ):
            await post_ideas.save_edited_post_idea(
                message,
                state,
            )

        save_all_post_ideas.assert_not_called()
        self.assertEqual(
            state.state,
            post_ideas.EditPostIdea.waiting_for_idea_number,
        )


class ClientFsmTests(unittest.IsolatedAsyncioTestCase):
    async def test_client_creation_uses_fsm_until_completion(self):
        state = FakeState()
        save_clients = Mock()

        with (
            patch.object(clients, "clients", []),
            patch.object(clients, "save_clients", save_clients),
        ):
            await clients.ask_client_name(
                FakeMessage("➕ Добавить клиента"),
                state,
            )

            for value in (
                "Анна",
                "Иванова",
                "+372000000",
                "@anna",
                "anna@example.com",
                "Тестовый клиент",
            ):
                await clients.handle_client_text(
                    FakeMessage(value),
                    state,
                )

            self.assertEqual(len(clients.clients), 1)
            self.assertEqual(
                clients.clients[0]["name"],
                "Анна",
            )

        save_clients.assert_called_once_with()
        self.assertTrue(state.cleared)
        self.assertEqual(state.data, {})

    async def test_back_from_client_flow_is_not_intercepted(self):
        active_state = clients.ClientFlow.waiting_for_name.state
        post_ideas_filter = get_state_filters(
            post_ideas.router,
            post_ideas.back,
        )[0]
        client_filters = get_state_filters(
            clients.router,
            clients.back,
        )

        self.assertFalse(
            await post_ideas_filter(
                None,
                raw_state=active_state,
            )
        )
        client_filter_matches = [
            await state_filter(
                None,
                raw_state=active_state,
            )
            for state_filter in client_filters
        ]
        self.assertIn(True, client_filter_matches)

        state = FakeState(
            data={"new_client": {"name": "Анна"}},
            state=clients.ClientFlow.waiting_for_last_name,
        )
        message = FakeMessage("⬅️ Назад")

        await clients.back(message, state)

        self.assertTrue(state.cleared)
        self.assertEqual(state.data, {})

    async def test_two_users_have_independent_client_states(self):
        storage = MemoryStorage()
        first_state = FSMContext(
            storage=storage,
            key=StorageKey(
                bot_id=1,
                chat_id=100,
                user_id=1,
            ),
        )
        second_state = FSMContext(
            storage=storage,
            key=StorageKey(
                bot_id=1,
                chat_id=200,
                user_id=2,
            ),
        )

        await clients.ask_client_name(
            FakeMessage("➕ Добавить клиента"),
            first_state,
        )
        await clients.ask_client_name(
            FakeMessage("➕ Добавить клиента"),
            second_state,
        )
        await clients.handle_client_text(
            FakeMessage("Анна"),
            first_state,
        )

        self.assertEqual(
            await first_state.get_state(),
            clients.ClientFlow.waiting_for_last_name.state,
        )
        self.assertEqual(
            await second_state.get_state(),
            clients.ClientFlow.waiting_for_name.state,
        )
        self.assertEqual(
            (await first_state.get_data())["new_client"],
            {"name": "Анна"},
        )
        self.assertEqual(
            (await second_state.get_data())["new_client"],
            {},
        )


class StartHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_clears_active_state_and_data(self):
        state = FakeState(
            data={"selected_ideas": ["Идея"]},
            state=content_plan.CreateContentPlan.waiting_for_brief,
        )
        message = FakeMessage("/start")

        await start_handler.start(message, state)

        self.assertTrue(state.cleared)
        self.assertEqual(state.data, {})
        self.assertIs(
            message.answers[-1][1]["reply_markup"],
            start_handler.main_menu,
        )


class ContentPlanIdeaSnapshotTests(unittest.IsolatedAsyncioTestCase):
    async def test_reordered_file_does_not_change_button_meaning(self):
        displayed_ideas = ["Идея A", "Идея B"]
        current_ideas = ["Идея B", "Идея A"]
        state = FakeState(
            data={
                "post_idea_choices": displayed_ideas,
                "selected_ideas": [],
            },
            state=content_plan.CreateContentPlan.waiting_for_ideas,
        )

        with patch.object(
            content_plan,
            "load_post_ideas",
            return_value=current_ideas,
        ):
            await content_plan.select_ideas_for_new_plan(
                FakeMessage("▫️ 1"),
                state,
            )

        self.assertEqual(state.data["selected_ideas"], ["Идея A"])
        self.assertEqual(
            state.data["post_idea_choices"],
            displayed_ideas,
        )

    async def test_removed_snapshot_idea_is_not_replaced_by_current_number(self):
        displayed_ideas = ["Старая 1", "Старая 2"]
        current_ideas = ["Новая 1", "Новая 2"]
        state = FakeState(
            data={
                "post_idea_choices": displayed_ideas,
                "selected_ideas": [],
            },
            state=content_plan.CreateContentPlan.waiting_for_ideas,
        )
        message = FakeMessage("▫️ 2")

        with patch.object(
            content_plan,
            "load_post_ideas",
            return_value=current_ideas,
        ):
            await content_plan.select_ideas_for_new_plan(
                message,
                state,
            )

        self.assertEqual(state.data["selected_ideas"], [])
        self.assertEqual(
            state.data["post_idea_choices"],
            current_ideas,
        )
        self.assertIn("Список идей изменился", message.answers[0][0])

    async def test_create_revalidates_selected_ideas_before_generation(self):
        state = FakeState(
            data={
                "selected_client": None,
                "selected_ideas": ["Удалённая идея"],
            },
            state=content_plan.CreateContentPlan.waiting_for_brief,
        )
        build_content_plan_text = AsyncMock()

        with (
            patch.object(
                content_plan,
                "load_post_ideas",
                return_value=["Актуальная идея"],
            ),
            patch.object(
                content_plan,
                "build_content_plan_text",
                build_content_plan_text,
            ),
        ):
            await content_plan.create_content_plan(
                FakeMessage("Короткий бриф"),
                state,
            )

        build_content_plan_text.assert_not_awaited()
        self.assertEqual(
            state.state,
            content_plan.CreateContentPlan.waiting_for_ideas,
        )
        self.assertEqual(state.data["selected_ideas"], [])

    async def test_edit_revalidates_selected_ideas_before_generation(self):
        selected_plan = "Сохранённый план"
        state = FakeState(
            data={
                "content_plan_number": 1,
                "selected_content_plan": selected_plan,
                "selected_client": None,
                "selected_ideas": ["Удалённая идея"],
            },
            state=content_plan.EditContentPlan.waiting_for_new_brief,
        )
        build_content_plan_text = AsyncMock()

        with (
            patch.object(
                content_plan,
                "read_content_plans",
                return_value=[selected_plan],
            ),
            patch.object(
                content_plan,
                "load_post_ideas",
                return_value=["Актуальная идея"],
            ),
            patch.object(
                content_plan,
                "build_content_plan_text",
                build_content_plan_text,
            ),
        ):
            await content_plan.edit_content_plan(
                FakeMessage("Новый бриф"),
                state,
            )

        build_content_plan_text.assert_not_awaited()
        self.assertEqual(
            state.state,
            content_plan.EditContentPlan.waiting_for_ideas,
        )
        self.assertEqual(state.data["selected_ideas"], [])

    async def test_create_revalidates_ideas_after_generation_before_save(self):
        state = FakeState(
            data={
                "selected_client": None,
                "selected_ideas": ["Выбранная идея"],
            },
            state=content_plan.CreateContentPlan.waiting_for_brief,
        )
        save_content_plans = Mock()

        with (
            patch.object(
                content_plan,
                "load_post_ideas",
                side_effect=[
                    ["Выбранная идея"],
                    [],
                ],
            ),
            patch.object(
                content_plan,
                "build_content_plan_text",
                new=AsyncMock(return_value="Новый план"),
            ),
            patch.object(
                content_plan,
                "save_content_plans",
                save_content_plans,
            ),
        ):
            await content_plan.create_content_plan(
                FakeMessage("Короткий бриф"),
                state,
            )

        save_content_plans.assert_not_called()
        self.assertEqual(
            state.state,
            content_plan.CreateContentPlan.waiting_for_ideas,
        )

    async def test_edit_revalidates_ideas_after_generation_before_save(self):
        selected_plan = "Сохранённый план"
        state = FakeState(
            data={
                "content_plan_number": 1,
                "selected_content_plan": selected_plan,
                "selected_client": None,
                "selected_ideas": ["Выбранная идея"],
            },
            state=content_plan.EditContentPlan.waiting_for_new_brief,
        )
        save_content_plans = Mock()

        with (
            patch.object(
                content_plan,
                "read_content_plans",
                return_value=[selected_plan],
            ),
            patch.object(
                content_plan,
                "load_post_ideas",
                side_effect=[
                    ["Выбранная идея"],
                    [],
                ],
            ),
            patch.object(
                content_plan,
                "build_content_plan_text",
                new=AsyncMock(return_value="Обновлённый план"),
            ),
            patch.object(
                content_plan,
                "save_content_plans",
                save_content_plans,
            ),
        ):
            await content_plan.edit_content_plan(
                FakeMessage("Новый бриф"),
                state,
            )

        save_content_plans.assert_not_called()
        self.assertEqual(
            state.state,
            content_plan.EditContentPlan.waiting_for_ideas,
        )


if __name__ == "__main__":
    unittest.main()
