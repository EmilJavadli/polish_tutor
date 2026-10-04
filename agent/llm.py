"""Thin wrapper around the OpenAI client."""
import json
from collections.abc import Iterator
from functools import lru_cache

from openai import OpenAI

from config import LLM_MODEL, OPENAI_API_KEY


@lru_cache(maxsize=1)
def get_client() -> OpenAI:
    """Return a cached OpenAI client."""
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set. Add it to your .env file.")
    return OpenAI(api_key=OPENAI_API_KEY)


def chat_json(messages: list[dict]) -> dict:
    """Call the model in JSON mode and return the parsed object.

    Raises:
        json.JSONDecodeError: if the model returns invalid JSON.
    """
    response = get_client().chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content or ""
    return json.loads(content)


def chat_stream(messages: list[dict]) -> Iterator[str]:
    """Stream a plain-text chat response token by token."""
    stream = get_client().chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        stream=True,
    )
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
