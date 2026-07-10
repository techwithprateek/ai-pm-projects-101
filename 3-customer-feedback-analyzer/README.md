# Guide: Customer Feedback Analyzer

## What this is

Upload raw customer feedback - a CSV with a `review_text` column, like an
export of App Store reviews, support tickets, or a Kaggle product-review
dataset - and the model tags every comment with a sentiment (positive / neutral
/ negative) and 1-3 themes (pricing, bugs, customer support, etc). The app
aggregates that into a sentiment breakdown and a ranked list of top themes,
each with an example quote pulled straight from the data.

`sample_feedback.csv` is 40 hand-written reviews shaped like a typical Kaggle
product-review dataset (`review_id, product, rating, review_text`), covering
a realistic spread of themes (bugs/reliability, billing/pricing, support
responsiveness, onboarding, performance, feature requests) so the aggregation
step has something real to rank. Swap in an actual Kaggle CSV (e.g. an Amazon
or SaaS review dataset) by pointing the uploader at it - the parser only
requires a text column, matched against `review_text`, `feedback`, `comment`,
`text`, or `review`.

## Where the value actually is for a PM

The interesting product question in the brief is "where does data come from,
what insights are valuable, how do you visualize them" - not "can an LLM
label text as positive or negative." So this app is built to demonstrate the
part after labeling: turning per-comment tags into a small set of *ranked,
quotable, actionable* themes a product team would actually put in a roadmap
review, rather than a wall of individually-tagged rows.

## How it works

**Architecture:**

```
app.py (Streamlit: upload, charts, per-theme example quotes)
   -> feedback_logic.py (CSV parsing, batching, prompt building, aggregation)
        -> llm_client.py (call_llm: prompt in, text out)
             -> OpenAI API
```

**The pipeline (`analyze_feedback`):**

1. `parse_feedback_csv` reads the CSV, tolerant of column-name variants, and
   assigns a stable id to every row (from `review_id`/`id` if present,
   otherwise the row number) so results can always be matched back to source
   rows.
2. `chunk` splits feedback into batches (default 20 rows) before prompting.
   Larger datasets get analyzed in multiple the model calls instead of one giant
   prompt - this keeps each call's output bounded and reliable, and is the
   same batching pattern you'd need for any "run an LLM over every row of a
   file" tool once the file is bigger than a demo dataset.
3. `build_analysis_prompt` lists each batch as `id: "text"` and asks for a
   JSON array of `{id, sentiment, themes}`, explicitly instructing the model to
   *reuse* theme tags across items instead of inventing a new phrase per
   comment - the whole point of asking one model to tag everything is that
   themes stay consistent enough to aggregate, which per-row human tagging
   often doesn't achieve.
4. `parse_analysis_json` validates each entry (rejects an unrecognized
   sentiment value outright rather than silently keeping it) and matches
   back to source rows by id, raising `FeedbackAnalysisError` if any id in
   the batch didn't come back.
5. Aggregation is plain Python, not another LLM call: `sentiment_counts`
   tallies positive/neutral/negative (always reporting all three, even at
   zero, so a chart doesn't silently drop a category), and `top_themes` uses
   `collections.Counter` to rank themes by frequency. `example_quote` pulls
   the first matching review for a theme, so every chart bar links back to a
   real sentence, not just a number.

**Charts:** sentiment breakdown uses the fixed status palette (green/amber/
red) because sentiment *is* a status, and status colors are reserved for
that - never reused as a generic series color. Top themes is a single-hue
blue bar chart sorted by count, because ranking by frequency is a magnitude
encoding, not an identity one - a rainbow of colors there would imply
categories that don't exist. Both charts use direct value labels on the bars
instead of relying on an axis, since the exact counts are the point.

## How to run it

```bash
cd 3-customer-feedback-analyzer
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your OPENAI_API_KEY
streamlit run app.py
```

Check "Analyze the sample feedback instead of uploading" to try it without a
CSV of your own.

Run the tests (no API key needed - everything is mocked):

```bash
pytest
```

## How this was vibecoded

1. **Batch before you prompt.** The naive version of this app calls the model
   once per row. That's slow, expensive, and loses the benefit of the model
   seeing related comments together. Deciding on batching (`chunk` +
   `batch_size`) up front - and testing it directly
   (`test_batches_and_aggregates` asserts exactly 2 calls for 3 rows at batch
   size 2) - was the first real design decision, before any prompt wording.
2. **Ask for consistent labels, not just labels.** The prompt explicitly says
   to reuse theme tags rather than invent new ones per item. Without that
   line, an LLM will happily tag "the checkout page crashed" and "app keeps
   freezing" as two different themes, and your aggregation step becomes
   useless. This is the single highest-leverage sentence in the prompt.
3. **Validate the vocabulary, not just the shape.** `parse_analysis_json`
   doesn't just check that `sentiment` is present - it checks the value is
   one of exactly three allowed strings and raises immediately if not. An
   LLM will occasionally return `"mixed"` or `"very positive"`; catching that
   at the parsing boundary means the aggregation code downstream never has
   to handle an unexpected category.
4. **Separate "what the model does" from "what the chart shows."** Sentiment
   counting and theme ranking are both one-liners with `Counter` - there's no
   reason to ask an LLM to also do the aggregation math. Keeping that in
   plain, tested Python (`TestAggregation`) means the charts are always
   correct given the per-row tags, regardless of anything about the prompt.
5. **Pick chart color by what the data means, not by what looks nice.**
   Sentiment is a status (good/warning/critical), so it gets the reserved
   status palette; theme frequency is a ranked magnitude, so it gets one
   sequential hue instead of a categorical rainbow that would wrongly imply
   the themes are unrelated categories rather than a ranked list. Deciding
   this before writing any chart code avoided the most common chart mistake:
   picking colors first and finding a design reason for them later.
