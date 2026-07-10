import json

import pytest

from prd_logic import (
    PRD,
    PRDGenerationError,
    build_critique_prompt,
    build_prd_prompt,
    build_revision_prompt,
    critique_prd,
    generate_prd,
    parse_critique_json,
    parse_prd_json,
    revise_prd,
)

VALID_PRD_JSON = json.dumps(
    {
        "problem": "Users miss important notifications because they have to dismiss them one by one.",
        "goals": ["Reduce time spent managing notifications", "Increase notification read rate"],
        "user_stories": [
            "As a busy user, I want to bulk-archive notifications so that I can clear my inbox quickly."
        ],
        "success_metrics": ["Median time to clear notification inbox drops by 30%"],
        "open_questions": ["Should archived notifications be recoverable?"],
    }
)

VALID_CRITIQUE_JSON = json.dumps(
    {
        "scores": {
            "problem_clarity": 4,
            "goal_specificity": 3,
            "user_story_quality": 5,
            "metric_measurability": 4,
        },
        "feedback": "Solid draft. Tighten the second goal so it has a measurable target too.",
    }
)


def fake_call_llm_factory(response_text):
    calls = []

    def fake_call_llm(prompt, system="", model=None, max_tokens=2000):
        calls.append({"prompt": prompt, "system": system})
        return response_text

    fake_call_llm.calls = calls
    return fake_call_llm


class TestBuildPrdPrompt:
    def test_includes_feature_idea_and_notes(self):
        prompt = build_prd_prompt("Bulk archive notifications", "Users complain in support tickets")
        assert "Bulk archive notifications" in prompt
        assert "Users complain in support tickets" in prompt

    def test_flags_missing_notes(self):
        prompt = build_prd_prompt("Bulk archive notifications", "")
        assert "no research notes provided" in prompt


class TestParsePrdJson:
    def test_parses_valid_json(self):
        prd = parse_prd_json(VALID_PRD_JSON)
        assert isinstance(prd, PRD)
        assert "one by one" in prd.problem
        assert len(prd.goals) == 2
        assert len(prd.user_stories) == 1

    def test_strips_markdown_code_fence(self):
        fenced = f"```json\n{VALID_PRD_JSON}\n```"
        prd = parse_prd_json(fenced)
        assert prd.goals[0] == "Reduce time spent managing notifications"

    def test_raises_on_invalid_json(self):
        with pytest.raises(PRDGenerationError, match="valid JSON"):
            parse_prd_json("not json at all")

    def test_raises_on_missing_fields(self):
        with pytest.raises(PRDGenerationError, match="missing required fields"):
            parse_prd_json(json.dumps({"problem": "x"}))

    def test_defaults_open_questions_to_empty(self):
        data = json.loads(VALID_PRD_JSON)
        del data["open_questions"]
        prd = parse_prd_json(json.dumps(data))
        assert prd.open_questions == []


class TestPrdToMarkdown:
    def test_contains_all_sections(self):
        prd = parse_prd_json(VALID_PRD_JSON)
        md = prd.to_markdown()
        for heading in ["Problem", "Goals", "User Stories", "Success Metrics", "Open Questions"]:
            assert f"## {heading}" in md


class TestGeneratePrd:
    def test_wires_prompt_through_to_llm_and_back(self):
        fake = fake_call_llm_factory(VALID_PRD_JSON)
        prd = generate_prd("Bulk archive notifications", "some notes", call_llm=fake)
        assert isinstance(prd, PRD)
        assert len(fake.calls) == 1
        assert "Bulk archive notifications" in fake.calls[0]["prompt"]

    def test_empty_idea_raises_before_calling_llm(self):
        fake = fake_call_llm_factory(VALID_PRD_JSON)
        with pytest.raises(ValueError):
            generate_prd("   ", "notes", call_llm=fake)
        assert len(fake.calls) == 0


class TestCritique:
    def test_build_critique_prompt_includes_prd(self):
        prd = parse_prd_json(VALID_PRD_JSON)
        prompt = build_critique_prompt(prd)
        assert prd.problem in prompt

    def test_parse_critique_json(self):
        critique = parse_critique_json(VALID_CRITIQUE_JSON)
        assert critique.scores["problem_clarity"] == 4
        assert critique.average == pytest.approx(4.0)

    def test_critique_prd_end_to_end(self):
        fake = fake_call_llm_factory(VALID_CRITIQUE_JSON)
        prd = parse_prd_json(VALID_PRD_JSON)
        critique = critique_prd(prd, call_llm=fake)
        assert critique.feedback.startswith("Solid draft")

    def test_missing_keys_raises(self):
        with pytest.raises(PRDGenerationError):
            parse_critique_json(json.dumps({"scores": {}}))


class TestRevise:
    def test_build_revision_prompt_includes_feedback_and_prd(self):
        prd = parse_prd_json(VALID_PRD_JSON)
        prompt = build_revision_prompt(prd, "Make the metrics more aggressive")
        assert "Make the metrics more aggressive" in prompt
        assert prd.problem in prompt

    def test_revise_prd_end_to_end(self):
        fake = fake_call_llm_factory(VALID_PRD_JSON)
        prd = parse_prd_json(VALID_PRD_JSON)
        revised = revise_prd(prd, "Tighten goal 2", call_llm=fake)
        assert isinstance(revised, PRD)

    def test_empty_feedback_raises_before_calling_llm(self):
        fake = fake_call_llm_factory(VALID_PRD_JSON)
        prd = parse_prd_json(VALID_PRD_JSON)
        with pytest.raises(ValueError):
            revise_prd(prd, "   ", call_llm=fake)
        assert len(fake.calls) == 0
