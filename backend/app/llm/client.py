"""LLM call for the FinAlly chat assistant (PLAN.md section 9, "How It Works").

Calls LiteLLM -> OpenRouter -> `openrouter/openai/gpt-oss-120b` with Cerebras as
the inference provider, requesting structured output parsed into `ChatResponse`.
`LLM_MOCK=true` bypasses the network call entirely (see `mock.py`).
"""

from __future__ import annotations

import os

from litellm import acompletion

from .mock import mock_complete
from .prompt import build_messages
from .schema import ChatResponse

MODEL = "openrouter/openai/gpt-oss-120b"
EXTRA_BODY = {"provider": {"order": ["cerebras"]}}


def _mock_enabled() -> bool:
    return os.environ.get("LLM_MOCK", "false").lower() == "true"


async def complete(
    user_message: str,
    portfolio_context: dict,
    history: list[dict],
    failures: list[dict] | None = None,
) -> ChatResponse:
    """Get the assistant's structured reply to `user_message`.

    `portfolio_context` is `services.portfolio.get_portfolio()` plus a
    `watchlist` key. `history` is prior chat messages, oldest-first,
    `{"role", "content"}`, at most 50. `failures` carries action failures from
    a first pass (PLAN.md section 9 step 7) so the model can explain them.
    """
    if _mock_enabled():
        return mock_complete(user_message, failures)

    messages = build_messages(user_message, portfolio_context, history, failures)
    response = await acompletion(
        model=MODEL,
        messages=messages,
        response_format=ChatResponse,
        reasoning_effort="low",
        extra_body=EXTRA_BODY,
    )
    content = response.choices[0].message.content
    return ChatResponse.model_validate_json(content)
