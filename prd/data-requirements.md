# Data requirements

## Existing files

The project contains these Excel inputs:

- `data/Quotazioni_Fantacalcio_Stagione_2026_27.xlsx`
- `data/Statistiche_Fantacalcio_Stagione_2023_24.xlsx`
- `data/Statistiche_Fantacalcio_Stagione_2024_25.xlsx`
- `data/Statistiche_Fantacalcio_Stagione_2025_26.xlsx`
- `data/Statistiche_Fantacalcio_Stagione_2026_27.xlsx`

The quotations workbook includes player ID, name, team, Mantra role (`RM`), quotations, and valuation fields including `FVM M`. Statistics workbooks contain season aggregates and use `Rm` for Mantra roles. Headers follow an initial title row.

The user considers the spreadsheets insufficiently detailed for the intended analysis. They cannot supply match-to-match variability on their own. Their completeness and extraction dates must be checked before using them as reconciliation totals.

## Matchday source

URL pattern:

```text
https://www.fantacalcio.it/voti-fantacalcio-serie-a/<season>/<match_day>
```

Sample inspected: [2026–27, matchday 2](https://www.fantacalcio.it/voti-fantacalcio-serie-a/2026-27/2).

The sample HTML exposes fixtures, player profile links containing IDs, and ratings and event counts in `data-value` attributes. Decimal values can use a comma. The page contains separate rating columns for Redazione Fantacalcio, Voto Statistico, and Voto Italia. **Select Redazione Fantacalcio explicitly.**

Direct HTML extraction appears feasible for the inspected sample; this does not establish historical-page compatibility. An HTML parser should extract attributes before pandas processes the records. Plain table-text extraction may omit the numeric values.

## Collection requirements

1. Validate the parser on a current-season page and historical samples before collecting the full period.
2. Collect all available matchdays for the three historical seasons and completed available fixtures in 2026–27.
3. Record the requested season and matchday, source URL, retrieval timestamp, and actual fixture date where available.
4. Cache original downloads, use paced requests, and allow interrupted collection to resume.
5. Validate returned season and matchday; detect redirects, empty pages, and incomplete fixtures rather than silently accepting them.
6. Make repeated imports safe: update or reconcile existing records instead of creating duplicates.
7. Keep missing, unrated, and numeric-zero values distinct. Do not interpret an absent player row as proof of non-participation without checking source semantics.
8. Exclude coach rows from player statistics.
9. Preserve source values and flag parsing failures or unexplained scoring discrepancies.

## Proposed database structure

Pandas will handle extraction and transformation into a database. The repository already includes pandas, openpyxl, and SQLAlchemy dependencies. PostgreSQL in Docker Compose and an initial SQL schema are now defined; see [database design](../db/README.md) and [startup instructions](../README.md). Collection pipelines and ORM integration remain to be implemented.

| Entity | Purpose and principal fields |
| --- | --- |
| Player | Source player ID, name |
| Player-season eligibility | Player, season, eligible Mantra roles, source snapshot date |
| Fixture | Source fixture ID if available, season, matchday, actual date, home/away teams, final score, status |
| Player-fixture performance | Player, fixture, team at that fixture, provider, match rating, published Fanta Voto, event counts, appearance/rating status |
| Valuation snapshot | Player, season, snapshot date, source quotation and valuation fields |
| Collection record | Source URL, retrieval time, cached file, collection/parsing status |

Preserve fixture-level team membership so mid-season transfers do not overwrite history. Use current-season roles for current auction eligibility while retaining historical role information. Validate source IDs across files and pages; do not rely on names alone for joins.

### Performance fields

Required where published: goals, goals conceded, own goals, penalties scored/missed/saved, assists, yellow cards, red cards, match rating, and Fanta Voto. Preserve other source event categories without assuming league-specific scoring weights.

Desirable if reliably available: minutes, starter/substitute status, and actual appearance status. Do not claim these fields are available until extraction is verified. Check whether penalty goals are included in total goals before reconstructing fantasy scores.

## Validation and completion criteria

- Sample parsed records match the source, including provider selection, decimal values, event counts, and unrated cases.
- Fixture and player-performance keys are unique; repeated imports do not duplicate records.
- A coverage summary identifies missing or incomplete matchdays, fixtures, and player joins.
- Current-season data are clearly distinguished from completed historical seasons.
- Season aggregates are compared with the Excel files where their coverage and definitions align; differences are investigated rather than silently corrected.
- Cached source data and documented collection steps make the dataset reproducible.
