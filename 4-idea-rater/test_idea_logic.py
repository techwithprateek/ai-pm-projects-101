import json

import pytest

from idea_logic import (
    IdeaRatingError,
    Rating,
    build_questions_prompt,
    build_rating_prompt,
    generate_questions,
    parse_questions_json,
    parse_rating_json,
    rate_idea,
)

QUESTIONS_RESPONSE = json.dumps(
    {
        "questions": [
            "Who exactly is the target user?",
            "How would they discover this today?",
            "What's the biggest untested assumption?",
        ]
    }
)

RATING_RESPONSE = json.dumps(
    {
        "pros": ["Clear target user", "Low cost to build an MVP"],
        "cons": ["Discovery channel is unclear", "Crowded market"],
        "score": 7,
        "rationale": "Solid idea with a real problem, but distribution is the open risk.",
    }
)


def fake_call_llm_factory(response_text):
    calls = []

    def fake_call_llm(prompt, system="", model=None, max_tokens=2000):
        calls.append({"prompt": prompt, "system": system})
        return response_text

    fake_call_llm.calls = calls
    return fake_call_llm


class TestBuildQuestionsPrompt:
    def test_includes_idea(self):
        prompt = build_questions_prompt("A Slack thread summarizer")
        assert "A Slack thread summarizer" in prompt


class TestParseQuestionsJson:
    def test_parses_list(self):
        questions = parse_questions_json(QUESTIONS_RESPONSE)
        assert len(questions) == 3
        assert questions[0] == "Who exactly is the target user?"

    def test_raises_on_missing_key(self):
        with pytest.raises(IdeaRatingError, match="questions"):
            parse_questions_json(json.dumps({"foo": "bar"}))

    def test_raises_on_invalid_json(self):
        with pytest.raises(IdeaRatingError, match="valid JSON"):
            parse_questions_json("not json")

    def test_raises_on_all_blank_questions(self):
        with pytest.raises(IdeaRatingError, match="zero questions"):
            parse_questions_json(json.dumps({"questions": ["", "  "]}))


class TestGenerateQuestions:
    def test_wires_prompt_through(self):
        fake = fake_call_llm_factory(QUESTIONS_RESPONSE)
        questions = generate_questions("A Slack thread summarizer", call_llm=fake)
        assert len(questions) == 3
        assert "Slack thread summarizer" in fake.calls[0]["prompt"]

    def test_empty_idea_raises_before_calling_llm(self):
        fake = fake_call_llm_factory(QUESTIONS_RESPONSE)
        with pytest.raises(ValueError):
            generate_questions("   ", call_llm=fake)
        assert len(fake.calls) == 0


class TestBuildRatingPrompt:
    def test_includes_idea_and_qa(self):
        prompt = build_rating_prompt(
            "A Slack thread summarizer", [("Who is the user?", "Busy managers")]
        )
        assert "A Slack thread summarizer" in prompt
        assert "Who is the user?" in prompt
        assert "Busy managers" in prompt

    def test_handles_blank_answer(self):
        prompt = build_rating_prompt("Idea", [("Q1?", "")])
        assert "no answer given" in prompt


class TestParseRatingJson:
    def test_parses_valid_response(self):
        rating = parse_rating_json(RATING_RESPONSE)
        assert isinstance(rating, Rating)
        assert rating.score == 7
        assert len(rating.pros) == 2

    def test_raises_on_missing_fields(self):
        with pytest.raises(IdeaRatingError, match="missing required fields"):
            parse_rating_json(json.dumps({"pros": []}))

    def test_raises_on_out_of_range_score(self):
        bad = json.dumps({"pros": [], "cons": [], "score": 15})
        with pytest.raises(IdeaRatingError, match="between 1 and 10"):
            parse_rating_json(bad)


class TestRateIdea:
    def test_end_to_end_with_fake_llm(self):
        fake = fake_call_llm_factory(RATING_RESPONSE)
        rating = rate_idea("A Slack thread summarizer", [("Who?", "Managers")], call_llm=fake)
        assert rating.score == 7
        assert len(fake.calls) == 1

    def test_empty_idea_raises_before_calling_llm(self):
        fake = fake_call_llm_factory(RATING_RESPONSE)
        with pytest.raises(ValueError):
            rate_idea("   ", [], call_llm=fake)
        assert len(fake.calls) == 0
