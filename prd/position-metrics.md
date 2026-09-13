# Position metrics and candidate comparison

## Decision and initial scope

Identify strong candidates for each position in the preferred 4-2-3-1 using
transparent, season-specific historical metrics. A strong candidate can offer
high typical performance, limited downside, frequent strong returns, or useful
coverage. Retain FV percentiles and raw metrics alongside the season-weighted
candidate score and defensive/midfield card preference.

The core, individual-role, and formation-position SQL views are implemented in
[002_player_metrics.sql](../db/init/002_player_metrics.sql). See
[access and weighting](../db/player-metrics.md) for installation, queries, and
the exact heuristic defaults. The interactive table and manual shortlist UI
remain proposed. Future score estimates and auction pricing are specified in
[score forecasting](score-forecasting.md).

## Position tables

Use one shared metrics dataset and ten position filters. The two Dc slots share
a comparison table, but a lineup requires two distinct players.

| Table | Direct eligible roles | Starting slots | Additional columns to emphasize |
| --- | --- | ---: | --- |
| Goalkeeper | Por | 1 | Goals conceded per evaluable rated match; penalty saves; team clean-sheet context |
| Right-back | Dd | 1 | Mean Voto; assists; card frequency |
| Centre-back | Dc | 2 | Mean Voto; poor-return frequency; cards; goals |
| Left-back | Ds | 1 | Mean Voto; assists; card frequency |
| Defensive midfield | M | 1 | Mean Voto; poor-return frequency; cards |
| Second central midfield | M or C | 1 | Bonus frequency; assists; strong-return frequency |
| Left attacking slot | W or T | 1 | Bonus frequency; strong returns; goals and assists |
| Central attacking midfield | T | 1 | Bonus frequency; strong returns; penalties |
| Right attacking slot | W or A | 1 | Bonus frequency; strong returns; goals and penalties |
| Forward | A or Pc | 1 | Goals; bonus frequency; strong returns; penalty attempts and conversion |

There are ten filters in this mapping: Por, Dd, Dc, Ds, M, M/C, W/T, T, W/A,
and A/Pc. Each filter uses OR membership, not an exact role-string match. For
example, M/C includes an M-only player and an M/C player exactly once each.
Retain a general role filter for E and B and for subsequent formation analysis.
Special role compatibility and substitutions must be verified before extending
the direct eligibility supplied in the user's diagram.

A player's raw statistical values do not change between position tables; their
comparison pool and relative standing can change. The candidate score additionally
applies the documented card preference in defensive and central-midfield positions.

## Dataset grain and joins

1. Select the latest validated eligibility snapshot per player/source for 2026,
   at or before the query time. Preserve all roles from that
   snapshot and its timestamp. Label its team as the current snapshot team.
2. Aggregate validated player-fixture observations by player, season, source,
   and provider before joining to roles. Use Redazione Fantacalcio only and
   completed fixtures within the selected season. The current views use live
   validated state, not a historical as-of reconstruction. Do not multiply performances
   by joining directly to multiple role records before aggregation.
3. Left-join aggregates to the eligible player pool so players without history
   remain visible. A missing season has no observed sample; averages and rates
   remain NULL. This does not establish zero appearances or zero season events.
4. Apply position membership after aggregation. A player may occur in several
   position tables, but only once per player/season in any one table.

Keep historical performance team membership separate from the current team.
Include season, cutoff, provider, eligibility timestamp, and collection coverage
in the dataset or its accompanying metadata. Never present missing collection
coverage as a player's absence.

## Core table layout

The initial comparison season is 2025–26, the latest complete historical season.
A season selector exposes 2023–24, 2024–25, and 2026–27 without mixing seasons.
Show current-season sample count and mean separately beside the selected history
or in row details; do not silently pool the opening games with prior seasons.

| Display column | Definition |
| --- | --- |
| Player / current team / roles | Identity and latest eligible snapshot; preserve multi-role combinations |
| Evidence | Valid Voto count, valid Fanta Voto count, missing-history and partial-coverage indicators |
| Mean Voto | Arithmetic mean of valid underlying ratings |
| Mean FV | Arithmetic mean of valid published Fanta Voto |
| FV P25 / P50 / P75 | Lower quartile, median, and upper quartile of valid FV |
| FV P10 / P90 | More extreme observed results; interpret with sample size |
| FV < 6 | Count and percentage of valid Fanta Voti strictly below 6 |
| FV ≥ 6 | Count and percentage at least 6 |
| FV ≥ 7 | Count and percentage at least 7 |
| FV ≥ 8 | Count and percentage at least 8; distinguishes particularly strong returns |
| Attacking bonus frequency | Count and percentage of evaluable rated observations with a goal, scored penalty, or assist |
| Penalties | Scored/attempted plus conversion percentage and event coverage |

Use `FV` as a compact label for published Fanta Voto. Thresholds are inclusive
where shown: ≥ 6 is not > 6. The ≥ 6, ≥ 7, and ≥ 8 groups overlap and must not
be added together. Display percentages alongside counts, such as `9/30 (30%)`.

To keep the default table readable, show player identity, sample count, mean
Voto, mean FV, P25/P50/P75 FV, FV < 6, and FV ≥ 7. P10/P90,
attacking bonus frequency, other thresholds, event breakdowns, and penalties remain selectable columns
or row details. Goalkeeper tables replace attacking bonus frequency with goals
conceded; other position-specific columns can be selected from the mapping above.

## Metric calculation rules

- Valid Voto observations have rated status, a non-null match rating, and no
  unresolved validation issue affecting the metric. Valid Fanta Voto observations
  additionally have non-null Fanta Voto. Expose both sample sizes when different.
- Rating means, quantiles, and thresholds each use their valid rating sample.
  Fanta Voto percentages use the valid FV count, not 38, imported team fixtures,
  or player rows including unrated observations. FV P10/P25/P50/P75/P90 use
  continuous interpolation (`PERCENTILE_CONT`) within each player/season.
  Null FV values are ignored; no FV yields NULL percentiles; one observation
  yields the same value at every percentile. Interpolated values need not be
  actual match scores. Retain `median_fv` and `lower_quartile_fv` as aliases
  for `fv_p50` and `fv_p25`. Percentiles are not guaranteed floors or ceilings.
- Initially define event frequencies and event-per-match rates on rated
  observations with known required event fields. Show the event denominator
  separately when it differs from the rating count. Label totals as observed
  rated-match totals, not full-season appearance totals.
- Attacking bonus frequency requires known `goals`, `penalties_scored`, and
  `assists` on each included observation. Count a match once if any is positive.
  Including penalties with OR avoids excluding penalty goals if the source's
  goal category excludes them, without counting them twice in the frequency.
- Show source goal counts and scored penalties separately. Do not sum them into
  total goals, or subtract penalties to infer non-penalty goals, until their
  overlap semantics are verified. Bonus volume and frequency are different.
- Penalty attempts are scored plus missed on the same observations where both
  are known. Conversion is total scored / total attempts; with zero attempts it
  is NULL, not 0%. Show the attempts count and do not infer current taker status.
- Card frequency counts evaluable rated matches with either a yellow or red
  flag, once per match. Keep the individual event totals in details. The source
  flags do not establish second-yellow sequences.
- Goalkeeper goals conceded per match uses known concession counts on rated
  observations. Penalty saves are an observed total; a save percentage is
  unavailable without a validated denominator of penalties faced.
- Team clean-sheet rate uses completed, validated team fixtures with known
  scores in an explicit season/window. Label it team context, not a player
  clean-sheet award or evidence the player appeared. Do not attribute a current
  team's earlier results to a player who was elsewhere.
- Missing events remain NULL; known zeroes remain zero. No per-90 metrics,
  actual appearance rate, injury inference, or starter rate until the necessary
  input semantics are established. A rated-match rate over eligible fixtures
  is deferred until registration/team-tenure coverage is reliable.

## Identifying strong candidates

Default to `candidate_score DESC NULLS LAST`, then FV sample descending and name.
The score weights nonnegative mean FV by `n / 38` and applies
the explicit card preference to Dd/Ds/Dc/B/E/M/C. Scores are unavailable with
fewer than two FV observations; no-history and single-observation players remain
visible. The exact formula, configurable constants, and missing-card treatment
are documented in [the database guide](../db/player-metrics.md). Always compare
the same season and inspect collection coverage. This is an observed-season
ranking preference, not a forecast or auction valuation.

Also offer three proposed raw-metric sorting presets, using full precision:

| Preset | Primary order | Secondary order | Interpretation |
| --- | --- | --- | --- |
| Overall contribution | Mean FV descending | Valid FV count descending | High observed average, with evidence visible |
| Reliable returns | FV < 6 ascending | Mean FV descending | Fewer poor returns; mean remains visible to distinguish consistently modest players |
| Strong returns | FV ≥ 7 descending | Mean FV descending | Frequent high scores; downside remains visible |

Standard deviation and its score penalty are removed because large positive
returns also increase it. Compare FV percentiles and threshold frequencies to
understand downside and upside; no new distribution penalty is applied. Event
bonuses are not added again to FV. The extra card discount is an additional risk preference,
not a second application of the league's scoring deductions to published FV.

Provide a configurable minimum FV sample for ordering established candidates.
For an initial full-season exploration, propose 15 observations as an editable
UI default, not a statistical confidence threshold or an agreed final rule.
Show players below that setting in a visible limited-evidence group, and players
without history in a visible no-history group. Both remain searchable and
shortlistable. Do not apply a 15-match filter to the opening current season;
show all players with their small samples explicitly labelled.

Any optional **percentile rank among players** is separate from the implemented
within-player FV percentiles. Such ranks would use only the selected position,
season, and stated evidence pool, with tied values receiving the same standing.
Show raw values first. Do not assign a zero percentile rank to missing history.

Allow manual shortlist selection with an explanation such as strong returns,
low downside, or useful cover. Multi-role usefulness means coverage of actual
unfilled positions, not simply the number of role labels. One player cannot
satisfy two simultaneous starting requirements.

## Assessing positional scarcity

For each position show total eligible players, players with historical evidence,
players meeting the selected sample setting, and players meeting the user's
performance filters. These groups describe different kinds of supply.

Inspect the drop in performance down the eligible ranking, rather than equating
a small raw role count with a shortage of good options. In particular, distinguish
E-only players from all E-eligible players. Role pools overlap, so their counts
cannot be summed into independent available players or complete squads.

Source quotations and FVM M can become optional reference columns once imported
and their meaning is verified. The existing player importer does not store them.
Neither reference values nor a shortlist establish actual auction affordability.

## Acceptance criteria for implementation

- Ten position groups, with two Dc places and one place in each other group,
  resolve to exactly eleven distinct assignments under the supplied mapping.
- A multi-role join never inflates counts, means, or event totals.
- Same player/season raw metrics are identical across eligible position tables;
  only the explicitly documented role/position card preference changes the score.
- `< 6` and `≥ 6` counts sum to the valid FV sample; `≥ 8` ≤ `≥ 7` ≤ `≥ 6`.
- Zero FV observations produce NULL percentiles; one FV gives that value at
  every percentile but no candidate score. No-history rows remain visible.
- P10 ≤ P25 ≤ P50 ≤ P75 ≤ P90; percentiles are identical across a player's
  role/position views. Equal means, samples, and cards yield equal scores
  regardless of dispersion.
- Missing event fields reduce the relevant event sample instead of becoming zero.
- No-attempt penalty conversion is NULL; all displayed rates expose denominators.
- Current eligibility and historical team membership remain distinct.
- A limited-evidence player is never silently hidden or labelled a poor performer.
- Position filters and weighted candidate ordering are descriptive; forecasts and bids
  remain absent until their separate design is implemented and validated.
