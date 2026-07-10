"""Prompt building, scoring, and CSV I/O for the Feature Prioritization Copilot.

Pure functions in this file take a `call_llm`-shaped function as a
parameter so they can be unit tested with a fake instead of the real API.
"""
import csv
import io
import json
from dataclasses import dataclass, field

from llm_client import call_llm as default_call_llm

RICE_IMPACT_SCALE = [0.25, 0.5, 1, 2, 3]


class PrioritizationError(RuntimeError):
    """Raised when the backlog CSV or the model's response can't be parsed."""


@dataclass
class Feature:
    name: str
    description: str = ""


@dataclass
class ScoredFeature:
    name: str
    description: str
    framework: str
    estimates: dict
    rationale: str
    score: float = field(init=False)

    def __post_init__(self):
        self.score = compute_score(self.framework, self.estimates)


def compute_score(framework: str, estimates: dict) -> float:
    if framework == "RICE":
        reach = float(estimates["reach"])
        impact = float(estimates["impact"])
        confidence = float(estimates["confidence"])
        effort = float(estimates["effort"])
        if effort <= 0:
            raise PrioritizationError("effort must be greater than 0")
        return round((reach * impact * (confidence / 100)) / effort, 2)
    elif framework == "ICE":
        impact = float(estimates["impact"])
        confidence = float(estimates["confidence"])
        ease = float(estimates["ease"])
        return round((impact + confidence + ease) / 3, 2)
    raise PrioritizationError(f"Unknown framework: {framework}")


def parse_backlog_csv(csv_text: str) -> list[Feature]:
    reader = csv.DictReader(io.StringIO(csv_text))
    if reader.fieldnames is None:
        raise PrioritizationError("CSV appears to be empty")

    lower_fields = {f.lower().strip(): f for f in reader.fieldnames}
    name_col = next((lower_fields[c] for c in ("feature", "name", "title") if c in lower_fields), None)
    if name_col is None:
        raise PrioritizationError(
            f"CSV must have a 'feature' (or 'name'/'title') column. Found columns: {reader.fieldnames}"
        )
    desc_col = next((lower_fields[c] for c in ("description", "notes", "details") if c in lower_fields), None)

    features = []
    for row in reader:
        name = (row.get(name_col) or "").strip()
        if not name:
            continue
        description = (row.get(desc_col) or "").strip() if desc_col else ""
        features.append(Feature(name=name, description=description))

    if not features:
        raise PrioritizationError("No feature rows found in CSV")
    return features


RICE_SCHEMA_HINT = """[
  {
    "index": "the item number from the backlog list below (1, 2, 3, ...) - do not include the feature name or description here",
    "reach": "integer - estimated number of users/customers affected per quarter",
    "impact": "one of 0.25, 0.5, 1, 2, 3 (minimal, low, medium, high, massive)",
    "confidence": "integer 0-100 - how confident you are in this estimate",
    "effort": "number of person-weeks to build, > 0",
    "rationale": "one sentence explaining the estimate"
  }
]"""

ICE_SCHEMA_HINT = """[
  {
    "index": "the item number from the backlog list below (1, 2, 3, ...) - do not include the feature name or description here",
    "impact": "integer 1-10 - how much this moves the needle if done well",
    "confidence": "integer 1-10 - how confident you are it will have that impact",
    "ease": "integer 1-10 - how easy/cheap this is to build (10 = trivial)",
    "rationale": "one sentence explaining the estimate"
  }
]"""


def build_scoring_prompt(features: list[Feature], framework: str) -> str:
    if framework not in ("RICE", "ICE"):
        raise ValueError("framework must be 'RICE' or 'ICE'")

    listing = "\n".join(
        f"{i + 1}. {f.name}" + (f" - {f.description}" if f.description else "")
        for i, f in enumerate(features)
    )
    schema = RICE_SCHEMA_HINT if framework == "RICE" else ICE_SCHEMA_HINT

    return f"""You are scoring a product backlog using the {framework} prioritization framework.

BACKLOG (numbered list):
{listing}

For EVERY item above, estimate the {framework} inputs. Respond with ONLY a
JSON array (no markdown fences, no commentary) with exactly one object per
backlog item, in this schema:
{schema}

Identify each item ONLY by its number from the list - do not repeat its name
or description in the response. Base estimates on the feature name and
description given. Be honest and differentiate between items - do not give
every item the same score.
"""


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


def parse_scores_json(text: str, features: list[Feature], framework: str) -> list[ScoredFeature]:
    cleaned = _strip_code_fence(text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise PrioritizationError(f"The model did not return valid JSON: {exc}\n\nRaw response:\n{text}") from exc

    if not isinstance(data, list):
        raise PrioritizationError("The model's response was valid JSON but not a list")

    estimate_keys = ("reach", "impact", "confidence", "effort") if framework == "RICE" else (
        "impact",
        "confidence",
        "ease",
    )

    scored = []
    seen_indices = set()
    for item in data:
        raw_index = item.get("index")
        try:
            index = int(raw_index)
        except (TypeError, ValueError):
            raise PrioritizationError(f"The model returned a non-integer index: {raw_index!r}")
        if not (1 <= index <= len(features)):
            raise PrioritizationError(f"The model returned an out-of-range index: {index}")

        feature = features[index - 1]
        seen_indices.add(index)

        missing = [k for k in estimate_keys if k not in item]
        if missing:
            raise PrioritizationError(
                f"The model's entry for item {index} ('{feature.name}') is missing fields: {missing}"
            )
        estimates = {k: item[k] for k in estimate_keys}
        scored.append(
            ScoredFeature(
                name=feature.name,
                description=feature.description,
                framework=framework,
                estimates=estimates,
                rationale=item.get("rationale", ""),
            )
        )

    missing_indices = [i for i in range(1, len(features) + 1) if i not in seen_indices]
    if missing_indices:
        missing_names = [features[i - 1].name for i in missing_indices]
        raise PrioritizationError(f"The model's response didn't include scores for: {missing_names}")

    return scored


def rank_features(scored: list[ScoredFeature]) -> list[ScoredFeature]:
    return sorted(scored, key=lambda s: s.score, reverse=True)


def score_backlog(csv_text: str, framework: str, call_llm=default_call_llm) -> list[ScoredFeature]:
    features = parse_backlog_csv(csv_text)
    prompt = build_scoring_prompt(features, framework)
    response_text = call_llm(prompt)
    scored = parse_scores_json(response_text, features, framework)
    return rank_features(scored)


def to_csv(scored: list[ScoredFeature]) -> str:
    if not scored:
        return ""
    estimate_keys = list(scored[0].estimates.keys())
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["rank", "feature", "description", *estimate_keys, "score", "rationale"])
    for rank, s in enumerate(scored, start=1):
        writer.writerow(
            [rank, s.name, s.description, *[s.estimates[k] for k in estimate_keys], s.score, s.rationale]
        )
    return output.getvalue()
