"""Prompt building + response parsing for the Idea Rater.

Pure functions in this file take a `call_llm`-shaped function as a
parameter so they can be unit tested with a fake instead of the real API.
"""
import json
from dataclasses import dataclass, field

from llm_client import call_llm as default_call_llm

SYSTEM_PROMPT = (
    "You are a sharp, honest startup advisor helping a product manager stress-test "
    "an idea. You are supportive but not a pushover - you point out real risks, "
    "not just encouragement. You always respond with valid JSON matching the "
    "schema you are given, and nothing else - no markdown fences, no commentary."
)


class IdeaRatingError(RuntimeError):
    """Raised when the model's response can't be parsed."""


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


def _parse_json(text: str):
    cleaned = _strip_code_fence(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise IdeaRatingError(f"The model did not return valid JSON: {exc}\n\nRaw response:\n{text}") from exc


QUESTIONS_SCHEMA_HINT = '{"questions": ["string", "..."]}'


def build_questions_prompt(idea: str) -> str:
    return f"""A product manager has this idea:

"{idea.strip()}"

Ask 3-5 clarifying questions that would most change your assessment of this
idea - things like who the target user is, what problem it solves for them,
how they'd discover/pay for it, or what the biggest untested assumption is.
Keep each question short (one sentence).

Respond with ONLY a JSON object matching this schema:
{QUESTIONS_SCHEMA_HINT}
"""


def parse_questions_json(text: str) -> list[str]:
    data = _parse_json(text)
    if "questions" not in data or not isinstance(data["questions"], list):
        raise IdeaRatingError("The model's response is missing a 'questions' list")
    questions = [q for q in data["questions"] if str(q).strip()]
    if not questions:
        raise IdeaRatingError("The model returned zero questions")
    return questions


def generate_questions(idea: str, call_llm=default_call_llm) -> list[str]:
    if not idea.strip():
        raise ValueError("idea must not be empty")
    prompt = build_questions_prompt(idea)
    response_text = call_llm(prompt, system=SYSTEM_PROMPT)
    return parse_questions_json(response_text)


RATING_SCHEMA_HINT = """{
  "pros": ["string", "..."],
  "cons": ["string", "..."],
  "score": "integer 1-10, where 10 means you'd invest your own time in this today",
  "rationale": "string - 1-3 sentences explaining the score"
}"""


@dataclass
class Rating:
    pros: list[str]
    cons: list[str]
    score: int
    rationale: str = ""

    def __post_init__(self):
        if not (1 <= self.score <= 10):
            raise IdeaRatingError(f"score must be between 1 and 10, got {self.score}")


def build_rating_prompt(idea: str, qa_pairs: list[tuple[str, str]]) -> str:
    qa_block = "\n".join(f"Q: {q}\nA: {a.strip() or '(no answer given)'}" for q, a in qa_pairs)
    return f"""A product manager pitched this idea:

"{idea.strip()}"

They answered your clarifying questions:
{qa_block}

Give a balanced pros-and-cons list grounded in their answers (not generic
startup advice), and an honest score from 1-10. Respond with ONLY a JSON
object matching this schema:
{RATING_SCHEMA_HINT}
"""


def parse_rating_json(text: str) -> Rating:
    data = _parse_json(text)
    missing = [k for k in ("pros", "cons", "score") if k not in data]
    if missing:
        raise IdeaRatingError(f"The model's JSON is missing required fields: {missing}")
    return Rating(
        pros=list(data["pros"]),
        cons=list(data["cons"]),
        score=int(data["score"]),
        rationale=data.get("rationale", ""),
    )


def rate_idea(idea: str, qa_pairs: list[tuple[str, str]], call_llm=default_call_llm) -> Rating:
    if not idea.strip():
        raise ValueError("idea must not be empty")
    prompt = build_rating_prompt(idea, qa_pairs)
    response_text = call_llm(prompt, system=SYSTEM_PROMPT)
    return parse_rating_json(response_text)
