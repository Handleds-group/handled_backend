from __future__ import annotations

import os

from openai import OpenAI


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

FREE_MODEL = "anthropic/claude-3.5-haiku"
PRO_MODEL = "anthropic/claude-3.5-haiku"
PREMIUM_MODEL = "deepseek/deepseek-chat"


client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url=OPENROUTER_BASE_URL,
)
