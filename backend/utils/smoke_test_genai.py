"""Check live Gemini access using minimal prompts and no repository content."""

import asyncio

import httpx
from google.genai import types
from google.genai.errors import APIError

if __package__ == "backend.utils":
    from ..config import Settings
    from ..services.ai_provider import GeminiProvider
else:
    from config import Settings
    from services.ai_provider import GeminiProvider


async def smoke_test() -> int:
    settings = Settings()
    if not settings.GEMINI_API_KEY:
        print("Set GEMINI_API_KEY locally before running the Gemini smoke test.")
        return 2

    provider = GeminiProvider(settings)
    checks = (
        ("reasoning", settings.GEMINI_REASONING_MODEL),
        ("summary", settings.GEMINI_SUMMARY_MODEL),
        ("embedding", settings.GEMINI_EMBEDDING_MODEL),
    )
    async def check(purpose: str, model: str) -> bool:
        try:
            async with asyncio.timeout(20):
                if purpose == "embedding":
                    await provider.embed_texts(["CodeScape setup check"])
                else:
                    config = types.GenerateContentConfig(max_output_tokens=256)
                    if purpose == "reasoning" and model.removeprefix("models/").startswith("gemini-3."):
                        config.thinking_config = types.ThinkingConfig(thinking_level="LOW")
                    response = await provider.client.aio.models.generate_content(
                        model=model,
                        contents="Reply with the word ready.",
                        config=config,
                    )
                    if not response.text:
                        raise ValueError("Empty generation response")
            print(f"{purpose} ({model}) passed")
            return True
        except APIError as exc:
            print(f"{purpose} ({model}) failed with Gemini HTTP {exc.code}")
        except (httpx.HTTPError, TimeoutError, ValueError) as exc:
            print(f"{purpose} ({model}) failed with {type(exc).__name__}")
        return False

    try:
        results = await asyncio.gather(*(check(purpose, model) for purpose, model in checks))
    finally:
        await provider.close()
    return int(not all(results))


if __name__ == "__main__":
    raise SystemExit(asyncio.run(smoke_test()))
