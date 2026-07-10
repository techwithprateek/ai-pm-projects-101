import json

import pytest

from update_logic import (
    UpdateGenerationError,
    WeeklyUpdate,
    build_update_prompt,
    generate_update,
    parse_update_json,
)

VALID_RESPONSE = json.dumps(
    {
        "accomplishments": ["Shipped CSV export", "Finished 6 onboarding interviews"],
        "in_progress": ["Waiting on legal sign-off for pricing page"],
        "blockers": ["Legal review has been pending for a week"],
        "next_steps": ["Start the RICE scoring doc"],
    }
)


def fake_call_llm_factory(response_text):
    calls = []

    def fake_call_llm(prompt, system="", model=None, max_tokens=2000):
        calls.append({"prompt": prompt, "system": system})
        return response_text

    fake_call_llm.calls = calls
    return fake_call_llm


class TestBuildUpdatePrompt:
    def test_includes_notes(self):
        prompt = build_update_prompt("Shipped the export feature", tone="concise", audience="manager")
        assert "Shipped the export feature" in prompt

    def test_invalid_tone_raises(self):
        with pytest.raises(ValueError):
            build_update_prompt("notes", tone="snarky")

    def test_invalid_audience_raises(self):
        with pytest.raises(ValueError):
            build_update_prompt("notes", audience="the board")

    def test_detailed_tone_differs_from_concise(self):
        concise = build_update_prompt("notes", tone="concise")
        detailed = build_update_prompt("notes", tone="detailed")
        assert concise != detailed


class TestParseUpdateJson:
    def test_parses_all_sections(self):
        update = parse_update_json(VALID_RESPONSE)
        assert isinstance(update, WeeklyUpdate)
        assert len(update.accomplishments) == 2
        assert len(update.blockers) == 1

    def test_strips_markdown_code_fence(self):
        fenced = f"```json\n{VALID_RESPONSE}\n```"
        update = parse_update_json(fenced)
        assert update.accomplishments[0] == "Shipped CSV export"

    def test_missing_accomplishments_key_raises(self):
        with pytest.raises(UpdateGenerationError, match="accomplishments"):
            parse_update_json(json.dumps({"in_progress": []}))

    def test_invalid_json_raises(self):
        with pytest.raises(UpdateGenerationError, match="valid JSON"):
            parse_update_json("not json")

    def test_missing_optional_sections_default_to_empty(self):
        update = parse_update_json(json.dumps({"accomplishments": ["Did a thing"]}))
        assert update.in_progress == []
        assert update.blockers == []
        assert update.next_steps == []


class TestToMessage:
    def test_includes_only_non_empty_sections(self):
        update = WeeklyUpdate(accomplishments=["Did a thing"], in_progress=[], blockers=[], next_steps=[])
        message = update.to_message()
        assert "Accomplishments this week" in message
        assert "In progress" not in message
        assert "Blockers" not in message

    def test_formats_bullets(self):
        update = WeeklyUpdate(accomplishments=["A", "B"], in_progress=[])
        message = update.to_message()
        assert "- A" in message
        assert "- B" in message


class TestGenerateUpdate:
    def test_end_to_end_with_fake_llm(self):
        fake = fake_call_llm_factory(VALID_RESPONSE)
        update = generate_update("Shipped export, waiting on legal", call_llm=fake)
        assert len(update.accomplishments) == 2
        assert len(fake.calls) == 1

    def test_empty_notes_raises_before_calling_llm(self):
        fake = fake_call_llm_factory(VALID_RESPONSE)
        with pytest.raises(ValueError):
            generate_update("   ", call_llm=fake)
        assert len(fake.calls) == 0

    def test_passes_tone_and_audience_into_prompt(self):
        fake = fake_call_llm_factory(VALID_RESPONSE)
        generate_update("notes here", tone="detailed", audience="stakeholders", call_llm=fake)
        assert "stakeholders" in fake.calls[0]["prompt"]
