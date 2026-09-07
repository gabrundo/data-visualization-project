# Historical collection validation — 2026-09-07

Collected all 114 requested Fantacalcio.it matchday pages using
`uv run python -m project.etl.scrape_seasons`. Ratings and Fanta Voto use
Redazione Fantacalcio consistently.

| Season | Matchdays | Fixtures | Player performances | Distinct players | Rated | Unrated |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2023–24 | 38 | 380 | 11,902 | 587 | 10,805 | 1,097 |
| 2024–25 | 38 | 380 | 11,886 | 598 | 10,719 | 1,167 |
| 2025–26 | 38 | 380 | 11,926 | 586 | 10,787 | 1,139 |
| Total | 114 | 1,140 | 35,714 | — | 32,311 | 3,403 |

No missing matchdays, incomplete fixtures, unknown rating statuses, invalid
performance-team associations, or numeric parsing issues were found. Counts
describe the source's published player rows; they do not establish actual
appearance totals or reasons for absent rows. Historical aggregate Excel
workbooks were unavailable, so independent season-total reconciliation remains
deferred.

The database now contains 1,170 canonical players, including the original 531.
Of those original players, 389 have historical performances in this collection;
the other 142 retain missing history rather than zero-valued performances.
All original player names, 531 eligibility snapshots, and 825 role records
were compared against the pre-import backup and are unchanged. Name variants
such as accents and shortened names remain in raw historical observations.

The pre-import data-only backup is under
`backups/before-historical-20260907T185631Z/`. Its `schema.sql` and `data.sql`
were restored into a disposable schema and all table counts checked. Restore
these files in order into an empty database; this backup is not a `pg_dump`
custom-format archive. The backup directory is ignored by Git.

Original HTML, retrieval metadata, the latest `coverage.json`, and the
`database-validation.json` comparison results are under
`data/cache/fantacalcio/` (ignored by Git). Preserve these alongside database
backups. The README documents collection and resume commands.

Validation: 18 automated tests pass, including source samples from all three
seasons, provider selection, unrated values, cards/events, retry/cache behavior,
incomplete-page rejection, transactional rollback, idempotent imports, and
historical transfers in isolated PostgreSQL schemas.
