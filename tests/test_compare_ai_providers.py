import io
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

from scripts import compare_ai_providers as compare
from services import content_plan as content_plan_service
from services import post_ideas as post_ideas_service
from services import write_post as write_post_service


class CompareAiProvidersTests(unittest.TestCase):
    def run_comparison(self, mode, providers=None):
        output = io.StringIO()

        with redirect_stdout(output):
            results = compare.run_comparison(mode, providers)

        return results, output.getvalue()

    def test_content_plan_runs_all_expected_providers(self):
        with (
            patch.dict(
                os.environ,
                {
                    "OPENAI_API_KEY": "openai-test-key",
                    "GEMINI_API_KEY": "gemini-test-key",
                    "GROQ_API_KEY": "groq-test-key",
                },
                clear=False,
            ),
            patch.object(
                compare.content_plan_openai_service,
                "generate_ai_content_plan",
                return_value="OpenAI plan",
            ) as openai,
            patch.object(
                compare.content_plan_gemini_service,
                "generate_gemini_content_plan",
                return_value="Gemini plan",
            ) as gemini,
            patch.object(
                compare.content_plan_groq_service,
                "generate_groq_content_plan",
                return_value="Groq plan",
            ) as groq,
        ):
            results, output = self.run_comparison("content_plan")

        self.assertEqual(
            [result.provider for result in results],
            ["openai", "gemini", "groq"],
        )
        self.assertEqual(
            [result.status for result in results],
            ["OK", "OK", "OK"],
        )
        self.assertIn("=== CONTENT_PLAN ===", output)
        self.assertIn("Time:", output)
        openai.assert_called_once()
        gemini.assert_called_once()
        groq.assert_called_once()
        self.assertEqual(
            openai.call_args.args,
            gemini.call_args.args,
        )
        self.assertEqual(
            gemini.call_args.args,
            groq.call_args.args,
        )

    def test_write_post_runs_only_gemini_and_groq(self):
        with (
            patch.dict(
                os.environ,
                {
                    "GEMINI_API_KEY": "gemini-test-key",
                    "GROQ_API_KEY": "groq-test-key",
                },
                clear=False,
            ),
            patch.object(
                compare.write_post_gemini_service,
                "generate_gemini_post",
                return_value="Gemini post",
            ) as gemini,
            patch.object(
                compare.write_post_groq_service,
                "generate_groq_post",
                return_value="Groq post",
            ) as groq,
        ):
            results, _ = self.run_comparison("write_post")

        self.assertEqual(
            [result.provider for result in results],
            ["gemini", "groq"],
        )
        self.assertEqual(gemini.call_args.args, groq.call_args.args)
        self.assertEqual(gemini.call_args.args[1], compare.WRITE_POST_TOPIC)
        self.assertEqual(gemini.call_args.args[2], compare.WRITE_POST_STYLE)

    def test_post_ideas_runs_only_gemini_and_groq(self):
        with (
            patch.dict(
                os.environ,
                {
                    "GEMINI_API_KEY": "gemini-test-key",
                    "GROQ_API_KEY": "groq-test-key",
                },
                clear=False,
            ),
            patch.object(
                compare.post_ideas_gemini_service,
                "generate_gemini_post_ideas",
                return_value="Gemini ideas",
            ) as gemini,
            patch.object(
                compare.post_ideas_groq_service,
                "generate_groq_post_ideas",
                return_value="Groq ideas",
            ) as groq,
        ):
            results, _ = self.run_comparison("post_ideas")

        self.assertEqual(
            [result.provider for result in results],
            ["gemini", "groq"],
        )
        self.assertEqual(gemini.call_args.args, groq.call_args.args)
        self.assertEqual(
            gemini.call_args.args[1],
            compare.POST_IDEAS_BRIEF,
        )
        self.assertEqual(
            gemini.call_args.args[2],
            compare.POST_IDEAS_EXISTING,
        )

    def test_provider_error_does_not_stop_other_providers(self):
        error = content_plan_service.ContentPlanGenerationError(
            "OpenAI временно недоступен"
        )

        with (
            patch.dict(
                os.environ,
                {
                    "OPENAI_API_KEY": "openai-test-key",
                    "GEMINI_API_KEY": "gemini-test-key",
                    "GROQ_API_KEY": "groq-test-key",
                },
                clear=False,
            ),
            patch.object(
                compare.content_plan_openai_service,
                "generate_ai_content_plan",
                side_effect=error,
            ),
            patch.object(
                compare.content_plan_gemini_service,
                "generate_gemini_content_plan",
                return_value="Gemini plan",
            ),
            patch.object(
                compare.content_plan_groq_service,
                "generate_groq_content_plan",
                return_value="Groq plan",
            ),
        ):
            results, output = self.run_comparison("content_plan")

        self.assertEqual(
            [result.status for result in results],
            ["ERROR", "OK", "OK"],
        )
        self.assertIn("OpenAI временно недоступен", output)
        self.assertIn("Gemini plan", output)
        self.assertIn("Groq plan", output)

    def test_missing_keys_skip_provider_without_crash(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(
                compare.write_post_gemini_service,
                "generate_gemini_post",
            ) as gemini,
            patch.object(
                compare.write_post_groq_service,
                "generate_groq_post",
            ) as groq,
        ):
            results, output = self.run_comparison("write_post")

        self.assertEqual(
            [result.status for result in results],
            ["SKIPPED", "SKIPPED"],
        )
        self.assertIn("GEMINI_API_KEY not configured", output)
        self.assertIn("GROQ_API_KEY not configured", output)
        gemini.assert_not_called()
        groq.assert_not_called()

    def test_elapsed_time_is_stored_and_printed(self):
        with (
            patch.dict(
                os.environ,
                {"GEMINI_API_KEY": "gemini-test-key"},
                clear=False,
            ),
            patch.object(
                compare.write_post_gemini_service,
                "generate_gemini_post",
                return_value="Post",
            ),
            patch.object(
                compare.time,
                "perf_counter",
                side_effect=[10.0, 12.25],
            ),
        ):
            results, output = self.run_comparison(
                "write_post",
                ["gemini"],
            )

        self.assertEqual(results[0].elapsed_seconds, 2.25)
        self.assertIn("Time: 2.25s", output)

    def test_harness_never_uses_storage_and_fake_data_has_no_private_fields(self):
        with (
            patch.dict(
                os.environ,
                {
                    "GEMINI_API_KEY": "gemini-test-key",
                    "GROQ_API_KEY": "groq-test-key",
                },
                clear=False,
            ),
            patch.object(
                compare.post_ideas_gemini_service,
                "generate_gemini_post_ideas",
                return_value="Gemini ideas",
            ),
            patch.object(
                compare.post_ideas_groq_service,
                "generate_groq_post_ideas",
                return_value="Groq ideas",
            ),
            patch.object(
                post_ideas_service.post_ideas_storage,
                "save_all_post_ideas",
            ) as save_ideas,
            patch.object(
                write_post_service.posts_storage,
                "save_posts",
            ) as save_posts,
            patch.object(
                content_plan_service.content_plans_storage,
                "save_content_plans",
            ) as save_content_plans,
        ):
            self.run_comparison("post_ideas")

        self.assertNotIn("phone", compare.TEST_CLIENT)
        self.assertNotIn("email", compare.TEST_CLIENT)
        self.assertNotIn("+", str(compare.TEST_CLIENT))
        save_ideas.assert_not_called()
        save_posts.assert_not_called()
        save_content_plans.assert_not_called()

    def test_unexpected_error_is_formatted_without_secret(self):
        with (
            patch.dict(
                os.environ,
                {"GROQ_API_KEY": "super-secret-key"},
                clear=False,
            ),
            patch.object(
                compare.write_post_groq_service,
                "generate_groq_post",
                side_effect=RuntimeError("super-secret-key"),
            ),
        ):
            results, output = self.run_comparison(
                "write_post",
                ["groq"],
            )

        self.assertEqual(results[0].status, "ERROR")
        self.assertEqual(
            results[0].error,
            "Непредвиденная ошибка: RuntimeError",
        )
        self.assertNotIn("super-secret-key", output)


if __name__ == "__main__":
    unittest.main()
