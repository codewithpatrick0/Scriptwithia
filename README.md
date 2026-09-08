# Scriptwithia

A Python CLI that enriches a CSV of companies with an LLM, through the [Groq](https://groq.com/) API.

You give it a CSV with `company_name` and `raw_description`. It gives back every original row plus four inferred fields:

| Field | Description | Values |
|---|---|---|
| `industry` | The company's main industry | Lowercase, up to 3 words |
| `estimated_company_size` | Estimated headcount range | `1-10`, `11-50`, `51-200`, `201-1000`, `1000+`, `unknown` |
| `one_line_summary` | A one-line description ready for outreach | Up to 20 words |
| `confidence_level` | Confidence in the generated fields | `high`, `medium`, `low`, `unknown` |

The two categorical fields are restricted to a closed vocabulary, so the result can be filtered and sorted without cleaning it first.

## Why

Lead-enrichment work asks for the same judgment call over and over: given a raw lead, infer fields that are implied by the text but never stated outright. By hand it is slow and inconsistent between reviewers.

This automates the first pass while keeping a human in the loop. Original columns are never touched, and every row carries a confidence level so the weak inferences are easy to pull out for manual review — the "don't guess, mark it for review" rule that shows up in real briefs.

## How it works

**One company per request, not the whole file in one prompt.** The CSV is read into a list of rows, and each row gets its own small call that returns just the four new fields, merged back in Python.

```
sample_input.csv  →  [ row1, row2, row3, ... ]
                          │
                          ▼
                     one call per row  →  { the four new fields }
                          │
                          ▼
                     row + fields  →  output.csv  and  output.json
```

That costs one API call per row, and buys three things:

- **The original data never passes through the model.** It cannot drop rows, reorder them, or quietly reword a description.
- **The prompt stays the same size** no matter how big the file is, so a large CSV does not degrade the results or hit a context limit.
- **A bad response breaks one row, not the run.** The rest keep going.

## Error handling

- Network hiccups, timeouts and rate limits are retried up to 3 times, waiting 3 seconds between attempts.
- A wrong API key, wrong permissions or a wrong model name stop the run immediately — those fail identically on every row, so retrying each one only burns calls.
- A row whose response is unusable is skipped with a message, and the run ends with a count of what was dropped, so a partial result is never mistaken for a complete one.
- The response is rebuilt from the four expected fields before merging: anything unexpected is dropped, anything missing or outside the allowed values becomes `unknown`.
- Writing the output reports success or failure per file instead of failing silently, and refuses to write an empty result.

## Setup

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/), and a Groq API key ([console.groq.com/keys](https://console.groq.com/keys)).

```bash
git clone https://github.com/codewithpatrick0/Scriptwithia.git
cd Scriptwithia
uv sync
cp .env.example .env
```

Then put your key in `.env`:

```
GROQ_API_KEY=your_groq_api_key_here
```

`.env` is gitignored and must never be committed.

## Usage

```bash
uv run scriptwithia
```

It asks for two names, both **without** the extension — the input CSV, then a base name for the outputs:

```
Enter the CSV filename WITHOUT the .csv extension: sample_input
recognizing CSV...
Extracting the final information ...
All 4 rows were processed.
All done!
Name for the new JSON and CSV files, WITHOUT extension: sample_output
Migrate to archive JSON ...
Done!
Migrate to archive CSV ...
Done!
Process completed.
```

`sample_input.csv` is the file this was built and tested against, and `sample_output.csv` / `sample_output.json` are the real result of that run, committed as-is so you can see the actual output without spending a call.

## Project structure

```
Scriptwithia/
├── src/
│   └── scriptwithia/
│       ├── script.py        # Reading, prompting, calling, validating, writing
│       └── settings.py      # Loads GROQ_API_KEY from .env
├── sample_input.csv
├── sample_output.csv
├── sample_output.json
├── .env.example
└── pyproject.toml
```

Model: `openai/gpt-oss-120b` via Groq, changeable in `call_llm()`.

## Limitations

- **Results are not reproducible run to run.** The vocabulary fixes the format, not the judgment. Across two runs of the same file the sizes came back identical while one row moved from `medium` to `high`. Treat `confidence_level` as a triage signal, not a stable key.
- **One API call per row.** Fine for a few hundred leads, slow and expensive for tens of thousands.
- **Calls run one at a time,** with no rate limiting and no concurrency.
- **File names are typed at a prompt,** not passed as command-line arguments, so it cannot be scripted or piped yet.
- **The input columns are not checked before starting,** so a CSV with the wrong headers spends API calls before the problem shows.
- **No tests.**
