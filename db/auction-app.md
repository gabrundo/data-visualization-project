# Mantra auction app

The local auction app records confirmed purchases in PostgreSQL and uses the
current Fantacalcio Mantra eligibility catalogue. Each fantasy team has 500
credits, a minimum of three goalkeepers and twenty outfield players, and no
upper limit on either role group. The minimum purchase price is one credit.

## Installation and startup

Use the existing `.env` PostgreSQL configuration. On an existing database,
install the statistics views first if needed, then the additive auction tables:

```bash
uv sync
docker compose exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < db/init/002_player_metrics.sql
uv run python -m project.web.migrate
uv run uvicorn project.web.app:app --host 127.0.0.1
```

Open <http://127.0.0.1:8000>. Settings opens on first use; enter league team names
and select your team. The catalogue, APIs and static frontend share one process.
The English interface displays auction times in Europe/Rome; recorded timestamps
use PostgreSQL `timestamptz`. No login or automatic refresh service is included.
Keep the listener on loopback for local single-user use.

`003_auction.sql` runs automatically on a fresh Docker volume after migrations
001 and 002. Its tables and indexes can also be installed repeatedly on existing
databases. It adds `fantasy_team`, `auction_settings`, `auction_sale`,
`auction_request`, `context_snapshot` and `context_entry`; existing player,
football-club and performance tables remain intact.
`004_three_goalkeepers.sql` updates existing auctions to three goalkeeper slots;
`005_uncapped_squads.sql` removes squad caps, using NULL for `maximum_outfield`.
The migration command applies all three files and preserves all recorded sales. Back up the database and
source cache using the repository's existing backup instructions.

## Recording and correcting purchases

Type part of a player's name, use Up/Down and Enter to select a suggestion, then
Tab to the buying team and price. Enter records the sale and returns focus to
the player input. The team dropdown remembers its previous selection. Selecting
a sold suggestion or using Edit corrects that player's buyer and price; Delete
refunds its credits and returns the player to the available pool. Undo removes
the newest remaining recorded sale, even if an older sale was edited more
recently. Settings allows team renames, changing your team, and removing teams
that own no players. Type RESET to confirm refunding and deleting all sales.

The server locks the singleton auction settings row before every mutation. It
validates the entire proposed purchase within that transaction, then returns the
resulting state only after commit. Editing excludes the old sale when calculating
the proposed buyer's budget and slots. Failed validation rolls back the write.
Read responses use a repeatable-read transaction for consistent squads and totals.

For a proposed purchase, the maximum bid is:

```text
remaining budget − max(3 − goalkeepers after purchase, 0)
                 − max(20 − outfield after purchase, 0)
```

An empty team can bid 478 credits. With at least 3 goalkeepers and 20 outfield players
purchased, the next optional outfield player requires no reserve for other
optional slots. Additional goalkeepers and outfield players are allowed while
budget permits. The UI announces minimum completion at 3 + 20.

Each sale-create request includes a UUID idempotency key. The frontend retains
that key and the form values after an uncertain response. Repeating the same
request returns the current committed auction state; reusing a key for different
values is rejected. Receipts remain after edit, delete, undo or reset so a delayed
retry cannot recreate a removed sale. A fresh intended sale needs a new key.

Sales and roster CSV files include internal IDs, buyer, role group, integer
price and timestamp. Strings that could be interpreted as spreadsheet formulas
are prefixed with an apostrophe in exports.

## Statistics and coverage

Collect the opening season with the existing resumable scraper:

```bash
uv run python -m project.etl.scrape_seasons --seasons 2026 --matchdays 1 2 3 4 5
```

The auction query explicitly restricts 2026–27 observations and coverage to
matchdays 1–5. Importing round 6 or later cannot expand that window. Statistics
use the existing validated publisher/provider view; rated matches describe
rating observations, not verified appearances. Goals and assists sum the events
in those validated rated observations. Missing raw statistics remain null.

Expanded details show 2023–24, 2024–25 and 2025–26 separately, plus the opening
window, with FV sample counts, imported fixtures and complete matchdays. The
comparison table shows 2025–26 and opening-window FV, rated matches, goals and
assists. Players without history remain visible.

The default ranking is a heuristic, with fixed weights:

```text
H = 0.60 × S2025 + 0.30 × S2024 + 0.10 × S2023
C = max(opening mean FV, 0) × opening FV sample count / 5
score = 0.80 × H + 0.20 × C
```

`S` is the existing `season_weighted_score`: nonnegative mean FV × FV sample
count / 38, requiring 2–38 FV samples. `C` requires 2–5 valid FV observations.
Missing or unusable components contribute zero without redistributing their
weights. If none is usable, the player remains unranked; unranked players sort
last in either direction. A score is provisional if any historical collection
is incomplete or the opening collection has fewer than five complete rounds.
Scores describe observed contribution and do not set auction prices.

The 6 October 2026 opening import collected 50 fixtures and 1,590 performance
records. The live eligibility catalogue contained 531 players, including 455
with usable ranking evidence. Coverage reports remain in the ignored source
cache; they are refreshed for each scraper command.

## Manual context imports

[Context snapshots and source review](../context/README.md) lists the preserved
supplied expectations, reviewed aliases, mapping reports, and official dated
updates for all twenty clubs. Import them with:

```bash
uv run python -m project.etl.import_context context/supplied-2026-10-06.json \
  --aliases context/aliases.json --report context/mapping-review.json
uv run python -m project.etl.import_context context/verified-2026-10-06.json \
  --aliases context/aliases.json --report context/verified-mapping-review.json
```

For a future update, create a new snapshot JSON with an `entries` list. Each entry
has `club`, optional player `name`, `fields`, `source_url`, timezone-aware
`retrieved_at`, optional `observed_at`, and boolean `verified`. Accepted example:

```json
{
  "entries": [{
    "club": "Parma",
    "fields": {"manager": "Alberto Gilardino"},
    "source_url": "https://www.parmacalcio1913.com/en/main-news/alberto-gilardino-e-il-nuovo-allenatore-del-parma-calcio/",
    "observed_at": "2026-09-29T12:00:00+02:00",
    "retrieved_at": "2026-10-06T18:00:00+00:00",
    "verified": true
  }]
}
```

The command also accepts the supplied `serie_a_2026_27` shape and translates its
Italian context fields. Use `--dry-run` to review names before writing. Aliases
use `Club|Supplied name` keys with canonical catalogue names or internal integer
IDs. Normalize case and accents; do not use fuzzy name matching. Club matches
must agree with current eligibility. Ambiguous, unmatched and club-conflicting
entries remain in the report and storage; they never create players or change
Mantra roles. `Konate A.` at Parma remains unmatched in the supplied snapshot.

Original JSON is preserved in `context_snapshot.raw_values` with a SHA-256,
source URI and retrieval/observation metadata. Identical content is imported
once; validate aliases before the first import. Submit later corrections as a
new dated snapshot. Per-field display precedence prefers verified records, then
the latest observation or retrieval date within that class. A verified explicit
null clears a stale field. Player records from another club are excluded.
Details display the value, evidence type, source link and both dates. Supplied
starter percentages and duties remain expectations; dated availability reports
do not establish a player's present fitness. Automatic news collection is deferred.

## JSON API

| Method and path | Behavior |
| --- | --- |
| GET `/api/catalogue` | Eligibility, historical/window metrics and resolved context |
| GET `/api/state` | Settings, squads, budgets, reserves and sales |
| PUT `/api/settings` | Team list with existing IDs or null for new teams; `my_team_index` |
| POST `/api/sales` | `player_id`, `buyer_id`, `price`, UUID `idempotency_key` |
| PUT `/api/sales/{id}` | Correct buyer/price for the same `player_id` |
| DELETE `/api/sales/{id}` | Remove and refund one sale |
| POST `/api/undo` | Remove newest remaining recorded sale |
| POST `/api/reset` | `confirmation: "RESET"` and current settings `revision` |
| GET `/api/export/sales.csv` | All auction sales |
| GET `/api/export/roster/{id}.csv` | One fantasy team's roster |

Validation failures return 409 with a specific reason. Invalid request types
return 422. Database errors return a safe retryable 503 without credentials or
SQL parameters. Reset rejects a stale revision so a confirmation cannot clear
an auction that changed since it was reviewed. API documentation is at `/docs`.

## Verification

```bash
HISTORICAL_DB_TESTS=1 uv run python -m unittest discover -s tests -v
node tests/frontend.test.mjs
```

The 50 Python tests passed with isolated PostgreSQL schemas, covering auction
budget/slot boundaries, concurrent requests, duplicate retries, corrections,
refunds, undo, rollback, reload persistence, CSV exports, additive installation,
fixed opening-window aggregation, weighting and context mapping/precedence.
Existing missing historical fixture files were restored from their documented
cached sources; parsed observations were checked for equality before compression.

The JavaScript harness exercises the shipped frontend with a DOM test double:
all role filters, sorting and nulls, accent matching, keyboard selection,
sold-player editing, failed saves, idempotent retry, focus return, escaped content
and loading retry. A 1,000-player fixture took approximately 3.5 ms to filter/sort
and 1.7 ms to autocomplete in the local JavaScript runtime. These measurements
exclude browser rendering.

Real-browser visual QA was unavailable because this session exposed no connected
browser. Before using the app at an auction, check the keyboard flow in a browser
at desktop and tablet widths, confirm the sidebar moves below the main area
below 780 px, inspect table scrolling/dialog layout, and check live status
announcements with assistive technology. The responsive styles and visible focus
states are implemented; the DOM harness does not verify their rendering.
