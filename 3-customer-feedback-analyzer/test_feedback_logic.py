import json

import pytest

from feedback_logic import (
    AnalyzedFeedback,
    Feedback,
    FeedbackAnalysisError,
    analyze_feedback,
    build_analysis_prompt,
    chunk,
    example_quote,
    parse_analysis_json,
    parse_feedback_csv,
    sentiment_counts,
    top_themes,
)

SAMPLE_CSV = """review_id,rating,review_text
1,2,App crashes when exporting large reports
2,5,Support fixed my issue within minutes
3,1,Billed for seats we don't use
"""

ANALYSIS_RESPONSE = json.dumps(
    [
        {"id": "1", "sentiment": "negative", "themes": ["bugs", "performance"]},
        {"id": "2", "sentiment": "positive", "themes": ["customer support"]},
        {"id": "3", "sentiment": "negative", "themes": ["pricing"]},
    ]
)


def fake_call_llm_factory(response_text):
    calls = []

    def fake_call_llm(prompt, system="", model=None, max_tokens=4000):
        calls.append(prompt)
        return response_text

    fake_call_llm.calls = calls
    return fake_call_llm


class TestParseFeedbackCsv:
    def test_parses_rows(self):
        feedback = parse_feedback_csv(SAMPLE_CSV)
        assert len(feedback) == 3
        assert feedback[0] == Feedback(id="1", text="App crashes when exporting large reports", rating="2")

    def test_accepts_column_aliases(self):
        csv_text = "comment\nGreat product\n"
        feedback = parse_feedback_csv(csv_text)
        assert feedback[0].text == "Great product"
        assert feedback[0].id == "1"  # falls back to row number

    def test_missing_text_column_raises(self):
        with pytest.raises(FeedbackAnalysisError, match="must have a 'review_text'"):
            parse_feedback_csv("col1,col2\na,b\n")

    def test_empty_csv_raises(self):
        with pytest.raises(FeedbackAnalysisError):
            parse_feedback_csv("")

    def test_skips_blank_rows(self):
        csv_text = "review_text\nGood\n\nBad\n"
        feedback = parse_feedback_csv(csv_text)
        assert len(feedback) == 2


class TestChunk:
    def test_splits_into_batches(self):
        assert chunk([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]

    def test_empty_list(self):
        assert chunk([], 2) == []


class TestBuildAnalysisPrompt:
    def test_includes_ids_and_text(self):
        feedback = parse_feedback_csv(SAMPLE_CSV)
        prompt = build_analysis_prompt(feedback)
        assert "App crashes when exporting large reports" in prompt
        assert "1:" in prompt


class TestParseAnalysisJson:
    def test_parses_valid_response(self):
        feedback = parse_feedback_csv(SAMPLE_CSV)
        results = parse_analysis_json(ANALYSIS_RESPONSE, feedback)
        assert len(results) == 3
        first = next(r for r in results if r.id == "1")
        assert first.sentiment == "negative"
        assert "bugs" in first.themes

    def test_invalid_sentiment_raises(self):
        feedback = parse_feedback_csv(SAMPLE_CSV)
        bad = json.dumps([{"id": "1", "sentiment": "furious", "themes": []}])
        with pytest.raises(FeedbackAnalysisError, match="Unexpected sentiment"):
            parse_analysis_json(bad, feedback)

    def test_mixed_sentiment_normalizes_to_neutral(self):
        feedback = parse_feedback_csv(SAMPLE_CSV)
        mixed = json.dumps([{"id": "1", "sentiment": "Mixed", "themes": []}])
        results = parse_analysis_json(mixed, feedback[:1])
        assert results[0].sentiment == "neutral"

    def test_invalid_json_raises(self):
        feedback = parse_feedback_csv(SAMPLE_CSV)
        with pytest.raises(FeedbackAnalysisError, match="valid JSON"):
            parse_analysis_json("not json", feedback)

    def test_missing_ids_raises(self):
        feedback = parse_feedback_csv(SAMPLE_CSV)
        partial = json.dumps([json.loads(ANALYSIS_RESPONSE)[0]])
        with pytest.raises(FeedbackAnalysisError, match="didn't include analysis"):
            parse_analysis_json(partial, feedback)


class TestAnalyzeFeedbackEndToEnd:
    def test_batches_and_aggregates(self):
        fake = fake_call_llm_factory(ANALYSIS_RESPONSE)
        results = analyze_feedback(SAMPLE_CSV, call_llm=fake, batch_size=2)
        assert len(fake.calls) == 2  # 3 rows, batch size 2 -> 2 batches
        assert len(results) == 3

    def test_single_batch_when_size_covers_all(self):
        fake = fake_call_llm_factory(ANALYSIS_RESPONSE)
        analyze_feedback(SAMPLE_CSV, call_llm=fake, batch_size=20)
        assert len(fake.calls) == 1


class TestAggregation:
    def test_sentiment_counts_includes_zero_categories(self):
        feedback = parse_feedback_csv(SAMPLE_CSV)
        analyzed = parse_analysis_json(ANALYSIS_RESPONSE, feedback)
        counts = sentiment_counts(analyzed)
        assert counts == {"positive": 1, "neutral": 0, "negative": 2}

    def test_top_themes_ranked_by_frequency(self):
        analyzed = [
            AnalyzedFeedback(id="1", text="a", rating="", sentiment="negative", themes=["bugs"]),
            AnalyzedFeedback(id="2", text="b", rating="", sentiment="negative", themes=["bugs", "pricing"]),
            AnalyzedFeedback(id="3", text="c", rating="", sentiment="positive", themes=["pricing"]),
        ]
        themes = top_themes(analyzed, n=2)
        assert themes[0] == ("bugs", 2)
        assert themes[1] == ("pricing", 2)

    def test_example_quote_returns_matching_text(self):
        analyzed = [
            AnalyzedFeedback(id="1", text="Billing is confusing", rating="", sentiment="negative", themes=["pricing"]),
        ]
        assert example_quote(analyzed, "pricing") == "Billing is confusing"

    def test_example_quote_returns_empty_when_no_match(self):
        assert example_quote([], "pricing") == ""
