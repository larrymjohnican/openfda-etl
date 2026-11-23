# openFDA → SQL Server Data Pipeline

[![CI](https://github.com/larrymjohnican/openfda-etl/actions/workflows/ci.yml/badge.svg)](https://github.com/larrymjohnican/openfda-etl/actions/workflows/ci.yml)

An incremental ETL pipeline that ingests FDA adverse drug event reports from the public [openFDA API](https://open.fda.gov/apis/), validates and flattens deeply nested JSON, and loads it into a normalized SQL Server schema — running end to end in Docker.

Built to be **idempotent**: the pipeline can be re-run any number of times without duplicating data, resuming automatically from the last date it successfully loaded.

---

## Architecture

```
openFDA API                  Python pipeline                    SQL Server 2022
(drug/event.json)   ──────>  ingest → validate → load   ──────>  (Docker container)
                             · pagination                         · Adverse_Events
                             · retry + backoff                    · Event_Drugs
                             · data quality checks                · Event_Reactions
                             · nested JSON flattening

                    all orchestrated by docker-compose
```

### Data flow

1. **Ingest** (`pipeline/ingest.py`) — pulls reports from openFDA one day at a time, paginating within each day past the API's 1,000-record-per-call limit. Wrapped in retry logic with exponential backoff.
2. **Validate** (`pipeline/validate.py`) — drops records with missing IDs, duplicate IDs, or malformed dates, logging each rejection with its specific reason. Also flattens the nested `patient.drug[]` and `patient.reaction[]` arrays into row-shaped records.
3. **Load** (`pipeline/load.py`) — writes each report and its children to SQL Server in a single transaction, deleting any prior version of that report first.
4. **Orchestrate** (`pipeline/main.py`) — the entry point. Reads the high-water mark from the database, computes the date range to fetch, and drives the three stages in order.

---

## Database schema

A parent–child model that preserves the one-to-many relationships in the source data. A single adverse event report can name multiple drugs and multiple reactions, so those become child tables rather than being flattened into a single wide row.

**`Adverse_Events`** — one row per FDA report
| Column | Type | Notes |
|---|---|---|
| `safetyreportid` | `VARCHAR(20)` | Primary key. Source-native identifier (string, not numeric) |
| `receivedate` | `DATE` | Incremental high-water-mark key |
| `serious` | `VARCHAR(10)` | FDA code |
| `seriousnessdeath` | `VARCHAR(10)` | FDA code |
| `seriousnesshospitalization` | `VARCHAR(10)` | FDA code |
| `primarysourcecountry` | `VARCHAR(10)` | |
| `patientonsetage` | `VARCHAR(10)` | Stored raw — source is not reliably numeric |
| `patientsex` | `VARCHAR(10)` | FDA code |

**`Event_Drugs`** — many rows per report
| Column | Type | Notes |
|---|---|---|
| `drug_id` | `INT IDENTITY` | Surrogate primary key |
| `safetyreportid` | `VARCHAR(20)` | Foreign key → `Adverse_Events` |
| `medicinalproduct` | `VARCHAR(255)` | Brand/product name |
| `activesubstancename` | `VARCHAR(255)` | Generic substance |
| `drugcharacterization` | `VARCHAR(10)` | 1 = suspect, 2 = concomitant, 3 = interacting |
| `drugindication` | `VARCHAR(255)` | What the drug was prescribed for |

**`Event_Reactions`** — many rows per report
| Column | Type | Notes |
|---|---|---|
| `reaction_id` | `INT IDENTITY` | Surrogate primary key |
| `safetyreportid` | `VARCHAR(20)` | Foreign key → `Adverse_Events` |
| `reactionmeddrapt` | `VARCHAR(255)` | MedDRA preferred term (the reaction itself) |
| `reactionoutcome` | `VARCHAR(10)` | FDA outcome code |

Both child tables are indexed on `safetyreportid` to keep the incremental delete step fast.

FDA numeric codes are stored **raw**, exactly as the API returns them, rather than being decoded during ingestion. Storing source data faithfully and decoding downstream keeps the load layer simple and avoids baking assumptions into the warehouse.

---

## Key design decisions

### Parent–child modeling over a flat table

The source JSON nests arrays of drugs and reactions inside each report. The simpler approach would have been to keep only the first drug and first reaction, producing one wide flat row per report — but that discards real information. One report describing an interaction between four medications is meaningfully different from one naming a single drug.

The parent–child model preserves all of it, at the cost of a more involved load step (insert ordering, foreign keys, and a harder incremental strategy). It also recovers analytically useful fields like `drugcharacterization`, which only becomes meaningful once every drug on a report is stored.

### Idempotent loads via delete-and-reinsert

Because `receivedate` has only day-level precision, any incremental run overlapping a previously loaded day will re-encounter reports already in the database. With three linked tables, "skip the duplicate" isn't sufficient — the child rows would need reconciling too.

Instead, each report is loaded by deleting its existing rows (children first, then parent, respecting the foreign key) and inserting the fresh version, **all inside one transaction**. This handles both cases with the same code path: a report never seen before deletes nothing and inserts cleanly, and a re-seen report is replaced atomically. A failure mid-load rolls the whole thing back rather than leaving a half-updated report.

### High-water-mark resumption

On startup the pipeline queries `MAX(receivedate)` from `Adverse_Events` and begins fetching from that same day, not the day after. If a previous run died partway through loading a day, that day is only half loaded; starting from the day after would skip the rest of it forever. Re-fetching the watermark day is safe because loads are idempotent (below), so it costs a few extra API calls and closes the gap. On an empty database it falls back to a configured start date. No manual bookkeeping, no state file — the warehouse itself is the source of truth for what's been loaded.

Each day is fetched, validated and loaded before the next one is fetched, so a crash loses at most the day in flight.

### Retry classification

Not every failure is worth retrying. The pipeline distinguishes:
- **Transient** — connection errors, timeouts, and 5xx server responses → retried with exponential backoff (up to 4 attempts, 2s → 30s)
- **Permanent** — 4xx client errors → fail immediately, since retrying a bad request or exhausted quota only wastes time and API budget

A separate case: openFDA returns **HTTP 404** for a date window with no matching records rather than an empty result set. The pipeline translates that into a legitimate zero-result response instead of treating it as an error.

---

## Running it

### Prerequisites
- Docker Desktop
- A free [openFDA API key](https://open.fda.gov/apis/authentication/) (optional but strongly recommended — raises the rate limit from 1,000 to 120,000 requests/day)

### Setup

Create a `.env` file in the project root:

```
DB_HOST=localhost
DB_PASSWORD=YourStrongPassword123!
OPENFDA_API_KEY=your_key_here
FETCH_START_DATE=2026-03-10
```

`FETCH_START_DATE` is optional — it's only used as the backfill starting point when `Adverse_Events` is empty (defaults to `2026-03-10` if unset). Once the table has data, the pipeline ignores this and resumes from its own high-water mark instead.

### Run the full stack

```bash
docker compose up --build
```

This brings up SQL Server, waits for it to actually accept connections (via healthcheck), creates the database and schema, then runs the pipeline. The whole stack builds from nothing and is safe to re-run.

### Run locally against a containerized database

```bash
# start just SQL Server
docker compose up sqlserver db-init -d

# run the pipeline on the host
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
python -m pipeline.main
```

Individual modules can be run standalone for testing:
```bash
python -m pipeline.ingest     # fetch only
python -m pipeline.validate   # fetch + validate + sample extraction
python -m pipeline.load       # database connection smoke test
```

### Tests and lint

```bash
pip install -r requirements-dev.txt
ruff check .
python -m pytest
```

The tests need no database or API key. CI runs both on every push and pull request.

---

## Project structure

```
.
├── pipeline/
│   ├── ingest.py           # API calls, pagination, retry logic
│   ├── validate.py         # data quality checks, nested JSON flattening
│   ├── load.py             # database connection, transactional loads
│   └── main.py             # orchestration entry point
├── sql/
│   └── schema.sql          # idempotent DDL — creates database, tables, indexes
├── Dockerfile              # pipeline image (Python 3.12 + msodbcsql18)
├── docker-compose.yml      # sqlserver → db-init → pipeline
├── requirements.txt
└── .env                    # credentials (gitignored)
```

---

## Tech stack

**Python 3.12** · requests · SQLAlchemy · pyodbc · tenacity · python-dotenv · pandas
**SQL Server 2022** (Docker) · **Docker Compose** · ODBC Driver 18

---

## Notes on the data

**The loaded dataset currently covers March 11–24, 2026** (14 contiguous days, ~44,000 reports, ~153,000 drug rows, ~116,000 reaction rows).

openFDA's FAERS adverse-event data does not appear to be indexed continuously. Testing across a wide date range found a hard cutoff: dense, real daily volume through the end of Q1 2026 (March 31), then a flat wall of zero-result days for every date tested afterward — not a gradually shrinking gap, which is what a rolling indexing lag would look like. That pattern is consistent with a **quarterly publish cycle** rather than a fixed lag, though this project hasn't confirmed that against FDA's own documentation. Practically: expect recently-elapsed quarters to return nothing until openFDA's next data refresh, and pick backfill/demo date ranges from a quarter you've confirmed has data rather than assuming "N weeks ago" is safe.

Daily volume within an indexed period runs roughly 500–6,000 reports, with visible dips on weekends.

The 404-vs-empty-result handling in `fetch_reports` (see Design Decisions above) is what lets the pipeline walk through a long stretch of unindexed days without erroring — see [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for how that was diagnosed.

---

## Possible extensions

- **Batch inserts** — the current load is row-by-row transactional, which is correct but slow at volume (~70k reports takes tens of minutes). Batching would trade some transaction granularity for throughput.
- **Code decoding** — a dimension table mapping FDA numeric codes (`patientsex`, `serious`, `reactionoutcome`) to human-readable labels.
- **Orchestration** — the high-water-mark pattern maps directly onto Azure Data Factory watermarks or an Airflow DAG.
- **Parquet staging** — landing raw responses to Parquet before loading, for replayability without re-hitting the API.
