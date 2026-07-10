# Guide: Feature Prioritization Copilot

## What this is

Upload a backlog CSV (just `feature` + `description` columns - no scores
required), pick RICE or ICE, and the model estimates the framework inputs for
every row and ranks the backlog for you. Download the ranked list as CSV.

This is the project from the brief described as "pure file-upload + LLM-call
app - no backend beyond the AI API, easy to vibecode in one sitting." It's a
good template for the most common shape of internal AI tool: take a file
people already have, run it through an LLM, hand back a better file.

## How it works

**Architecture:**

```
app.py (Streamlit: upload, framework picker, table, CSV download)
   -> prioritization_logic.py (CSV parsing, prompt building, scoring, ranking)
        -> llm_client.py (call_llm: prompt in, text out)
             -> OpenAI API
```

**The pipeline (`score_backlog`):**

1. `parse_backlog_csv` reads the uploaded CSV with `csv.DictReader`, tolerant
   of column-name variants (`feature`/`name`/`title`, `description`/`notes`/`details`),
   and raises a clear error naming the columns it actually found if it can't
   locate a feature-name column.
2. `build_scoring_prompt` lists every feature (numbered, with description) and
   asks the model for a JSON array of framework-specific estimates - one object
   per feature - identified by exact feature name so responses can be matched
   back to the input rows even if the model reorders them.
3. `parse_scores_json` parses that array, matches each entry back to its
   `Feature` by name, and raises `PrioritizationError` if any feature is
   missing from the response (rather than silently dropping it).
4. `compute_score` applies the actual framework math:
   - **RICE:** `(Reach × Impact × Confidence%) / Effort`
   - **ICE:** average of Impact, Confidence, Ease (all 1-10)
   These are plain arithmetic, not LLM calls - the model estimates the inputs,
   the app computes the score. That split matters: the score is always
   reproducible from the estimates, and you can sanity-check or hand-edit an
   estimate without re-prompting.
5. `rank_features` sorts by score descending; `to_csv` writes the ranked list
   back out with every estimate column plus the model's one-line rationale, so a
   stakeholder can see *why* something ranked where it did, not just the
   number.

**Why a single batched prompt instead of one call per feature:** it's faster,
cheaper, and - more importantly for a scoring tool - it gives the model the
whole backlog as context, so estimates are made *relative to each other*
instead of independently, which is closer to how a PM would actually score a
backlog by hand.

## How to run it

```bash
cd 2-feature-prioritization-copilot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your OPENAI_API_KEY
streamlit run app.py
```

No CSV handy? Check "Score the sample backlog instead of uploading" in the
app, or use `sample_backlog.csv` directly.

Run the tests (no API key needed - everything is mocked):

```bash
pytest
```

## How this was vibecoded

1. **Read "no backend beyond the AI API" as a design constraint, not a
   shortcut.** It means: no database, no auth, no server-side state beyond
   one request/response cycle. Streamlit's session state plus a single
   the model call is the entire backend. Resisting the urge to add anything more
   (a features table, saved history, user accounts) is what kept this
   buildable in one sitting.
2. **Decide the math before writing the prompt.** RICE and ICE are exact
   formulas - working those out first (reach × impact × confidence / effort)
   made it obvious exactly which four or three numbers to ask the model for, and
   in what ranges. A vague prompt like "score this feature" would produce
   inconsistent, unscalable output; asking for specific bounded fields
   (impact as one of five fixed values, confidence 0-100) makes the output
   both parseable and comparable across runs.
3. **Match by name, not by position.** Early designs that assume "item N in
   the response is item N in the request" break the moment the model
   reorders or skips something. Requiring the feature name in each response
   object and matching on it - with a hard error if any are missing - trades
   a little prompt verbosity for a pipeline that fails loudly instead of
   silently misattributing scores.
4. **Test the CSV edge cases as much as the LLM parsing.** Real backlog
   exports have blank rows, a `name` column instead of `feature`, extra
   columns. `test_prioritization_logic.py` covers those before it ever mocks
   a the model response, because a CSV parsing bug is a much more embarrassing
   demo failure than an LLM hiccup.
5. **Compute scores in Python, not in the prompt.** Asking an LLM to also do
   the arithmetic invites rounding/formula drift between runs. Splitting
   "the model estimates, Python computes" keeps the score function unit-testable
   with exact expected numbers (see `TestComputeScore`), independent of
   whatever the model returns.
