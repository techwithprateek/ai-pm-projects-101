"""Thin wrapper around the OpenAI API.

Kept as a single small function so every other module can depend on a
function signature (`call_llm(prompt, system=..., ...) -> str`) instead of
the OpenAI SDK directly. That's what makes the rest of the app testable
without hitting the real API: tests just pass in a fake function with the
same signature.
"""
import os

from openai import OpenAI

DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5")

# Reasoning models (gpt-5, o-series) spend part of max_completion_tokens on
# hidden reasoning tokens before writing any visible output - on "minimal"
# effort tasks like these (generate JSON from a prompt) that can silently eat
# the whole budget and return an empty response. Capping effort to "minimal"
# keeps that budget for the actual answer. Non-reasoning models don't accept
# this parameter, so it's only sent for models that support it.
REASONING_MODEL_PREFIXES = ("gpt-5", "o1", "o3", "o4")


def call_llm(prompt: str, system: str = "", model: str | None = None, max_tokens: int = 4000) -> str:
    """Send a single-turn prompt to the model and return the text response."""
    client = OpenAI()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    model_name = model or DEFAULT_MODEL
    extra_args = {}
    if model_name.startswith(REASONING_MODEL_PREFIXES):
        extra_args["reasoning_effort"] = "minimal"
    response = client.chat.completions.create(
        model=model_name,
        max_completion_tokens=max_tokens,
        messages=messages,
        **extra_args,
    )
    return response.choices[0].message.content
