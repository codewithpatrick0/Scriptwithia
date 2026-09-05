# Scriptwithia

A Python script that enriches a CSV of companies using an LLM through the [Groq](https://groq.com/) API.

Given a CSV with `company_name` and `raw_description` columns, the model returns each original row extended with four inferred fields:

| Field | Description |
|---|---|
| `industry` | The company's main industry |
| `estimated_company_size` | Estimated size of the company |
| `one_line_summary` | A concise one-line description ready for outreach |
| `confidence_level` | Confidence level of the generated information |

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
```

This is more efficient and far less error-prone than sending the entire file in one prompt:

- **Deterministic parsing.** Each call returns a small JSON object requested with `response_format={"type": "json_object"}`, so the output is parsed with `json.loads()` instead of hoping the model reproduces valid CSV. No stray markdown fences, no explanatory text, no broken quoting.
- **No data loss or hallucinated rows.** The original data never passes through the model — the prompt explicitly forbids repeating input fields, and the source row is preserved verbatim on the Python side. The model cannot drop rows, reorder them, invent companies, or silently rewrite a description.
- **Bounded context per call.** The prompt size stays constant regardless of how large the input file is, so the script does not degrade as the CSV grows or hit the context limit on a large file.
- **Focused attention.** The model reasons about a single company per request rather than splitting its attention across dozens, which yields more consistent classifications.
- **Isolated failures.** A malformed response affects one row instead of invalidating the entire output.

The trade-off is one API call per row instead of one per file. That is the cost paid for reliability.

## Error handling

Failures are contained at two levels, so a bad row or a flaky network never aborts the whole run.

**Transient failures are retried.** `call_llm()` wraps the request in a retry loop of up to 3 attempts, catching `APIConnectionError`, `APITimeoutError`, `RateLimitError` and `InternalServerError`. Each failed attempt is reported; if all three are exhausted the error propagates so the caller can decide what to do. Non-recoverable status errors (`APIStatusError` — bad request, bad credentials, missing model) are raised immediately without wasting retries.

**Bad rows are skipped, not fatal.** `analyze_dicts()` guards every iteration and uses `continue` to move on:

- `APIError` — the row exhausted its retries or hit an unrecoverable API error.
- `json.JSONDecodeError` — the model returned something that is not valid JSON.

Either way the row is dropped with a message and the loop keeps going, so the remaining companies are still processed and whatever succeeded is returned.

**Missing input is handled up front.** `analyze_csv()` catches `FileNotFoundError` and returns `None`; `main()` checks for it and exits cleanly instead of crashing.

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

The script asks for the CSV filename (including the `.csv` extension) and prints the enriched rows:

```
Enter the full CSV filename, including .csv. sample_input.csv
recognizing CSV...
Extracting the final information ...
All done!
[{'company_name': 'Greenfield Roasters', 'raw_description': '...', 'industry': 'Food & Beverage - Specialty Coffee', 'estimated_company_size': '5-15', 'one_line_summary': '...', 'confidence_level': '0.90'}, ...]
```

`sample_input.csv` is included as a test file.

## Project structure

```
Scriptwithia/
├── src/
│   └── scriptwithia/
│       ├── __init__.py      # Package marker
│       ├── script.py        # Main logic: parsing, prompting and LLM calls
│       └── settings.py      # Environment loading via pydantic-settings
├── sample_input.csv         # Example CSV
├── .env.example             # Environment variable template
└── pyproject.toml
```

### Components

- **`settings.py`** — defines `Settings` with `pydantic-settings`, reading `GROQ_API_KEY` from `.env` and failing at startup if it is missing.
- **`script.py`** — the full pipeline:
  - `analyze_csv(csv_archive)` parses the file with `csv.DictReader` and returns a list of dicts.
  - `craft_prompt(dict_company)` builds the prompt for a single company, requesting only the four new fields.
  - `call_llm(prompt)` calls the model in JSON mode, retrying transient failures up to 3 times.
  - `analyze_dicts(list_dicts)` loops over the rows, merges each response into its source row, and skips rows that fail.
  - `main()` orchestrates the pipeline.

## Model

Currently uses `openai/gpt-oss-120b` via Groq. It can be changed in `call_llm()` inside `src/scriptwithia/script.py`.

## Project status

Working base version with error handling in place for network failures, API errors and malformed model responses. Still pending:

**Error handling**

- [ ] No backoff between retries — the 3 attempts fire back to back, which does not help on a rate limit that needs time to clear.
- [ ] The response contents are not validated: there is no check that the four expected fields are present, nor that `dict_ | response` is not silently overwriting original columns with model output.
- [ ] Skipped rows are printed as they happen but never summarized — the run ends without reporting how many rows were dropped or which ones.

**Features**

- [ ] Finish `migrate_json()` and write the result to a file instead of printing the raw list of dicts.
- [ ] No rate limiting between calls, and calls run sequentially (concurrency would cut runtime significantly).
- [ ] Accept the CSV path as a command-line argument instead of `input()`.
- [ ] Validate the input CSV has the expected columns before spending API calls.
- [ ] Tests.
