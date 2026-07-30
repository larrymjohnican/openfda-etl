# Troubleshooting Log

A record of the real problems hit while building this pipeline, what caused them, and how they were diagnosed and fixed. Kept because the debugging was most of the learning.

---

## 1. Windows: "Python was not found" after installing Python

**Symptom:** `winget install Python.Python.3.12` succeeded, but `python --version` returned "Python was not found; run without arguments to install from the Microsoft Store."

**Cause:** Two problems stacked. Windows ships a stub `python.exe` in `%LocalAppData%\Microsoft\WindowsApps` that intercepts the command and points at the Microsoft Store. Separately, the real install directory wasn't on PATH — `where.exe python` returned *only* the stub path, which was the giveaway.

**Fix:** Prepended the real install and its `Scripts` folder to the user PATH, and disabled the Store aliases under Settings → Apps → Advanced app settings → App execution aliases.

**Follow-on problem:** After fixing PATH, the terminal *still* couldn't find Python. `[Environment]::GetEnvironmentVariable("Path","User")` showed the correct value, proving the change had persisted — but the running shell had captured its environment at launch and never saw it. VS Code compounds this: it hands every integrated terminal the environment from when the *application* started, so opening a new terminal tab isn't enough — the whole app has to restart.

**Takeaway:** When a tool "isn't found" right after installing it, check whether the saved PATH and the *session's* PATH disagree. The bulletproof escape hatch is calling the executable by full path, which ignores PATH entirely.

---

## 2. Running modules: `ImportError` and `ModuleNotFoundError`

**Symptom:** `from pipeline.ingest import fetch_date_range` failed with `ModuleNotFoundError: No module named 'pipeline'`.

**Cause:** The file was being run by direct path (`python c:/.../pipeline/validate.py`), usually via VS Code's Run button. Running a file directly tells Python only about that file's own folder — it has no idea a package named `pipeline` exists one level up.

**Fix:** Run modules with `python -m pipeline.validate` from the project root. The `-m` form resolves `pipeline` as a package relative to the current directory.

**Takeaway:** In a multi-file package, `-m` isn't a style preference — it's what makes cross-module imports resolve at all.

---

## 3. Script ran with no output and no error

**Symptom:** `python -m pipeline.ingest` returned instantly, printing nothing. No traceback either.

**Cause:** The editor tab showed an unsaved-changes indicator. Python executes what's saved on disk, not what's in the editor buffer — so it ran an older version of the file that had no print statements.

**Fix:** Save before running. Better: turn on auto-save.

**Takeaway:** "No output *and* no error" usually means the code that ran isn't the code on screen.

---

## 4. openFDA 403 Forbidden

**Symptom:** After several test runs, every API call returned `403 Client Error: Forbidden`.

**Cause:** Rate limiting. Without an API key, openFDA allows 240 requests/minute and 1,000/day per IP. Repeated debugging runs — including ones that silently fired requests before the save issue above was found — exhausted the quota.

**Fix:** Requested a free API key (instant, email only), stored it in `.env` as `OPENFDA_API_KEY`, and passed it as a query parameter. This raises the ceiling to 120,000 requests/day, which the pagination phase needs anyway.

**Takeaway:** Handling API authentication and rate limits is part of building a pipeline, not an obstacle to it. Diagnosing it correctly meant reading the status code rather than assuming the code was broken.

---

## 5. Date range query returning zero results

**Symptom:** The search parameter `receivedate:[{start}+TO+{end}]` returned nothing.

**Cause:** `requests` URL-encodes the literal `+` characters when building the query string, mangling openFDA's range syntax.

**Fix:** Used spaces instead — `receivedate:[{start} TO {end}]` — which encode predictably.

---

## 6. Silent double-counting: the date boundary bug

**Symptom:** A three-day pull returned 21,946 reports, of which the validation layer flagged **8,231 as duplicates — 37% of the batch.** Far too many to be incidental.

**Cause:** openFDA's date range is **inclusive on both ends**. The daily loop was building each window as `[today TO tomorrow]`, using the next day as an exclusive-style boundary. But since both ends are inclusive, every day was fetched twice: once as the tail of one window and once as the head of the next.

**Fix:** Query a single day as `[today TO today]` — the same date on both ends.

**Verification:** After the fix, the same three-day range returned 9,739 reports with **zero duplicates**, and the per-day counts summed exactly to the total.

**Takeaway:** This is the bug the validation layer paid for itself catching. Without duplicate detection it would have silently loaded inflated data. It's also a reminder to verify whether a date-range API is inclusive or exclusive rather than assuming — the same trap exists in watermark-based incremental patterns generally.

---

## 7. Wrong nested field name

**Symptom:** Every extracted reaction had a null reaction name.

**Cause:** The code read `reactionmeddraversion`, which doesn't exist. The actual keys are `reactionmeddraversionpt` (the MedDRA dictionary *version number*, e.g. `"26.1"`) and `reactionmeddrapt` (the actual reaction, e.g. `"Dry eye"`). A plausible-looking guess that returned `None` silently instead of erroring.

**Fix:** Read `reactionmeddrapt`, confirmed against a raw JSON sample.

**Takeaway:** Nested field names must be verified against real data. Defensive `.get()` chaining prevents crashes, but it also means a wrong key fails *quietly* — worth spot-checking extracted output rather than trusting that no error means correct.

---

## 8. `.env` committed to git

**Symptom:** Noticed `.env` had been pushed to GitHub, containing the SQL Server password and openFDA API key.

**Cause:** `.gitignore` only ignores files git isn't **already tracking**. The `.env` had been committed before the ignore rule existed, so adding it afterward had no effect.

**Fix:** `git rm --cached .env` to untrack it while keeping the local file, then commit. Because the secrets remained in git history, both were treated as compromised and rotated.

**Takeaway:** Create `.gitignore` with `.env` in it as the *first* commit, before the file exists. And when a secret leaks, rotating it is the fix that matters — scrubbing history is secondary.

---

## 9. Forgotten SA password

**Symptom:** `KeyError: 'DB_PASSWORD'` — the `.env` had the API key but never got the database credentials, and the container's password had been set weeks earlier and forgotten.

**Cause:** Environment variables were added one at a time across phases; the database pair was skipped. The password itself existed only in shell history.

**Fix:** No recovery path for a forgotten SA password — recreated the container with a new one, which wipes its storage. `FdaDB` and all three tables were rebuilt in seconds by re-running `sql/schema.sql`.

**Takeaway:** The moment a password goes into a `docker run` command, it goes into `.env` in the same breath. Also: this is exactly why the schema lives in a version-controlled file rather than only in a query editor's history.

---

## 10. Querying the wrong database

**Symptom:** After a successful load reporting 1,508 records, `SELECT COUNT(*)` returned **0** for all three tables.

**Cause:** The query editor's active database context was `master`, not `FdaDB` — visible in the connection bar but easy to overlook, since the *connection profile* was named after the database. The Python pipeline was unaffected because its connection string names `FdaDB` explicitly.

**Fix:** `SELECT DB_NAME()` to confirm the actual context, then `USE FdaDB;` before querying. Row counts immediately showed the real data: 1,508 / 6,411 / 5,018.

**Related:** A separate incident in the same file — leftover `DELETE FROM` statements from an earlier cleanup were sitting above the count queries, and the extension's default Run action executes the *entire file*, not just the highlighted lines. The counts were accurate; the tables had just been emptied a millisecond earlier.

**Takeaway:** When results contradict what the application reports, verify you're looking at the same database. And never leave destructive statements in a scratch file you re-run casually.

---

## 11. Docker build failure: `apt-key: not found`

**Symptom:** The image build failed at the ODBC driver install with `/bin/sh: 1: apt-key: not found`, exit code 127.

**Cause:** The unpinned `python:3.12-slim` tag had moved to a Debian 13 (trixie) base, and `apt-key` — deprecated for years — was removed in that release. The Microsoft package repo URL also targeted Debian 12, mismatching the base.

**Fix:** Pinned the base image to `python:3.12-slim-bookworm` (Debian 12), and replaced `apt-key add` with the modern keyring approach: `gpg --dearmor` into `/usr/share/keyrings/` plus a `signed-by=` reference in the sources list.

**Takeaway:** Unpinned tags silently move to new base OS versions and break builds without any change on your end. Pinning is what makes builds reproducible.

---

## 12. Compose: login failed, then database not found

Two failures in sequence, each one representing progress.

**First — `Login failed for user 'sa'` (error 18456, state 7).** The timestamps told the story: SQL Server logged "ready for client connections" and the failed login arrived ~100ms later, while the container was still finalizing system database setup. `depends_on` only waits for the container *process* to start, not for the database to be usable.

**Fix:** Added a healthcheck that actually runs `SELECT 1` via `sqlcmd` every 10 seconds, and changed the pipeline's dependency to `condition: service_healthy`.

**Second — `Cannot open database "FdaDB"`.** Expected: authentication now succeeded, but the composed SQL Server was a brand-new instance with only system databases. The previously loaded data lived in a *different* container.

**Fix:** Added a one-shot `db-init` service that runs `sql/schema.sql` against the fresh instance and exits, with the pipeline depending on `condition: service_completed_successfully`.

**A wrinkle along the way:** the obvious image for the init container, `mcr.microsoft.com/mssql-tools18:latest`, doesn't exist. Reused the SQL Server image itself, which already contains `sqlcmd` — no extra pull, and the healthcheck had already proven the binary path.

**Takeaway:** In compose, "the container started" and "the service is ready" are different things. And a failing error that's *further along* than the last one is progress.

---

## 13. Schema script not re-runnable

**Symptom:** Anticipated rather than hit — the second `docker compose up` would fail, because `CREATE TABLE` against an existing table errors, `db-init` would exit non-zero, and the pipeline (gated on `service_completed_successfully`) would never start.

**Fix:** Guarded every object: `IF DB_ID(...) IS NULL` for the database, `IF OBJECT_ID(...) IS NULL` for tables, `IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = ...)` for indexes.

**Verification:** Ran `docker compose up` twice against a persisted database. The second run's `db-init` completed cleanly and the pipeline started — which, given the dependency condition, is itself proof that db-init exited zero.

**Takeaway:** Setup scripts need the same idempotency as the pipeline's data loads. Converge to a target state; don't error because the state already exists.

---

## 14. Interrupted long-running load

**Symptom:** A load of 71,623 reports had to be stopped partway through, leaving 57,934 loaded and a partially-loaded day at the boundary.

**Assessment:** No corruption — each report loads inside its own transaction, so every report that completed is fully consistent, including its child rows. The result was an incomplete but internally valid dataset.

**Takeaway:** Per-report transactions mean an interrupted run degrades gracefully instead of leaving broken data. Separately: row-by-row transactional loading is correct but slow at this volume, which is a real argument for batching in a production version.
