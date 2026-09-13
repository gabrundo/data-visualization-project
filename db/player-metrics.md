# Player statistics views

The views in [002_player_metrics.sql](init/002_player_metrics.sql) compare players
with a validated 2026–27 eligibility snapshot. Each row describes **one player
and one performance season**, with Redazione Fantacalcio ratings. They retain
2023–24 through 2026–27 separately and include players without historical data.

## Installation and access

New empty Docker volumes install both schema and views automatically. For an
existing database, apply the views explicitly from the project directory:

```bash
docker compose exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < db/init/002_player_metrics.sql
```

The script runs in one transaction. When upgrading the former SD-based schema,
it rebuilds the managed statistics views to remove obsolete columns; subsequent
runs use `CREATE OR REPLACE VIEW`. Tables and imported observations are preserved.
The upgrade uses no `CASCADE`: additional dependent views cause an error and
rollback so they can be migrated explicitly. Custom grants on rebuilt views must
be reapplied. Do not delete the Docker volume to install it. These are ordinary
views: subsequent imports are reflected when queried without a refresh.

Update queries using removed `sd_fv`, `consistency_penalty`, or
`consistency_adjusted_score` columns. Use the FV percentiles for the distribution
and `season_weighted_score` for the score before the role-specific card preference.
Existing `median_fv` and `lower_quartile_fv` remain aliases for P50 and P25.

Open psql:

```bash
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

Find candidates for the M/C slot using the last completed historical season:

```sql
SELECT player_name, current_team, roles, rated_matches, fv_matches,
       round(mean_voto, 2) AS mean_voto,
       round(mean_fv, 2) AS mean_fv,
       round(fv_p25, 2) AS fv_p25,
       round(fv_p50, 2) AS fv_p50,
       round(fv_p75, 2) AS fv_p75,
       round(100 * fv_season_fraction, 1) AS season_sample_pct,
       round(100 * fv_ge7_rate, 1) AS strong_return_pct,
       round(100 * card_rate, 1) AS card_pct,
       card_sample,
       round(candidate_score, 3) AS candidate_score,
       evidence_status, coverage_status
FROM position_m_c_statistics
WHERE performance_season = 2025
ORDER BY candidate_score DESC NULLS LAST, fv_matches DESC, player_name
LIMIT 30;
```

Use `performance_season = 2026` for the opening current-season observations.
Always select a season and explicitly order `DESC NULLS LAST`; views do not
guarantee row order. The eligibility season stays 2026 even when examining 2025
performance. Inspect coverage before interpreting a low season fraction.

```sql
SELECT DISTINCT performance_season, coverage_status, imported_fixtures,
                complete_matchdays
FROM player_season_metrics
ORDER BY performance_season;

SELECT player_name, performance_season, bonus_matches, bonus_sample, bonus_rate,
       source_goals, goal_sample, assists, assist_sample,
       penalties_scored, penalties_missed, penalty_attempts,
       penalty_conversion_rate
FROM role_t_statistics
WHERE performance_season = 2025
ORDER BY candidate_score DESC NULLS LAST, player_name;
```

Use `\d+ player_season_metrics` to inspect all metric columns, `\dv` to list
views, and `\q` to exit. Full definitions are in the SQL and the
[position metrics PRD](../prd/position-metrics.md).

## Views by role and position

| Use | View names |
| --- | --- |
| Current eligible identities and role arrays | `current_eligible_player` |
| Core metrics, one row per player/season | `player_season_metrics` |
| All individual roles | `player_role_statistics` (filter `role`) |
| Individual role views | `role_por_statistics`, `role_dd_statistics`, `role_ds_statistics`, `role_dc_statistics`, `role_b_statistics`, `role_e_statistics`, `role_m_statistics`, `role_c_statistics`, `role_w_statistics`, `role_t_statistics`, `role_a_statistics`, `role_pc_statistics` |
| All 4-2-3-1 positions | `player_position_statistics` (filter `position`) |
| Single-role positions | `position_por_statistics`, `position_dd_statistics`, `position_ds_statistics`, `position_dc_statistics`, `position_m_statistics`, `position_t_statistics` |
| Alternative-role positions | `position_m_c_statistics`, `position_w_t_statistics`, `position_w_a_statistics`, `position_a_pc_statistics` |

Alternative-role views use OR membership and return each player once per season.
The Dc position has two starting slots, but its candidates are not duplicated.
These views implement direct eligibility from the supplied formation. Special B
compatibility, adapted substitutions, and a legal eleven-player selection solver
are not implemented.

## FV percentiles

All core, role, and position statistics expose `fv_p10`, `fv_p25`, `fv_p50`,
`fv_p75`, and `fv_p90`. They use `PERCENTILE_CONT` on valid non-null FV values
within **one player and one season**, with the same source and validation rules
as mean FV. They are not percentile ranks against other players.

P25 and P75 bound the middle half of the distribution; P50 is the median.
P10 and P90 describe more extreme results and are particularly sensitive to
small samples. These are descriptive landmarks, not confidence intervals or
guaranteed future floors/ceilings. Interpolation can produce values never
observed in a match: for FV `[4, 10]`, P25 is 5.5 and P75 is 8.5.

No valid FV gives NULL percentiles. One FV gives that value at all five
percentiles, but the player remains unranked. Always show `fv_matches` and
`evidence_status`; percentiles do not make a small sample reliable. Retain mean
FV and the below-6/at-least-7/at-least-8 frequencies: equal quartiles can conceal
different tails. `median_fv = fv_p50` and `lower_quartile_fv = fv_p25`.

For E-role analysis:

```sql
SELECT player_name, fv_matches, round(mean_fv, 2) AS mean_fv,
       round(fv_p10, 2) AS p10, round(fv_p25, 2) AS p25,
       round(fv_p50, 2) AS p50, round(fv_p75, 2) AS p75,
       round(fv_p90, 2) AS p90,
       round(100 * fv_lt6_rate, 1) AS below_6_pct,
       round(candidate_score, 3) AS candidate_score,
       evidence_status, coverage_status
FROM role_e_statistics
WHERE performance_season = 2025
ORDER BY candidate_score DESC NULLS LAST, fv_matches DESC, player_name;
```

## Weighting and interpretation

The settings view exposes these editable starting preferences:

```text
season_games = 38
card_risk_weight = 0.25

fv_season_fraction = valid FV count / 38
observed_fv_per_season_game = observed FV sum / 38
season_weighted_score = fv_season_fraction * max(mean FV, 0)
card_rate = rated matches with a yellow OR red card / rated matches with both flags known
candidate_score, defensive and central-midfield roles
  = season_weighted_score * (1 - 0.25 * card_rate)
candidate_score, other roles = season_weighted_score
```

The card preference applies to **Dd, Ds, Dc, B, E, M, C**, and to the Dd, Ds,
Dc, M, M/C formation positions. W, T, A, Pc, and Por still expose card statistics
but receive no extra discount. A C/T player's core metrics are identical in both
tables; the explicit preference differs according to the role being compared.

The SD penalty has been removed: high positive returns should not reduce the
score merely by increasing dispersion. Percentiles describe downside and upside
without adding another penalty. The nonnegative score floor is retained.
The 0.25 card coefficient is a heuristic preference, not a fitted probability,
official fantasy scoring, or an auction value. A 40%
card frequency yields a 10% preference discount. Published FV already includes
card effects; the extra factor expresses the user's additional aversion to
disciplinary risk and must not be described as a correction to FV. Yellow and
red frequencies/totals remain separate; flags do not reveal second-yellow
sequences or suspension duration.

Season-weighted and candidate scores remain NULL for fewer than two FV
observations as an evidence rule, independent of percentile calculation.
Over-38 FV samples are flagged and unranked. No-history players remain visible
with zero observed counts and NULL event totals/averages/rates/scores. A player
with no usable card observations has NULL card rate and NULL card-adjusted score,
rather than being treated as card-free. Event sample sizes remain visible when
only some rated observations have known values. The 15-observation evidence
label is descriptive; it does not hide players or establish statistical confidence.

The season fraction measures **observed rated contribution out of 38**, not
appearance probability, injury risk, or registration-adjusted availability.
An opening two-game sample contributes 2/38; it is not extrapolated to a full
season and must not be ranked against full previous seasons. Missing imports,
transfers, and missing history can also lower the fraction. Coverage is reported
as complete (380 validated fixtures across 38 ten-fixture matchdays), partial,
or uncollected. Partial collections can bias comparisons even within a season.

All `*_rate` fields are fractions from 0 to 1; multiply by 100 for percentages.
Threshold rates use valid FV count; event rates use their known-event sample.
Season threshold fractions divide the corresponding counts by 38. Goals remain
the source category; scored penalties are not added to it without verified
overlap semantics. Event totals cover evaluable rated observations, not inferred
actual appearances. Team clean-sheet context, per-90 metrics, true availability,
forecasting, and auction prices remain separate future work.

## Validation

```bash
HISTORICAL_DB_TESTS=1 uv run python -m unittest discover -s tests -v
```

The statistics tests create and remove a disposable schema with a synthetic
38-round season. They exercise percentile interpolation, missing FV, single
observations, equal-mean distributions without a variability penalty, card
discounts, missing events/history, all role filters, overlapping position pools,
source isolation, partial current seasons, validation failures, legacy migration,
protection of external dependent views, and repeated installation.
