# AI PM Projects 101

A portfolio of five small, end-to-end AI products, each built the way a product
manager would "vibe code" a prototype: describe the outcome you want, let
an AI write the code, run it, poke at it until it's actually useful, then
write down what you learned.

Every project is a self-contained Streamlit app backed by the OpenAI API, with
its own tests and its own `GUIDE.md` that explains two things:

1. **How it works** — the architecture, the prompt design, the data flow.
2. **How it was vibecoded** — the actual prompt-build-test loop used to get
   from idea to working app, so you can repeat the process on your own ideas.

## Projects

| # | Project | What it does |
|---|---------|---------------|
| 1 | [PRD Generator](./1-prd-generator) | Turns a rough feature idea + research notes into a structured PRD, then critiques and scores its own draft. |
| 2 | [Feature Prioritization Copilot](./2-feature-prioritization-copilot) | Upload a backlog CSV, get RICE/ICE scores and a ranked, exportable list. |
| 3 | [Customer Feedback Analyzer](./3-customer-feedback-analyzer) | Turns raw customer comments into themes, sentiment, and charts. |
| 4 | [Idea Rater](./4-idea-rater) | Type a product idea, answer a few clarifying questions, get pros/cons and a score. |
| 5 | [Weekly Update Writer](./5-weekly-update-writer) | Paste messy notes from the week, get a clean update ready to send to your manager. |

## Running any project

Each project is independent — its own `requirements.txt`, its own virtualenv.

```bash
cd 1-prd-generator          # or any other project folder
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then add your OPENAI_API_KEY
streamlit run app.py
```

## Running tests

Every project separates **logic** (prompt building + response parsing, pure
functions) from the **UI** (Streamlit). The logic modules are unit tested with
the OpenAI API mocked out, so tests run offline, fast, and without an API key.

```bash
cd 1-prd-generator
pip install -r requirements.txt
pytest
```

## Why these five

They're the five ideas from the "AI PM Projects" brief: a mix of pure
LLM-prompting products (Idea Rater, Weekly Update Writer), a structured
generation + self-critique loop (PRD Generator), a file-upload-and-score tool
(Prioritization Copilot), and a data analysis + visualization tool (Feedback
Analyzer). Together they cover the core shapes of "AI feature" a PM is likely
to prototype or ship.
