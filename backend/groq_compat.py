import logging
import re
import time
from functools import lru_cache
from types import SimpleNamespace
from typing import Callable, TypeVar

import httpx
from groq import AsyncGroq, Groq, RateLimitError
from langchain_groq import ChatGroq
from langchain_community.llms import Ollama

from backend.config import config


DEFAULT_GROQ_TIMEOUT = httpx.Timeout(60.0, connect=10.0)
RETRY_AFTER_SECONDS_PATTERN = re.compile(
    r"Please try again in (?:(?P<minutes>\d+)m)?(?P<seconds>\d+(?:\.\d+)?)s",
    re.IGNORECASE,
)

logger = logging.getLogger(__name__)
T = TypeVar("T")


def _build_ollama_prompt(messages: list[dict]) -> str:
    prompt_parts = []
    system_messages = [
        message.get("content", "").strip()
        for message in messages
        if message.get("role") == "system" and message.get("content")
    ]
    if system_messages:
        prompt_parts.append("\n\n".join(system_messages))

    for message in messages:
        role = message.get("role")
        content = (message.get("content") or "").strip()
        if not content or role == "system":
            continue
        prompt_parts.append(f"{role.title()}:\n{content}")

    return "\n\n".join(prompt_parts).strip()


def _wrap_text_as_chat_completion(text: str):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=text)
            )
        ]
    )


@lru_cache
def get_ollama_llm(model: str | None = None) -> Ollama:
    return Ollama(
        model=model or config.OLLAMA_CHAT_MODEL,
        base_url=config.OLLAMA_BASE_URL,
        temperature=0,
        timeout=config.OLLAMA_REQUEST_TIMEOUT_SECONDS,
    )


def create_ollama_chat_completion(**kwargs):
    prompt = _build_ollama_prompt(kwargs.get("messages", []))
    text = get_ollama_llm().invoke(
        prompt,
        temperature=kwargs.get("temperature", 0),
    )
    return _wrap_text_as_chat_completion(str(text))


def _require_groq_api_key() -> str:
    if not config.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set.")
    return config.GROQ_API_KEY


def _parse_retry_after_seconds(error: RateLimitError) -> float | None:
    response = getattr(error, "response", None)
    if response is not None:
        retry_after = response.headers.get("retry-after")
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass

    match = RETRY_AFTER_SECONDS_PATTERN.search(str(error))
    if not match:
        return None

    minutes = int(match.group("minutes") or 0)
    seconds = float(match.group("seconds"))
    return minutes * 60 + seconds


def _get_retry_delay_seconds(error: RateLimitError, attempt: int) -> float:
    parsed_delay = _parse_retry_after_seconds(error)
    if parsed_delay is not None:
        return min(parsed_delay + 1.0, config.GROQ_RETRY_MAX_SECONDS)

    exponential_delay = config.GROQ_RETRY_BASE_SECONDS * (2 ** attempt)
    return min(exponential_delay, config.GROQ_RETRY_MAX_SECONDS)


def with_groq_retries(
    operation: str,
    func: Callable[[], T],
) -> T:
    max_retries = max(0, config.GROQ_MAX_RETRIES)

    for attempt in range(max_retries + 1):
        try:
            return func()
        except RateLimitError as exc:
            if attempt >= max_retries:
                logger.error(
                    "Groq rate limit persisted during %s after %s retries: %s",
                    operation,
                    max_retries,
                    exc,
                )
                raise

            delay_seconds = _get_retry_delay_seconds(exc, attempt)
            logger.warning(
                "Groq rate limit during %s. Waiting %.1fs before retry %s/%s.",
                operation,
                delay_seconds,
                attempt + 1,
                max_retries,
            )
            time.sleep(delay_seconds)

    raise RuntimeError(f"Unreachable retry state for {operation}")


def create_chat_completion(**kwargs):
    provider = (config.LLM_PROVIDER or "ollama").strip().lower()

    if provider == "ollama":
        return create_ollama_chat_completion(**kwargs)

    try:
        return with_groq_retries(
            operation=f"chat.completions.create(model={kwargs.get('model')})",
            func=lambda: get_groq_client().chat.completions.create(**kwargs),
        )
    except RateLimitError:
        logger.warning(
            "Falling back to local Ollama model %s after Groq rate limit.",
            config.OLLAMA_CHAT_MODEL,
        )
        return create_ollama_chat_completion(**kwargs)


@lru_cache
def get_groq_client() -> Groq:
    # groq==0.5.0 is not compatible with httpx 0.28's removed `proxies` arg
    # unless we inject our own client.
    return Groq(
        api_key=_require_groq_api_key(),
        max_retries=0,
        http_client=httpx.Client(timeout=DEFAULT_GROQ_TIMEOUT)
    )


@lru_cache
def get_async_groq_client() -> AsyncGroq:
    return AsyncGroq(
        api_key=_require_groq_api_key(),
        max_retries=0,
        http_client=httpx.AsyncClient(timeout=DEFAULT_GROQ_TIMEOUT)
    )


@lru_cache
def get_chat_groq(model: str | None = None) -> ChatGroq:
    return ChatGroq(
        model=model or config.GENERATION_MODEL,
        api_key=_require_groq_api_key(),
        temperature=0,
        client=get_groq_client().chat.completions,
        async_client=get_async_groq_client().chat.completions
    )
