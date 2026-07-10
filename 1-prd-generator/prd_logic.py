"""Prompt building + response parsing for the PRD Generator.

Pure functions in this file take a `call_llm`-shaped function as a
parameter so they can be unit tested with a fake instead of the real API.
"""
import json
from dataclasses import dataclass, field

from llm_client import call_llm as default_call_llm

SYSTEM_PROMPT = (
    "You are a senior product manager who writes crisp, specific PRDs. "
    "You never write vague filler like 'improve user experience' - every "
    "line should be concrete enough that an engineer or designer could act "
    "on it. You always respond with valid JSON matching the schema you are "
    "given, and nothing else - no markdown fences, no commentary."
)

PRD_SCHEMA_HINT = """{
  "problem": "string - the user/business problem, grounded in the research notes",
  "goals": ["string", "..."],
  "user_stories": ["As a <user>, I want <need> so that <benefit>", "..."],
  "success_metrics": ["string - specific, measurable metric with a target or direction", "..."],
  "open_questions": ["string - things this PRD does not yet answer", "..."]
}"""


class PRDGenerationError(RuntimeError):
    """Raised when the model's response can't be parsed into a PRD."""


@dataclass
class PRD:
    problem: str
    goals: list[str]
    user_stories: list[str]
    success_metrics: list[str]
    open_questions: list[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        def section(title, items):
            body = "\n".join(f"- {item}" for item in items) if items else "_none_"
            return f"## {title}\n{body}\n"

        return "\n".join(
            [
                "# PRD\n",
                f"## Problem\n{self.problem}\n",
                section("Goals", self.goals),
                section("User Stories", self.user_stories),
                section("Success Metrics", self.success_metrics),
                section("Open Questions", self.open_questions),
            ]
        )


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


def parse_prd_json(text: str) -> PRD:
    cleaned = _strip_code_fence(text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise PRDGenerationError(f"The model did not return valid JSON: {exc}\n\nRaw response:\n{text}") from exc

    missing = [k for k in ("problem", "goals", "user_stories", "success_metrics") if k not in data]
    if missing:
        raise PRDGenerationError(f"The model's JSON is missing required fields: {missing}")

    return PRD(
        problem=data["problem"],
        goals=list(data["goals"]),
        user_stories=list(data["user_stories"]),
        success_metrics=list(data["success_metrics"]),
        open_questions=list(data.get("open_questions", [])),
    )


def build_prd_prompt(feature_idea: str, research_notes: str) -> str:
    notes_block = research_notes.strip() or "(no research notes provided - flag assumptions explicitly)"
    return f"""Turn this rough feature idea and research notes into a structured PRD.

FEATURE IDEA:
{feature_idea.strip()}

RESEARCH NOTES:
{notes_block}

Respond with ONLY a JSON object matching this schema:
{PRD_SCHEMA_HINT}

Rules:
- Ground the problem statement in the research notes, not just the idea.
- Success metrics must be measurable (a number, rate, or clear direction), never vague like "improve satisfaction".
- Write 3-6 user stories in "As a ... I want ... so that ..." form.
- List open_questions for anything the research notes don't answer.
"""


def generate_prd(feature_idea: str, research_notes: str, call_llm=default_call_llm) -> PRD:
    if not feature_idea.strip():
        raise ValueError("feature_idea must not be empty")
    prompt = build_prd_prompt(feature_idea, research_notes)
    response_text = call_llm(prompt, system=SYSTEM_PROMPT)
    return parse_prd_json(response_text)


CRITIQUE_SCHEMA_HINT = """{
  "scores": {
    "problem_clarity": 1-5,
    "goal_specificity": 1-5,
    "user_story_quality": 1-5,
    "metric_measurability": 1-5
  },
  "feedback": "string - 2-4 sentences of concrete, actionable critique"
}"""


@dataclass
class Critique:
    scores: dict
    feedback: str

    @property
    def average(self) -> float:
        return sum(self.scores.values()) / len(self.scores) if self.scores else 0.0


def build_critique_prompt(prd: PRD) -> str:
    return f"""Critique this PRD as a skeptical, experienced PM reviewing a draft.

PRD:
{prd.to_markdown()}

Score it on each dimension from 1 (weak) to 5 (excellent) and give concrete
feedback on what to fix. Respond with ONLY a JSON object matching this schema:
{CRITIQUE_SCHEMA_HINT}
"""


def parse_critique_json(text: str) -> Critique:
    cleaned = _strip_code_fence(text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise PRDGenerationError(f"The model did not return valid JSON: {exc}\n\nRaw response:\n{text}") from exc

    if "scores" not in data or "feedback" not in data:
        raise PRDGenerationError("The model's critique JSON is missing 'scores' or 'feedback'")

    return Critique(scores=dict(data["scores"]), feedback=data["feedback"])


def critique_prd(prd: PRD, call_llm=default_call_llm) -> Critique:
    prompt = build_critique_prompt(prd)
    response_text = call_llm(prompt, system=SYSTEM_PROMPT)
    return parse_critique_json(response_text)


def build_revision_prompt(prd: PRD, user_feedback: str) -> str:
    return f"""Here is a draft PRD:

{prd.to_markdown()}

The author wants these changes incorporated:
{user_feedback.strip()}

Revise the PRD accordingly. Respond with ONLY a JSON object matching this schema:
{PRD_SCHEMA_HINT}
"""


def revise_prd(prd: PRD, user_feedback: str, call_llm=default_call_llm) -> PRD:
    if not user_feedback.strip():
        raise ValueError("user_feedback must not be empty")
    prompt = build_revision_prompt(prd, user_feedback)
    response_text = call_llm(prompt, system=SYSTEM_PROMPT)
    return parse_prd_json(response_text)
