import json

import pytest

from prioritization_logic import (
    Feature,
    PrioritizationError,
    build_scoring_prompt,
    compute_score,
    parse_backlog_csv,
    parse_scores_json,
    rank_features,
    score_backlog,
    to_csv,
)

SAMPLE_CSV = """feature,description
Bulk archive,Archive many notifications at once
Dark mode,Dark color theme
"""

RICE_RESPONSE = json.dumps(
    [
        {
            "index": 1,
            "reach": 5000,
            "impact": 2,
            "confidence": 80,
            "effort": 2,
            "rationale": "High reach, moderate effort",
        },
        {
            "index": 2,
            "reach": 8000,
            "impact": 1,
            "confidence": 90,
            "effort": 4,
            "rationale": "Very high reach but lower impact",
        },
    ]
)

ICE_RESPONSE = json.dumps(
    [
        {"index": 1, "impact": 7, "confidence": 8, "ease": 6, "rationale": "Solid win"},
        {"index": 2, "impact": 4, "confidence": 9, "ease": 5, "rationale": "Nice to have"},
    ]
)

# Regression case: the model sometimes echoes the full "name - description"
# line instead of just the index. Index-based matching must ignore this.
RICE_RESPONSE_WITH_VERBOSE_NAME_FIELD = json.dumps(
    [
        {
            "index": 1,
            "feature": "Bulk archive - Archive many notifications at once",
            "reach": 5000,
            "impact": 2,
            "confidence": 80,
            "effort": 2,
            "rationale": "High reach, moderate effort",
        },
        {
            "index": 2,
            "feature": "Dark mode - Dark color theme",
            "reach": 8000,
            "impact": 1,
            "confidence": 90,
            "effort": 4,
            "rationale": "Very high reach but lower impact",
        },
    ]
)


def fake_call_llm_factory(response_text):
    calls = []

    def fake_call_llm(prompt, system="", model=None, max_tokens=4000):
        calls.append(prompt)
        return response_text

    fake_call_llm.calls = calls
    return fake_call_llm


class TestParseBacklogCsv:
    def test_parses_feature_and_description(self):
        features = parse_backlog_csv(SAMPLE_CSV)
        assert len(features) == 2
        assert features[0] == Feature(name="Bulk archive", description="Archive many notifications at once")

    def test_accepts_name_column_alias(self):
        csv_text = "name,notes\nFoo,bar\n"
        features = parse_backlog_csv(csv_text)
        assert features[0].name == "Foo"
        assert features[0].description == "bar"

    def test_missing_feature_column_raises(self):
        with pytest.raises(PrioritizationError, match="must have a 'feature'"):
            parse_backlog_csv("col1,col2\na,b\n")

    def test_empty_csv_raises(self):
        with pytest.raises(PrioritizationError):
            parse_backlog_csv("")

    def test_skips_blank_rows(self):
        csv_text = "feature,description\nFoo,bar\n,\nBaz,qux\n"
        features = parse_backlog_csv(csv_text)
        assert len(features) == 2


class TestComputeScore:
    def test_rice_score(self):
        score = compute_score("RICE", {"reach": 1000, "impact": 2, "confidence": 50, "effort": 5})
        # (1000 * 2 * 0.5) / 5 = 200
        assert score == 200.0

    def test_rice_zero_effort_raises(self):
        with pytest.raises(PrioritizationError):
            compute_score("RICE", {"reach": 1000, "impact": 2, "confidence": 50, "effort": 0})

    def test_ice_score(self):
        score = compute_score("ICE", {"impact": 9, "confidence": 6, "ease": 3})
        assert score == 6.0

    def test_unknown_framework_raises(self):
        with pytest.raises(PrioritizationError):
            compute_score("WSJF", {})


class TestBuildScoringPrompt:
    def test_includes_all_features(self):
        features = parse_backlog_csv(SAMPLE_CSV)
        prompt = build_scoring_prompt(features, "RICE")
        assert "Bulk archive" in prompt
        assert "Dark mode" in prompt
        assert "RICE" in prompt

    def test_invalid_framework_raises(self):
        features = parse_backlog_csv(SAMPLE_CSV)
        with pytest.raises(ValueError):
            build_scoring_prompt(features, "MoSCoW")


class TestParseScoresJson:
    def test_parses_rice_response(self):
        features = parse_backlog_csv(SAMPLE_CSV)
        scored = parse_scores_json(RICE_RESPONSE, features, "RICE")
        assert len(scored) == 2
        bulk = next(s for s in scored if s.name == "Bulk archive")
        assert bulk.score == round((5000 * 2 * 0.8) / 2, 2)

    def test_parses_ice_response(self):
        features = parse_backlog_csv(SAMPLE_CSV)
        scored = parse_scores_json(ICE_RESPONSE, features, "ICE")
        bulk = next(s for s in scored if s.name == "Bulk archive")
        assert bulk.score == pytest.approx(7.0)

    def test_missing_feature_in_response_raises(self):
        features = parse_backlog_csv(SAMPLE_CSV)
        partial = json.dumps([json.loads(RICE_RESPONSE)[0]])
        with pytest.raises(PrioritizationError, match="didn't include scores"):
            parse_scores_json(partial, features, "RICE")

    def test_invalid_json_raises(self):
        features = parse_backlog_csv(SAMPLE_CSV)
        with pytest.raises(PrioritizationError, match="valid JSON"):
            parse_scores_json("not json", features, "RICE")

    def test_non_list_json_raises(self):
        features = parse_backlog_csv(SAMPLE_CSV)
        with pytest.raises(PrioritizationError, match="not a list"):
            parse_scores_json(json.dumps({"foo": "bar"}), features, "RICE")

    def test_ignores_extra_feature_field_and_matches_by_index(self):
        # Regression: the model once echoed "name - description" into an
        # extra 'feature' field instead of the requested bare index. Matching
        # must key off 'index' only, not any name-like field the model adds.
        features = parse_backlog_csv(SAMPLE_CSV)
        scored = parse_scores_json(RICE_RESPONSE_WITH_VERBOSE_NAME_FIELD, features, "RICE")
        assert len(scored) == 2
        assert {s.name for s in scored} == {"Bulk archive", "Dark mode"}

    def test_non_integer_index_raises(self):
        features = parse_backlog_csv(SAMPLE_CSV)
        bad = json.dumps([{"index": "first", "reach": 1, "impact": 1, "confidence": 1, "effort": 1}])
        with pytest.raises(PrioritizationError, match="non-integer index"):
            parse_scores_json(bad, features, "RICE")

    def test_out_of_range_index_raises(self):
        features = parse_backlog_csv(SAMPLE_CSV)
        bad = json.dumps([{"index": 99, "reach": 1, "impact": 1, "confidence": 1, "effort": 1}])
        with pytest.raises(PrioritizationError, match="out-of-range index"):
            parse_scores_json(bad, features, "RICE")


class TestRankFeatures:
    def test_sorts_descending_by_score(self):
        features = parse_backlog_csv(SAMPLE_CSV)
        scored = parse_scores_json(RICE_RESPONSE, features, "RICE")
        ranked = rank_features(scored)
        assert ranked[0].score >= ranked[1].score


class TestScoreBacklogEndToEnd:
    def test_full_pipeline_with_fake_llm(self):
        fake = fake_call_llm_factory(RICE_RESPONSE)
        ranked = score_backlog(SAMPLE_CSV, "RICE", call_llm=fake)
        assert len(ranked) == 2
        assert len(fake.calls) == 1
        assert ranked[0].score >= ranked[1].score


class TestToCsv:
    def test_round_trips_expected_columns(self):
        features = parse_backlog_csv(SAMPLE_CSV)
        scored = rank_features(parse_scores_json(RICE_RESPONSE, features, "RICE"))
        csv_text = to_csv(scored)
        assert "rank,feature,description" in csv_text
        assert "Bulk archive" in csv_text

    def test_empty_list_returns_empty_string(self):
        assert to_csv([]) == ""
