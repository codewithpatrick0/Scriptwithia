# Scriptwithia

A Python script that enriches a CSV of companies using an LLM through the [Groq](https://groq.com/) API.

Given a CSV with `company_name` and `raw_description` columns, the model returns each original row extended with four inferred fields:

| Field | Description | Values |
|---|---|---|
| `industry` | The company's main industry | Lowercase, up to 3 words |
| `estimated_company_size` | Estimated headcount range | `1-10`, `11-50`, `51-200`, `201-1000`, `1000+`, `unknown` |
| `one_line_summary` | A concise one-line description ready for outreach | Up to 20 words |
| `confidence_level` | Confidence in the generated fields | `high`, `medium`, `low`, `unknown` |

The two categorical fields are restricted to a closed vocabulary, so the output can be filtered, sorted and grouped without cleaning it first.

## Why

Freelance data-enrichment jobs almost always ask for the same kind of judgment call: given a raw lead (a name, a title, a short description), infer structured fields like industry, seniority, or company size — fields that are usually implicit in the text, not handed to you directly. Doing that by hand for a few hundred leads is slow and inconsistent between reviewers.

This project automates the first pass of that judgment call with an LLM, while keeping a human (or a downstream reviewer) in control: nothing is guessed silently, every original field is preserved untouched, and a `confidence_level` is attached to every row so low-confidence inferences are easy to flag for manual review — the same "don't guess, mark it for review" principle that shows up in real lead-enrichment briefs.

## How it works: row-by-row analysis

The key design decision of this project is that **the LLM analyzes one company at a time, not the whole CSV in a single prompt.**

The file is parsed with `csv.DictReader` into a list of dictionaries, and `analyze_dicts()` iterates over them, issuing one focused request per row. Each response comes back as a JSON object holding only the four new fields, which is then merged into its source row with `dict_ | response`.

```
sample_input.csv
      │
      ▼
 analyze_csv()          csv.DictReader  →  [ {row1}, {row2}, {row3}, ... ]
      │
      ▼
 analyze_dicts()        for each row:
      │                     craft_prompt(row)   →  prompt for ONE company
      │                     call_llm(prompt)    →  {"industry": ..., ...}
      │                     row | response      →  enriched row
      ▼
 [ {row1 + 4 fields}, {row2 + 4 fields}, ... ]
      │
      ▼
 migrate_json()  +  migrate_csv()   →   <name>.json  and  <name>.csv
```

This is more efficient and far less error-prone than sending the entire file in one prompt:

- **Deterministic parsing.** Each call returns a small JSON object requested with `response_format={"type": "json_object"}`, so the output is parsed with `json.loads()` instead of hoping the model reproduces valid CSV. No stray markdown fences, no explanatory text, no broken quoting.
- **No data loss or hallucinated rows.** The original data never passes through the model — the prompt explicitly forbids repeating input fields, and the source row is preserved verbatim on the Python side. The model cannot drop rows, reorder them, invent companies, or silently rewrite a description.
- **Bounded context per call.** The prompt size stays constant regardless of how large the input file is, so the script does not degrade as the CSV grows or hit the context limit on a large file.
- **Focused attention.** The model reasons about a single company per request rather than splitting its attention across dozens, which yields more consistent classifications.
- **Isolated failures.** A malformed response affects one row instead of invalidating the entire output.

The trade-off is one API call per row instead of one per file. That is the cost paid for reliability.

## Error handling

Failures are contained at several levels, so a bad row or a flaky network never aborts the whole run.

**Transient failures are retried with backoff.** `call_llm()` wraps the request in a retry loop of up to 3 attempts, catching `APIConnectionError`, `APITimeoutError`, `RateLimitError` and `InternalServerError`. Each failed attempt waits 3 seconds before retrying, giving rate limits and transient network issues a moment to clear. If all three attempts are exhausted, the error propagates so the caller can decide what to do. Non-recoverable status errors (`APIStatusError` — bad request, bad credentials, missing model) are raised immediately without wasting retries.

**Bad rows are skipped, not fatal.** `analyze_dicts()` guards every iteration and uses `continue` to move on:

- `APIError` — the row exhausted its retries or hit an API error specific to that request.
- `json.JSONDecodeError` — the model returned something that is not valid JSON.

Either way the row is dropped with a message and the loop keeps going, so the remaining companies are still processed and whatever succeeded is returned.

**Run-wide failures stop immediately.** Not every API error deserves the same treatment. `AuthenticationError`, `PermissionDeniedError` and `NotFoundError` mean the API key, the permissions or the model name are wrong — a problem that affects every single row, so retrying per row only burns calls to fail identically. These are caught *before* the generic `APIError` handler and re-raised, and `main()` turns them into a clean abort message instead of a traceback. A bad API key now fails on the first row rather than after the whole file.

**Missing input is handled up front.** `analyze_csv()` catches `FileNotFoundError` and returns `None`; `main()` checks for it and exits cleanly instead of crashing.

**Categorical values are validated in two layers.** The prompt pins `estimated_company_size` and `confidence_level` to a closed vocabulary, which is what actually keeps the output consistent — the model has the context to map `team of 12` to `11-50`, and code does not. But a prompt is a request, not a guarantee, so `normalize()` runs on every parsed response before it is merged into its row: it strips and lowercases both fields, checks them against the allowed sets, and falls back to `unknown` for anything else. A missing field, a stray label like `40-50 employees`, or a bare number instead of a string all resolve to `unknown` instead of reaching the output. That last case would otherwise raise `AttributeError` on `.strip()`, so each field is guarded independently and the failure is reported rather than crashing the run.

**The merged row is built from a fixed set of fields.** `normalize()` does not edit the response in place — it builds a new dict from `FIELDS`, the four keys this project actually declares, so what reaches `dict_ | response` is a fixed shape regardless of what came back. Extra keys are dropped, which means a model that returns `company_name` despite the prompt forbidding it can no longer overwrite the original column; missing keys are filled with `unknown` instead of silently vanishing from the output. Deriving that set from the response itself would defeat the purpose, since the response is exactly the untrusted part. A response that is valid JSON but not an object is discarded before it gets there.

**Writes report success instead of failing silently.** `migrate_json()` and `migrate_csv()` each return a boolean flag rather than raising. Both refuse to write an empty result set — `migrate_json()` checks the length explicitly, `migrate_csv()` catches the `IndexError` raised when it reads the header from the first row — and both handle `OSError` on write, plus `TypeError` for non-serializable data and `ValueError` for rows that do not match the CSV header. `main()` reports the outcome per file instead of assuming the write worked.

## Requirements

- Python >= 3.12
- [uv](https://docs.astral.sh/uv/) for dependency management
- A Groq API key ([console.groq.com/keys](https://console.groq.com/keys))

## Installation

```bash
git clone https://github.com/codewithpatrick0/Scriptwithia.git
cd Scriptwithia
uv sync
```

## Configuration

Copy the example file and add your API key:

```bash
cp .env.example .env
```

Then edit `.env`:

```
GROQ_API_KEY=your_groq_api_key_here
```

`.env` is gitignored and must **never** be committed.

## Usage

```bash
uv run scriptwithia
```

Both prompts ask for names **without** an extension: first the input CSV, then a base name for the two output files it generates (a `.json` and a `.csv`, both enriched with the four new fields):

```
Enter the CSV filename WITHOUT the .csv extension: sample_input
recognizing CSV...
Extracting the final information ...
All done!
Name for the new JSON and CSV files, WITHOUT extension: sample_output
Migrate to archive JSON ...
Done!
Migrate to archive CSV ...
Done!
Process completed.
```

`sample_input.csv` is the example this project was built and tested against, and `sample_output.csv` / `sample_output.json` are the real result of the run above — committed as-is, so you can see the actual model output without spending an API call. Every categorical value in that sample falls inside the vocabulary, with no normalization fallback triggered.

Expect your own run to differ slightly. The vocabulary fixes the *format*, not the *judgment*: across two runs of this same file the `estimated_company_size` values came back identical, while one row moved from `medium` to `high`. `confidence_level` is the model's own assessment of an inference, so it is the field most likely to shift between calls. Reproducing an exact run is not something this script guarantees — treat `confidence_level` as a triage signal for manual review, not as a stable key.

## Project structure

```
Scriptwithia/
├── src/
│   └── scriptwithia/
│       ├── __init__.py      # Package marker
│       ├── script.py        # Main logic: parsing, prompting, LLM calls, output
│       └── settings.py      # Environment loading via pydantic-settings
├── sample_input.csv         # Example input
├── sample_output.csv        # Real enriched output from sample_input.csv
├── sample_output.json       # Same result in JSON
├── .env.example             # Environment variable template
└── pyproject.toml
```

### Components

- **`settings.py`** — defines `Settings` with `pydantic-settings`, reading `GROQ_API_KEY` from `.env` and failing at startup if it is missing.
- **`script.py`** — the full pipeline:
  - `analyze_csv(csv_archive)` parses the file with `csv.DictReader` and returns a list of dicts.
  - `craft_prompt(dict_company)` builds the prompt for a single company, requesting only the four new fields and pinning the two categorical ones to a closed vocabulary.
  - `call_llm(prompt)` calls the model in JSON mode, retrying transient failures up to 3 times with a 3-second backoff.
  - `normalize(response)` rebuilds the response from the four declared `FIELDS`, strips and lowercases the categorical ones, and falls back to `unknown` for anything missing or outside the allowed sets.
  - `analyze_dicts(list_dicts)` loops over the rows, normalizes and merges each response into its source row, and skips rows that fail.
  - `migrate_json(final_list, json_name)` / `migrate_csv(final_list, csv_name)` write the enriched data to disk and return a success flag.
  - `main()` orchestrates the pipeline end to end.

## Model

Currently uses `openai/gpt-oss-120b` via Groq. It can be changed in `call_llm()` inside `src/scriptwithia/script.py`.

## Project status

Working end to end: input validation, row-by-row enrichment, retries with backoff, response validation against a fixed field set and vocabulary, and dual-format output (JSON + CSV) with explicit success/failure reporting. Still pending:

**Error handling**

- [ ] Skipped rows are printed as they happen but never summarized — the run ends without reporting how many rows were dropped or which ones.

**Features**

- [ ] No rate limiting between calls, and calls run sequentially (concurrency would cut runtime significantly).
- [ ] Accept the CSV path as a command-line argument instead of `input()`.
- [ ] Validate the input CSV has the expected columns before spending API calls.
- [ ] Tests.
