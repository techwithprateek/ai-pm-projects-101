# Guide: Idea Rater

## What this is

Type a product idea in one or two sentences. The model asks you 3-5 clarifying
questions - the things that would actually change whether the idea is good
(who's the user, how would they find it, what's the biggest untested
assumption). You answer them, and the model gives you a pros-and-cons list
grounded in your actual answers, plus an honest 1-10 score.

This is the smallest of the five projects - two sequential LLM calls and no
file handling - and it's here to show the smallest *good* shape for a
conversational AI feature, not just a single prompt-response.

## How it works

**Architecture:**

```
app.py (Streamlit: idea input -> questions -> answers -> rating, session state)
   -> idea_logic.py (build prompts, parse responses)
        -> llm_client.py (call_llm: prompt in, text out)
             -> OpenAI API
```

**Why two calls instead of one:** the brief asks for "AI asks you a few
questions, then gives pros/cons." A single-call version ("here's my idea,
give me pros and cons") is easy to build but shallow - it forces the model to
guess at the target user, the market, the constraints, and it'll fill those
gaps with generic startup-advice filler. Splitting it into
**questions first, then rating** means the pros/cons are actually about
*your* idea and *your* answers, not a generic template. That's the entire
product insight behind this "simple" app.

1. `build_questions_prompt` / `generate_questions` - sends the idea alone,
   asks for 3-5 short clarifying questions as JSON (`{"questions": [...]}`).
   The system prompt frames the model as "supportive but not a pushover" so the
   questions probe real risk (distribution, differentiation) instead of just
   flattering the idea.
2. The Streamlit form renders one text input per question and collects
   answers, defaulting a blank answer to `"(no answer given)"` in the prompt
   rather than breaking - if you skip a question, the model just works with
   less information, same as a real conversation would.
3. `build_rating_prompt` / `rate_idea` - sends the idea plus every Q&A pair,
   asks for pros, cons, a 1-10 score, and a short rationale, all as JSON.
   `Rating.__post_init__` enforces the score is actually 1-10, raising
   `IdeaRatingError` if the model ever returns something out of range - a
   guardrail against the model silently returning `"score": 15`.

**Parsing:** both response parsers share `_parse_json`/`_strip_code_fence`
helpers that tolerate a markdown-fenced response and raise a clear error with
the raw text attached if JSON parsing or schema validation fails.

## How to run it

```bash
cd 4-idea-rater
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your OPENAI_API_KEY
streamlit run app.py
```

Run the tests (no API key needed - everything is mocked):

```bash
pytest
```

## How this was vibecoded

1. **Notice when "one prompt" is actually two products.** The brief's
   description - idea, then questions, then rating - already implies two
   distinct LLM calls with different jobs (probe vs. judge). Naming that
   split before writing any code is what kept the app from collapsing into
   "one big prompt that tries to do both," which is both harder to test and
   produces worse output.
2. **Give the rating call the raw context, not a summary.** The rating
   prompt includes every question and answer verbatim rather than an
   AI-written summary of them. An extra summarization step is tempting to
   add ("clean up the answers first") but it's a place for information to
   get lost or hallucinated for no benefit here - the raw Q&A is short enough
   to just pass through.
3. **Validate the score range, not just its type.** `int(data["score"])`
   alone would accept a the model response of `15` or `-3`. Enforcing `1 <= score
   <= 10` inside the dataclass (`Rating.__post_init__`) means every caller of
   `Rating` gets that guarantee for free, instead of every UI spot that
   reads `.score` needing to re-check it.
4. **Test the empty-input guard rails explicitly.** `test_empty_idea_raises_before_calling_llm`
   checks not just that an error is raised, but that the model is never called
   for an empty idea (`fake.calls == 0`) - the kind of assertion that would
   catch a regression where a future edit removes the early `if not
   idea.strip()` check and starts burning API calls on empty submissions.
5. **Use `st.form` for the questions step.** Streamlit reruns the whole
   script on every widget interaction; wrapping the per-question text inputs
   in a form means partial typing in one field doesn't trigger a rating call
   before all answers are in. This is a small Streamlit-specific detail, but
   it's the difference between "demo works" and "demo submits early and
   confuses people."
