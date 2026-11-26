import asyncio
import importlib.util
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

if importlib.util.find_spec("pydantic_settings") is None:
    raise unittest.SkipTest("Gemini resilience tests require backend dependencies.")

from google.genai.errors import APIError

from backend.config import Settings
from backend.services import ai_provider


class GeminiResilienceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.provider = ai_provider.GeminiProvider.__new__(ai_provider.GeminiProvider)
        self.provider.settings = Settings(
            _env_file=None,
            GEMINI_REASONING_MODEL="gemini-4-hydrogen",
            GEMINI_REASONING_FALLBACK_MODEL="gemini-3.5-flash-lite",
        )
        self.generate = AsyncMock()
        self.provider.client = SimpleNamespace(
            aio=SimpleNamespace(models=SimpleNamespace(generate_content=self.generate))
        )
        self.draft = SimpleNamespace(text='{"replacement_code":"pass","rationale":"example"}')

    async def test_retries_primary_then_falls_back_once(self):
        self.generate.side_effect = [APIError(503, {}), APIError(503, {}), self.draft]
        with patch.object(ai_provider.asyncio, "sleep", new_callable=AsyncMock) as sleep:
            with self.assertLogs(ai_provider.logger, "INFO") as logs:
                result = await self.provider.draft_function_patch({}, "", {})
        sleep.assert_awaited_once()
        self.assertEqual([call.kwargs["model"] for call in self.generate.await_args_list],
                         ["gemini-4-hydrogen", "gemini-4-hydrogen", "gemini-3.5-flash-lite"])
        self.assertIn("gemini-3.5-flash-lite", logs.output[0])
        self.assertEqual(result, {"replacement_code": "pass", "rationale": "example"})

    async def test_other_http_errors_do_not_retry_or_fall_back(self):
        self.generate.side_effect = APIError(400, {})
        with self.assertRaises(APIError):
            await self.provider.draft_function_patch({}, "", {})
        self.generate.assert_awaited_once()

    async def test_low_remaining_budget_skips_retry_and_fallback(self):
        self.generate.side_effect = APIError(503, {})
        with patch.object(ai_provider, "PATCH_DRAFT_TIMEOUT_SECONDS", 1):
            with self.assertRaises(APIError):
                await self.provider.draft_function_patch({}, "", {})
        self.generate.assert_awaited_once()

    async def test_single_deadline_cancels_stalled_draft(self):
        async def stall(**kwargs):
            await asyncio.Event().wait()

        self.generate.side_effect = stall
        with patch.object(ai_provider, "PATCH_DRAFT_TIMEOUT_SECONDS", 0.02):
            with self.assertRaisesRegex(TimeoutError, "patch drafting exceeded"):
                await self.provider.draft_function_patch({}, "", {})
        self.generate.assert_awaited_once()
