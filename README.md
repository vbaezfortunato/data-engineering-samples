# Data engineering samples: API integration, ETL, SQL, SAS

![Python tests](https://github.com/vbaezfortunato/data-engineering-samples/actions/workflows/tests.yml/badge.svg)

Small, runnable examples of the backend and data engineering work I do day to day: pulling data from REST APIs, cleaning messy vendor feeds, correcting data safely in SQL Server, and doing the same transformation in SAS.

Everything here uses **invented records**. These are independent portfolio examples, not copies of any employer's code, and they contain no real credentials, hostnames, report IDs, or personal records.

## What each project shows

| Folder | Problem | What it demonstrates |
|---|---|---|
| [`api_integration/`](api_integration/) | Export a paginated report from a REST API without leaking personal data | Token authentication (JSON or plain-text token), pagination with a safety limit, payload validation, **field allowlisting** so unapproved fields never reach the CSV, and secrets read from environment variables |
| [`book_adoption/`](book_adoption/) | Two bookstore vendors send textbook data in different layouts | Normalizing two schemas into one, splitting compound `CRN\|TERM` references, mapping legacy term codes (`J24` → `202420`), keeping ISBNs as text so leading zeros survive, parsing the "New" price from free text, and a record-count check after loading |
| [`sql/`](sql/) | Fix malformed course references already stored in a table | A **transactional correction** that saves the term before trimming, validates the result, and rolls back automatically if validation fails. It runs on any SQL Server, because it builds its own temp table |
| [`sas/`](sas/) | Same parsing rule in SAS | A DATA step using `index` / `scan` to split compound references |
| [`tests/`](tests/) | Prove it works | 8 unit tests, including a mocked live API run (plain-text token, two pages, empty last page), run on every push by GitHub Actions |

## Run it

Python 3.10+, standard library only. Nothing to install.

```bash
python -m unittest discover -s tests -v
python -m api_integration.extract_report --mock --output output/sample_report.csv
python -m book_adoption.etl --db output/book_adoption_demo.sqlite
```

Expected output:

```
Ran 8 tests ... OK
Exported 3 records to output/sample_report.csv
{'feed_a': 3, 'feed_b': 3, 'loaded': 6}
```

**SQL:** open `sql/course_crn_fix.sql` in SSMS or Azure Data Studio and run it. It prints the table before and after the correction.
**SAS:** run `sas/composite_crn_example.sas` in SAS Studio.

### Live API mode

Set these environment variables, then run without `--mock`:

| Variable | Meaning |
|---|---|
| `API_BASE_URL` | Base URL of the API |
| `API_TENANT_ID` | Tenant / business entity ID |
| `API_KEY` | Web services key |
| `API_REPORT_ID` | Report to export |

Live mode is covered by a mocked test, but it hasn't been run against a real API in this repository.

## Design choices

- **Allowlist, not blocklist.** The export lists the fields it *may* write, so a new field added upstream (for example, a personal identifier) is dropped by default.
- **Fail loudly on bad input.** Malformed API payloads, missing term codes, or missing book identifiers raise errors instead of loading partial data.
- **Identifiers are text.** ISBNs, CRNs, and term codes are never converted to numbers.
- **Make corrections safe to re-run.** The SQL fix only touches rows that still need fixing, and it commits only after validation passes.

## Author

Vidal Baez Fortunato: data systems architect (SQL Server, SAS, Power BI, Python) · [LinkedIn](https://www.linkedin.com/in/vidal-baez-fortunato)
