from .base_api import AITranslator
from openai import AsyncOpenAI
from random import randint

import logging, asyncio, os, dotenv

logger = logging.getLogger(__name__)

dotenv.load_dotenv(override=True)

API_KEY = os.getenv("API_KEY")
API_URL = os.getenv("API_URL")
MODEL = os.getenv("MODEL")


class OpenAITranslator(AITranslator):

    def __init__(self, prompt):
        self.prompt = prompt
        self.client = AsyncOpenAI(
            api_key=API_KEY,
            base_url=API_URL,
            max_retries=5,
        )

    async def __call__(self, text: str) -> str:
        """调用 OpenAI API 翻译文本（带冷却时间）"""

        try:
            response = await self.client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": self.prompt},
                    {"role": "user", "content": text},
                ],
                temperature=0.7,
                timeout=30,
                logprobs=False,
            )
            translated_text = response.choices[0].message.content
        except Exception as e:
            logger.error(f"api 请求失败: {e}")
            raise e

        sleep_time = randint(5, 6)
        await asyncio.sleep(sleep_time)

        return f"""{translated_text}"""
