"""Prompt building + response parsing for the Weekly Update Writer.

Pure functions in this file take a `call_llm`-shaped function as a
parameter so they can be unit tested with a fake instead of the real API.
"""
import json
from dataclasses import dataclass, field

from llm_client import call_llm as default_call_llm

SYSTEM_PROMPT = (
    "You are a product manager writing a status update for your own manager. "
    "You write in plain, confident language - no corporate filler like "
    "'synergy' or 'leverage', no restating the obvious. You only include "
    "things that are actually in the notes given to you; you never invent "
    "accomplishments or metrics. You always respond with valid JSON matching "
    "the schema you are given, and nothing else - no markdown fences, no "
    "commentary."
)

TONES = ("concise", "detailed")
AUDIENCES = ("manager", "team", "stakeholders")

UPDATE_SCHEMA_HINT = """{
  "accomplishments": ["string", "..."],
  "in_progress": ["string", "..."],
  "blockers": ["string", "..."],
  "next_steps": ["string", "..."]
}"""


class UpdateGenerationError(RuntimeError):
    """Raised when the model's response can't be parsed into an update."""


@dataclass
class WeeklyUpdate:
    accomplishments: list[str]
    in_progress: list[str]
    blockers: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)

    def to_message(self) -> str:
        def section(title, items):
            if not items:
                return ""
            body = "\n".join(f"- {item}" for item in items)
            return f"{title}\n{body}\n"

        parts = [
            section("Accomplishments this week", self.accomplishments),
            section("In progress", self.in_progress),
            section("Blockers", self.blockers),
            section("Next week", self.next_steps),
        ]
        return "\n".join(p for p in parts if p).strip() + "\n"


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


def build_update_prompt(raw_notes: str, tone: str = "concise", audience: str = "manager") -> str:
    if tone not in TONES:
        raise ValueError(f"tone must be one of {TONES}")
    if audience not in AUDIENCES:
        raise ValueError(f"audience must be one of {AUDIENCES}")

    tone_instruction = {
        "concise": "Keep each bullet to one short sentence. Favor brevity over completeness.",
        "detailed": "Bullets can be 1-2 sentences with enough context to stand alone.",
    }[tone]

    return f"""Turn these rough weekly notes into a status update for {audience}.

ROUGH NOTES:
{raw_notes.strip()}

{tone_instruction}
Group items into accomplishments (done this week), in_progress (started but
not done), blockers (things stuck or needing help), and next_steps (planned
for next week). Only use what's actually in the notes - if a category has
nothing, return an empty list for it, don't pad it with filler.

Respond with ONLY a JSON object matching this schema:
{UPDATE_SCHEMA_HINT}
"""


def parse_update_json(text: str) -> WeeklyUpdate:
    cleaned = _strip_code_fence(text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise UpdateGenerationError(f"The model did not return valid JSON: {exc}\n\nRaw response:\n{text}") from exc

    if "accomplishments" not in data:
        raise UpdateGenerationError("The model's JSON is missing 'accomplishments'")

    return WeeklyUpdate(
        accomplishments=list(data.get("accomplishments", [])),
        in_progress=list(data.get("in_progress", [])),
        blockers=list(data.get("blockers", [])),
        next_steps=list(data.get("next_steps", [])),
    )


def generate_update(
    raw_notes: str, tone: str = "concise", audience: str = "manager", call_llm=default_call_llm
) -> WeeklyUpdate:
    if not raw_notes.strip():
        raise ValueError("raw_notes must not be empty")
    prompt = build_update_prompt(raw_notes, tone, audience)
    response_text = call_llm(prompt, system=SYSTEM_PROMPT)
    return parse_update_json(response_text)
