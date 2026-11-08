"""`TextModel` implementations. LangChain stays behind this file."""

from __future__ import annotations

from typing import Any

from vacuole.ports import TextModel


class LangChainTextModel:
    """Adapts any LangChain chat model (Groq, Gemini, ...) to `TextModel`."""

    def __init__(self, chat_model: Any):
        self._model = chat_model

    async def complete(self, prompt: str) -> str:
        response = await self._model.ainvoke(prompt)
        return str(response.content)


class FallbackTextModel:
    """Try `primary`; if it raises, answer with `fallback` instead."""

    def __init__(self, primary: TextModel, fallback: TextModel, *, name: str = "model"):
        self._primary = primary
        self._fallback = fallback
        self._name = name

    async def complete(self, prompt: str) -> str:
        try:
            return await self._primary.complete(prompt)
        except Exception as exc:
            print(f"[{self._name}] primary model failed: {exc}")
            return await self._fallback.complete(prompt)
