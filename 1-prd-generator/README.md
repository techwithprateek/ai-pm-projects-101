# Guide: PRD Generator

## What this is

You paste in a rough feature idea and whatever research notes you have
(interview quotes, support tickets, survey data - or nothing at all). The model
turns that into a structured PRD: problem statement, goals, user stories, and
success metrics. Then you can ask the model to critique its own draft, and feed
back revisions until it's good enough to actually ship to your team.

This is the single most common "can AI do my job" question a PM gets asked.
The honest answer this project tries to demonstrate: AI is a genuinely good
first-draft machine, but a PRD is only as good as the problem framing and
metrics behind it - so the interesting product decisions here are about
*evaluation* and *iteration*, not the generation itself.

## How it works

**Architecture:** a single Streamlit page, a `llm_client.py` wrapper
around the OpenAI SDK, and `prd_logic.py`, which holds every prompt and
every bit of parsing as plain functions with no UI code in them.

```
app.py (Streamlit UI, session state)
   -> prd_logic.py (build prompts, parse responses)
        -> llm_client.py (call_llm: prompt in, text out)
             -> OpenAI API
```

That separation is what makes this testable: `test_prd_logic.py` never
touches the network. It passes a fake `call_llm` function into
`generate_prd()`, `critique_prd()`, and `revise_prd()` and checks that (a) the
prompt sent to the model contains what it should, and (b) the response gets
parsed into the right shape - including malformed-response cases.

**The three prompts:**

1. **Generate** (`build_prd_prompt`) - takes the idea + notes, asks for a PRD
   as JSON with a fixed schema (`problem`, `goals`, `user_stories`,
   `success_metrics`, `open_questions`). Forcing JSON output (rather than
   free-form markdown) is what lets the app render clean sections, offer a
   markdown export, and feed the PRD back into the next two prompts as
   structured data instead of a wall of text.
2. **Critique** (`build_critique_prompt`) - the "how do you evaluate a good
   PRD vs a bad one" question from the brief. Rather than build a bespoke
   scoring rubric by hand, the app asks the model to *play a skeptical reviewer*
   and score four dimensions (problem clarity, goal specificity, user story
   quality, metric measurability) each 1-5, with concrete feedback. This is a
   second, independent LLM call - it does not just rubber-stamp its own work
   because it's evaluating the finished PRD fresh, with an explicit "be
   skeptical" instruction and a different objective (critique, not generate).
3. **Revise** (`build_revision_prompt`) - takes the current PRD plus your
   free-text feedback ("make the metrics more aggressive", "add a story for
   the admin persona") and regenerates the full PRD. This is the "prompt
   chain" iteration loop: each revision is a fresh call seeded with the prior
   draft, not an ever-growing conversation, which keeps output quality
   consistent instead of drifting after several edits.

**Parsing:** `parse_prd_json` and `parse_critique_json` strip a markdown code
fence if the model adds one, `json.loads` the result, and check for required
keys - raising a clear `PRDGenerationError` (with the raw response attached)
if anything's missing or malformed, instead of silently showing broken data.

## How to run it

```bash
cd 1-prd-generator
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

"Vibecoding" here means: describe the end state precisely enough that the
implementation is a small, checkable step, not a leap of faith. The loop
looked like this:

1. **Start from the job to be done, not the tech.** The brief says "feed it
   an idea + notes, get a structured PRD, think about how you'd evaluate good
   vs bad output." That last clause is the actual product thinking - it's
   what turned this from "call an LLM once" into "generate, then critique,
   then let the user iterate."
2. **Force structure early.** The first version of this kind of app is
   tempting to build as "ask the model to write a PRD in markdown." That's
   *harder* to build well, not easier - you can't validate it, can't render
   it in sections, can't feed it back into a second prompt cleanly. Asking
   for JSON against an explicit schema up front made everything downstream
   (rendering, exporting, critiquing, revising) simpler.
3. **Separate logic from UI before writing either.** Every function that
   talks to the model takes `call_llm` as a parameter with a default. That
   one decision is what makes `pytest` possible without secrets or network
   calls - it wasn't an afterthought, it's the first thing to decide when the
   product is "wrap an LLM call in a UI."
4. **Write the failure cases as tests, not as manual pokes.** Malformed JSON,
   empty input, missing schema keys - these are the cases that break a demo
   in front of your team. Writing them as `pytest` cases (`test_raises_on_invalid_json`,
   `test_empty_idea_raises_before_calling_llm`) means they stay caught
   after the next prompt tweak, instead of being rediscovered live.
5. **Run it for real before calling it done.** Type-checking and unit tests
   confirm the plumbing is correct; they don't confirm the PRD is actually
   good. Run `streamlit run app.py`, generate a PRD from a real rough idea you
   have, and read it like a stakeholder would before you trust it.

The general shape - **pure logic module + thin UI + injected LLM client +
tests that mock the client** - is the reusable pattern here. It's the
difference between "a demo that calls an API" and something you could hand to
another engineer to maintain.
