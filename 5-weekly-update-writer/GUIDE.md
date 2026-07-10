# Guide: Weekly Update Writer

## What this is

Paste your rough, messy notes from the week - half-sentences, fragments,
whatever you jotted down - and the model organizes them into a clean status
update: what got done, what's in progress, what's blocked, and what's next.
Pick a tone (concise or detailed) and an audience (manager, team,
stakeholders), and copy the result straight into Slack or email.

This is the simplest of the five projects on purpose: one text box in, one
LLM call, one clean result out. It's here to show the smallest *correct*
version of that shape - most people's first AI side project looks exactly
like this, and the difference between a toy and something you'd actually use
weekly is in the details below, not in added complexity.

## How it works

**Architecture:**

```
app.py (Streamlit: notes input, tone/audience pickers, formatted output)
   -> update_logic.py (build prompt, parse response, format message)
        -> llm_client.py (call_llm: prompt in, text out)
             -> OpenAI API
```

**The single prompt (`build_update_prompt`):** takes the raw notes plus a
`tone` (concise/detailed) and `audience` (manager/team/stakeholders), and
asks the model to bucket the notes into four categories - accomplishments,
in_progress, blockers, next_steps - as JSON. Two instructions in the system
prompt matter more than they look:

- **"Only use what's actually in the notes... don't pad it with filler."**
  Without this, an LLM asked to fill four categories will often invent a
  plausible-sounding blocker or generic next step to avoid leaving a section
  empty. For a real status update, a fabricated blocker is worse than an
  empty section - it's the one failure mode of this app that would actually
  damage trust with your manager, so it's called out explicitly rather than
  assumed.
- **"You never invent accomplishments or metrics."** Same failure mode, more
  directly: this app must never make you look like you did something you
  didn't.

**Parsing:** `parse_update_json` requires only `accomplishments` to be
present (a week can genuinely have no blockers or next steps) and defaults
the other three lists to empty rather than raising - the schema is
deliberately permissive about *emptiness*, strict about *fabrication*.

**Formatting:** `WeeklyUpdate.to_message()` builds the final plain-text
version by skipping any section that's empty, so the output you copy-paste
never has a "Blockers: none" line cluttering an otherwise clean update.

## How to run it

```bash
cd 5-weekly-update-writer
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

1. **Find the one failure mode that actually matters and design against it.**
   For most of these five apps, a slightly-off LLM response is annoying. For
   this one specifically, a *fabricated* accomplishment or blocker is a
   credibility problem with your actual manager. That's why "never invent,
   never pad empty sections" is written directly into the system prompt
   instead of being left implicit - the one thing worth being paranoid about
   here is hallucination, not formatting.
2. **Make emptiness a valid, expected output.** `parse_update_json` only
   requires one key. A version that required all four categories to be
   non-empty would force the model to invent content for a category that
   genuinely has nothing in it this week - exactly the failure mode from
   point 1, introduced by an overly strict schema instead of a bad prompt.
3. **Keep the personalization surface small and explicit.** Tone and
   audience are the only two knobs, both closed enums (`TONES`, `AUDIENCES`)
   validated in `build_update_prompt` before any API call. That's enough
   variation to make the tool feel adaptable without turning "write my
   update" into a form with a dozen options nobody will actually use.
4. **Test that the knobs actually do something.**
   `test_detailed_tone_differs_from_concise` and
   `test_passes_tone_and_audience_into_prompt` aren't testing the model's
   output - they're testing that the app's own code correctly changes its
   behavior based on the tone/audience inputs. It's a cheap, fast way to
   catch a bug where a UI control is wired to nothing.
5. **Resist adding scope.** It would be easy to bolt on "save update
   history," "email integration," or "compare to last week's update." None
   of that was asked for, and each one adds state and failure surface to what
   is meant to be a five-minute-a-week tool. The one addition worth having -
   a plain-text, copy-paste-ready rendering (`to_message`) - exists because
   the whole point of the app is to produce something you paste somewhere
   else, not because it's a "nice to have."
