# Database design

PostgreSQL links analysis records using foreign keys and unique constraints.
JSONB preserves varying workbook columns and original parsed values. Original
HTML/Excel downloads stay on disk, referenced by collection records; back up
these cached files alongside the database.

| Table | Purpose |
| --- | --- |
| `data_source` | Source namespace, such as Fantacalcio.it |
| `collection_record` | Retrieval/import attempt, URI, timestamp, cache path, status and errors |
| `season` | Season start year: 2026 means 2026–27 |
| `player` | Canonical player |
| `player_source_id` | Source player ID mapped to canonical player |
| `team` | Canonical club; importers explicitly reconcile source names |
| `player_season_snapshot` | Dated player/team/eligibility observation |
| `player_snapshot_role` | One Mantra role per snapshot, allowing multiple roles |
| `fixture` | Serie A home/away pairing per season, independent of rescheduling |
| `fixture_source_id` | Optional published fixture ID mapping |
| `player_fixture_performance` | Player/fixture/source/ratings-provider observation |
| `valuation_snapshot` | Published quotation and valuation fields at a snapshot time |
| `season_statistics_snapshot` | Workbook aggregate fields for reconciliation |

The fixture key assumes Serie A league matches. Supporting other competitions
or repeated home/away pairings would require extending it.

## Import conventions

- Resolve players through source IDs, never names alone. Excel and web records
  from the same publisher share a namespace after verifying their IDs.
- Create collection records before importing rows. Use transactions for validated
  batches and retain failed/incomplete attempts in the collection log.
- Use `INSERT ... ON CONFLICT ... DO UPDATE` against unique keys for repeatable
  imports. Constraints reject duplicates; they do not implement an importer.
- Snapshot times represent source publication/extraction, not every reimport.
  Reuse the same timestamp for the same file. If unknown, retain first retrieval
  time and document that assumption in source data.
- Preserve team membership on performances and roles on dated snapshots. Use
  the latest validated 2026 snapshot for auction eligibility. Transfers must
  not overwrite earlier observations.
- Select `Redazione Fantacalcio` explicitly for analysis. The source is the
  publisher; the provider is the rating system within its data.
- Missing values use SQL `NULL`; zero remains zero. Known unrated cases use
  `rating_status = 'unrated'`; unknown appearance is `NULL`. Exclude coaches.
  Preserve original tokens in `raw_values` and issues in `validation_issues`.
- Store published Fanta Voto and raw events separately; never add bonuses twice.
  D-Factor is not a player-level adjustment.
- Preserve quotation column names, including `FVM M`, in valuation `values`.
  These are not auction prices. Workbook totals belong in season-statistics
  `values` and must not be converted into fabricated fixture observations.
- Importers must check performance teams belong to fixtures, returned
  season/matchday match requests, and source coverage is valid. Database keys
  alone cannot validate source semantics.

`001_schema.sql` is the authoritative initial schema. The existing Python
`src/project/db/models.py` is an unfinished scaffold and is not used by this
setup. ORM mappings and collection pipelines can be added against this schema.

## Connect to DB via shell

```bash
docker compose exec db sh -c 'psql -U fantacalcio -d fantacalcio'
```