import unittest
from collections.abc import Mapping
from unittest.mock import AsyncMock, Mock, patch

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import BaseStorage, StorageKey
from aiogram.fsm.storage.memory import DisabledEventIsolation

import main as bot_main


class FakeRedisClient:
    def __init__(self, unavailable=False):
        self.unavailable = unavailable
        self.closed = False

    async def ping(self):
        if self.unavailable:
            raise ConnectionError("Redis is unavailable")


class FakeRedisStorage(BaseStorage):
    state_by_key = {}
    data_by_key = {}
    created_urls = []
    last_instance = None

    def __init__(self, redis_url, unavailable=False):
        self.redis_url = redis_url
        self.redis = FakeRedisClient(unavailable)
        self.closed = False
        type(self).last_instance = self

    @classmethod
    def from_url(cls, redis_url):
        cls.created_urls.append(redis_url)
        return cls(redis_url)

    def create_isolation(self):
        return DisabledEventIsolation()

    async def close(self):
        self.closed = True
        self.redis.closed = True

    async def set_state(self, key, state=None):
        if state is None:
            self.state_by_key.pop(key, None)
        else:
            self.state_by_key[key] = (
                state.state if hasattr(state, "state") else state
            )

    async def get_state(self, key):
        return self.state_by_key.get(key)

    async def set_data(self, key, data: Mapping):
        if data:
            self.data_by_key[key] = dict(data)
        else:
            self.data_by_key.pop(key, None)

    async def get_data(self, key):
        return dict(self.data_by_key.get(key, {}))


class PersistentFsmStorageTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        FakeRedisStorage.state_by_key = {}
        FakeRedisStorage.data_by_key = {}
        FakeRedisStorage.created_urls = []

    async def test_state_persists_after_new_storage_instance_and_clear(self):
        with patch.object(bot_main, "RedisStorage", FakeRedisStorage):
            first_storage = bot_main.create_fsm_storage("redis://test/0")
            first_context = FSMContext(
                storage=first_storage,
                key=StorageKey(bot_id=1, chat_id=10, user_id=101),
            )
            second_context = FSMContext(
                storage=first_storage,
                key=StorageKey(bot_id=1, chat_id=20, user_id=202),
            )
            await first_context.set_state("Clients:waiting_for_name")
            await first_context.update_data(name="Alice")
            await second_context.set_state("PostIdeas:waiting_for_brief")
            await second_context.update_data(brief="Ideas")
            await first_storage.close()

            reopened_storage = bot_main.create_fsm_storage("redis://test/0")
            reopened_first_context = FSMContext(
                storage=reopened_storage,
                key=StorageKey(bot_id=1, chat_id=10, user_id=101),
            )
            reopened_second_context = FSMContext(
                storage=reopened_storage,
                key=StorageKey(bot_id=1, chat_id=20, user_id=202),
            )

            self.assertEqual(
                await reopened_first_context.get_state(),
                "Clients:waiting_for_name",
            )
            self.assertEqual(
                await reopened_first_context.get_data(), {"name": "Alice"}
            )
            self.assertEqual(
                await reopened_second_context.get_state(),
                "PostIdeas:waiting_for_brief",
            )
            self.assertEqual(
                await reopened_second_context.get_data(), {"brief": "Ideas"}
            )

            await reopened_first_context.clear()
            final_storage = bot_main.create_fsm_storage("redis://test/0")
            final_context = FSMContext(
                storage=final_storage,
                key=StorageKey(bot_id=1, chat_id=10, user_id=101),
            )
            self.assertIsNone(await final_context.get_state())
            self.assertEqual(await final_context.get_data(), {})

    async def test_dispatcher_checks_backend_and_configures_event_isolation(self):
        with patch.object(bot_main, "RedisStorage", FakeRedisStorage):
            dispatcher = await bot_main.create_dispatcher("redis://test/1")

        self.assertEqual(FakeRedisStorage.created_urls, ["redis://test/1"])
        self.assertIsInstance(dispatcher.storage, FakeRedisStorage)
        self.assertIsInstance(
            dispatcher.fsm.events_isolation, DisabledEventIsolation
        )

    async def test_unavailable_backend_closes_storage_and_raises_clear_error(self):
        class UnavailableStorage(FakeRedisStorage):
            @classmethod
            def from_url(cls, redis_url):
                instance = cls(redis_url, unavailable=True)
                cls.last_instance = instance
                return instance

        with patch.object(bot_main, "RedisStorage", UnavailableStorage):
            with self.assertRaisesRegex(
                RuntimeError, "Persistent FSM Redis backend is unavailable"
            ):
                await bot_main.create_dispatcher("redis://test/2")

        self.assertTrue(UnavailableStorage.last_instance.closed)

    def test_missing_url_or_dependency_fails_explicitly(self):
        with self.assertRaisesRegex(RuntimeError, "FSM_REDIS_URL"):
            bot_main.create_fsm_storage("")

        with patch.object(bot_main, "RedisStorage", None):
            with self.assertRaisesRegex(RuntimeError, "redis dependency"):
                bot_main.create_fsm_storage("redis://test/3")

    async def test_startup_does_not_require_ai_provider_keys(self):
        dispatcher = Mock()
        dispatcher.start_polling = AsyncMock()

        with (
            patch.dict(
                "os.environ",
                {
                    "TELEGRAM_BOT_TOKEN": "123456:token",
                    "FSM_REDIS_URL": "redis://test/4",
                },
                clear=True,
            ),
            patch.object(bot_main, "load_dotenv"),
            patch.object(
                bot_main,
                "create_dispatcher",
                AsyncMock(return_value=dispatcher),
            ) as create_dispatcher,
            patch.object(bot_main, "Bot") as bot,
        ):
            await bot_main.main()

        create_dispatcher.assert_awaited_once_with("redis://test/4")
        dispatcher.start_polling.assert_awaited_once_with(bot.return_value)
