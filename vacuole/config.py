"""All environment access in one place.

Everything else receives plain values (or a `Settings`) instead of calling `os.getenv`,
which keeps modules importable and testable without a configured environment.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from dotenv import load_dotenv

_FIREBASE_KEYS = (
    "type",
    "project_id",
    "private_key_id",
    "private_key",
    "client_email",
    "client_id",
    "auth_uri",
    "token_uri",
    "auth_provider_x509_cert_url",
    "client_x509_cert_url",
    "universe_domain",
)


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _firebase_credentials() -> dict[str, Any]:
    credentials: dict[str, Any] = {key: os.getenv(key) for key in _FIREBASE_KEYS}
    credentials["private_key"] = os.getenv("private_key", "").replace("\\n", "\n")
    return credentials


@dataclass(frozen=True)
class Settings:
    telegram_token: str = ""
    bot_username: str = ""
    webhook_url: str = ""
    port: int = 8443

    groq_api_key: str = ""
    groq_chat_api_key: str = ""
    # Groq retires models without notice -- gemma2-9b-it and deepseek-r1-distill-llama-70b
    # were both decommissioned under this project. Keep the ids in env so the next
    # retirement is a config change. `curl https://api.groq.com/openai/v1/models` lists
    # what the key can currently reach.
    fast_model: str = "qwen/qwen3.8-27b"
    chat_model: str = "openai/gpt-oss-120b"
    fast_max_tokens: int = 700

    serpapi_api_key: str = ""
    firebase_credentials: dict[str, Any] = field(default_factory=dict, repr=False)

    history_limit: int = 10          # turns loaded from storage
    max_history_messages: int = 6    # turns shown to the model
    max_products: int = 8

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        groq_key = _env("GROQ_API_KEY")
        return cls(
            telegram_token=_env("TOKEN"),
            bot_username=_env("BOT_USERNAME"),
            webhook_url=_env("WEBHOOK_URL"),
            port=int(_env("PORT", "8443")),
            groq_api_key=groq_key,
            # A blank second key falls back to the first; an invalid one only shows up
            # at call time, where the chat model falls back to the fast one.
            groq_chat_api_key=_env("GROQ2_API_KEY") or groq_key,
            fast_model=_env("GROQ_FAST_MODEL", cls.fast_model),
            chat_model=_env("GROQ_CHAT_MODEL", cls.chat_model),
            fast_max_tokens=int(_env("GROQ_FAST_MAX_TOKENS", str(cls.fast_max_tokens))),
            serpapi_api_key=_env("SERPAPI_API_KEY") or _env("SERP_API_KEY"),
            firebase_credentials=_firebase_credentials(),
        )
