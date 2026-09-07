# Analysis requirements

## Decision to support

Help the user choose auction targets for each Mantra role in an eight-manager league, with 500 credits and a squad of at least 25 players including three goalkeepers. Assess the preferred 4-2-3-1 and, subsequently, other legal formations against the available player pool.

## Player metrics

| Metric | Intended interpretation |
| --- | --- |
| Mean and median Fanta Voto | Average and typical fantasy performance |
| Standard deviation of Fanta Voto | Match-to-match variability |
| Rated appearances | Number of fixtures with a valid rating |
| Actual appearances, if observable | Participation, including appearances without a rating |
| Appearance/rated-appearance rate | Frequency of contribution, with an explicitly defined eligible-fixture denominator |
| Mean underlying match rating | Performance before event adjustments |
| Frequency above/below stated thresholds | Strong-return and poor-return frequency |
| Event totals and per-appearance rates | Sources of bonuses and penalties |
| Season-by-season trends | Change and persistence across seasons |

Standard deviation must be reported with mean performance and sample size. Low variation alone does not indicate a good target. Use rated observations for rating statistics and document the standard-deviation convention; fewer than two observations cannot support a sample standard deviation.

Missing seasons are missing history, not zero performance. Keep newcomers visible and clearly distinguish limited evidence from poor performance. Do not infer injury history or reasons for absence from missing ratings alone.

Include early 2026–27 performances, but show their sample size and season separately. Any pooled or recency-weighted metric must document its weighting and treatment of partial seasons; weights have not yet been chosen.

## Role and formation analysis

- Compare players within their eligible 2026–27 Mantra roles.
- Retain multiple roles and expose their usefulness for squad coverage.
- Explore the supply of strong options by role and the coverage needed for the user's preferred formation.
- Avoid counting the same player twice when evaluating a lineup.
- Separate descriptive historical performance from forecasts of the incoming season.

## Team analysis

Use fixture results to calculate goals scored/conceded, clean sheets, and home/away splits. Player ratings can also support team-level rating summaries with explicit inclusion rules. Do not sum player Fanta Voti and label the result as a Serie A team result or fantasy lineup score.

Team context may help interpret individual returns, especially goalkeeper and defensive performance. More detailed metrics depend on the fields actually available in the source.

## Valuation and budget

Keep published quotations and `FVM M` separate from actual auction prices. Historical league prices have not been supplied. These source values may be used as clearly labelled reference valuations after their scale and meaning are verified; they do not establish that a player will be obtainable at that price.

Any proposed squad or bid allocation must account for the 500-credit total and minimum roster/goalkeeper requirements. Price assumptions must be explicit. No specific price model or automatic bid recommendation has been agreed.

## Expected initial outputs

- A documented dataset and collection-coverage summary.
- A player metrics table with role eligibility, sample sizes, and season-specific results.
- Role-based shortlists showing performance, consistency, and evidence limitations.
- Formation coverage analysis once the required eligibility rules are validated.

These are proposed functional outputs; final chart selection and the English exam PDF's design remain deferred at the user's request.

## Acceptance criteria

- Every reported metric has a stated definition, observation window, and missing-data treatment.
- Ratings use Redazione Fantacalcio consistently and do not double-count published bonuses.
- Rankings and shortlists expose small samples and missing historical coverage.
- Historical team/role changes do not corrupt current eligibility or past performance records.
- D-Factor effects are only quantified with explicit settings and sufficient fixture-level lineup data.
- Conclusions support practical role comparisons without presenting historical statistics or reference valuations as guaranteed future returns or auction prices.
