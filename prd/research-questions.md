# Research ideas: player comparisons within Mantra formation constraints

Status: exploratory draft for further analysis. These questions and hypotheses
are not findings, and the proposed comparisons have not yet been implemented.

## Purpose and scope

Use historical data to compare players and combinations of players that can
legally occupy the slots in available Mantra formations. The preferred 4-2-3-1
provides a starting point for choosing meaningful comparisons.

A formation is a set of eligibility constraints, not an independent source of
performance. Any observed advantage belongs to the selected players under those
constraints. The aim is to identify viable alternatives and understand their
tradeoffs, rather than assign each formation an intrinsic performance score.

**Working overarching question:** How can historical player performance inform
the choice between viable role combinations in the 4-2-3-1 and E-compatible
Mantra formations?

The initial population is the available 2026–27 player roster, using current
Mantra eligibility and historical performance from 2023–24, 2024–25, and 2025–26.
These are comparisons of today's eligible player pool, not reconstructions of
historical Mantra eligibility. Missing historical seasons remain missing.

## 1. What do E-eligible players offer relative to the player combinations they could replace?

**Research question:** When comparing viable role combinations, under what
conditions do E-eligible players offer stronger historical performance than
the alternatives supported by the 4-2-3-1?

**Hypothesis to test:** Some E-eligible players offer enough attacking output
and consistent FV to make an E-compatible combination attractive, after
accounting for every other slot that must change.

Start with the existing comparison of E players with Ds/Dd eligibility against
E players without those roles. Examine mean and median FV, frequency of FV ≥ 6,
P90, goals, assists, cards, and rated-match coverage. Then compare actual
candidates across the formation-compatible blocks below.

The within-E comparison describes the available profiles; it cannot by itself
establish whether changing formation is beneficial. An E player who also has Ds,
Dd, W, or another eligible role may already fit the 4-2-3-1 through that role.
The absence of an E slot does not exclude every E-eligible player.

**Existing starting points:** `src/project/analysis/e_comparison.py`,
`svg/role-e-best-violin-2025.svg`, and the outfield comparison queries. The violin
plot of selected players is a case study; group-wide conclusions require the
full eligible comparison pools and their sample sizes.

## 2. Which viable role combinations have the strongest supply of alternatives?

**Research question:** How does the depth of the available player pool affect
the practicality and adaptability of competing role combinations?

**Hypothesis to test:** A combination with slightly lower first-choice
performance may be more robust because it has more adequate replacements and
allows the same roster to cover more formations.

For each relevant slot, count candidates meeting explicit performance and
rated-coverage thresholds. Compare the decline from leading candidates to
alternatives, then evaluate whether those candidates can cover the required
slots simultaneously. A player eligible for several slots contributes options,
but cannot fill several slots in the same lineup.

Use Dc and Pc analyses as recruitment case studies. Extra Dc demand matters in
three-back alternatives; two A/Pc slots create different choices from a single
forward slot. Retain A eligibility when studying A/Pc slots: Pc-only comparisons
do not represent the whole candidate pool.

Possible measures are candidate counts, the historical performance loss after
excluding a selected player and reassigning the remaining candidates, and the
number of formations a fixed squad can field. Specify the squad and assignment
rules before calculating roster adaptability.

**Existing starting points:** `svg/role-pc-scatter-2025.svg`,
`svg/role-pc-goals-assists-2025.svg`,
`src/project/analysis/outfield_comparison.py`, and
`src/project/analysis/dc_boxplot.py`.

## 3. How stable are these player-comparison conclusions across seasons and selection criteria?

**Research question:** Do preferred players and role combinations remain
attractive across historical seasons and different definitions of performance?

**Hypothesis to test:** Some apparent advantages depend on a few exceptional
returns, a particular season, or a permissive minimum-coverage threshold.

Repeat comparisons separately for the three historical seasons. Examine how
shortlists change when prioritizing mean FV, median FV, or frequency of FV ≥ 6,
and when changing minimum rated-season coverage, for example to 30%, 50%, and
70%. Report retained players, changes in candidate-pool size, and whether the
preferred combination changes.

Distinguish changes in a player's performance from changes in which players
have sufficient history to enter the comparison. Show a common-player subset
alongside season-specific eligible samples where useful.

**Existing starting point:** the three-season Dc distribution comparison. It
provides a focused case study before extending the method to E and other roles.

## Selecting viable comparisons

The following slot lists are transcribed from the user's supplied 2026–27
formation diagram. They define candidate direct-eligibility comparisons;
official eligibility and substitution rules still need verification before
implementing a lineup engine. `P` in the diagram corresponds to `Por` in the
project. A slash means alternative eligibility for one slot, not multiple
players.

Hold shared slots and their selected players fixed, then compare equally sized
blocks of changed slots. Replacing Ds and Dd with two E players alone does not
describe the full change to a three-back formation.

| Comparison | Shared slots | 4-2-3-1 block | Alternative block |
| --- | --- | --- | --- |
| 4-2-3-1 vs 3-4-3 | Por, Dc, Dc, M/C, W/A, A/Pc | Dd, Ds, M, W/T, T | Dc/B, E, E, C, W/A |
| 4-2-3-1 vs 4-4-1-1 | Por, Dd, Dc, Dc, Ds, M, A/Pc | M/C, W/T, T, W/A | C, E/W, E/W, T/A |

These are practical decompositions of the diagrams, not the only possible
ways to match shared slots. Start with one comparison, identify distinct
candidates for every slot, and ensure that no candidate in a changed block is
already occupying a shared slot. If all players are reselected instead, label
that as a full-lineup comparison.

The 4-4-1-1 permits E players but does not require them in its E/W slots. Compare
the actual assignments, including whether zero, one, or two E-eligible players
are selected there. Eligibility labels and observed attacking contribution are
separate concepts; do not infer goals or assists from a defensive/offensive
classification.

## Analysis conventions and limits

- Use Redazione Fantacalcio consistently. Published FV already contains event
  adjustments; goals and assists help explain profiles and must not be added
  again to FV.
- Keep player score distributions and rated coverage separate. Rated matches
  divided by 38 describes historical coverage, not injury risk or future
  appearance probability. Display valid sample sizes for each metric.
- Define candidate selection before comparing outcomes. Avoid hand-picking
  exceptionally strong players for one side or treating a selected top group
  as representative of an entire role.
- Summing season mean FV can describe a selected block's mean-score profile,
  but does not establish an achievable weekly total. A matchday-level analysis
  needs explicit handling of missing ratings, replacements, and eligibility.
  Do not silently treat missing FV as zero or sum player medians/P90 values and
  label them as the lineup's median/P90.
- Selecting and evaluating players on the same season measures retrospective
  potential. An optional stronger extension selects using an earlier season
  and evaluates in the following season, with historical roster information if
  claiming to reproduce a decision that could have been made at that time.
- No auction-price evidence is currently available. Candidate depth describes
  supply in the dataset; it does not establish affordability, opponent demand,
  or the ability to acquire all selected players. Budget comparisons require
  explicit price assumptions or additional data.
- Keep D-Factor outside the initial comparison until league settings and the
  required lineup-level calculation are established.

## Suggested data story

1. Introduce the 4-2-3-1 preference and the opportunity to use E players elsewhere.
2. Show the available E profiles and their historical contributions.
3. Compare one feasible pair of player blocks, explaining all changed slots.
4. Investigate candidate depth and replacement options, including Dc and Pc/A.
5. Check whether the interpretation survives other seasons and criteria.
6. State which player combinations the evidence supports, under which
   assumptions, and where the conclusion remains uncertain.

The intended result is an evidence-based comparison of selectable players and
role combinations. It may support retaining the 4-2-3-1, considering an
E-compatible alternative, or keeping both available depending on recruitment.
