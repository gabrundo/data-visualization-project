# Score forecasting and auction valuation — proposed design

## Purpose and status

Estimate future player contribution and, subsequently, a suggested auction bid
for an eight-manager league with 500 credits and at least 25 players, including
three goalkeepers. This records the proposed approach; no forecasting model,
weights, or credit conversion have been selected or implemented.

Descriptive metrics are specified separately in
[position metrics](position-metrics.md). Historical averages and event
frequencies describe observations; they must not be labelled forecasts.

## Forecast target

Start with expected published Fanta Voto **conditional on receiving a valid
Fanta Voto**, using Redazione Fantacalcio. State the forecast horizon, cutoff,
sample sizes, and model version. This is not automatically an expected weekly
lineup contribution: that also depends on receiving a usable score and being
selected in the fantasy lineup.

Keep underlying Voto, published Fanta Voto, and raw events separate. Published
Fanta Voto already includes event adjustments; adding goal, assist, or penalty
bonuses again would double-count them. Forecasting a league-specific score
requires the complete confirmed scoring configuration and verified event
semantics. D-Factor remains a separate lineup-level scenario.

## Combining history with an early current season

A transparent candidate model is:

```text
forecast = w * current_season_mean + (1 - w) * historical_expectation
w = n / (n + k)
```

- `n`: valid current-season Fanta Voto observations available at the cutoff.
- `k > 0`: historical prior strength, expressed as an effective number of
  observations. It is a parameter to validate, not a chosen constant.
- `historical_expectation`: an estimate from prior seasons. Its season weights,
  sample requirements, and treatment of team/context changes remain to be chosen.

With no current observations, use the historical expectation directly; do not
evaluate a missing current average as zero. With no player history, use a
separately validated comparable-player prior or report insufficient evidence.
Missing seasons are never zero-performance seasons. Keep all season-specific
observations visible alongside a pooled prediction.

Do not assume that a current Mantra role describes the player's historical role.
Current eligibility defines auction comparisons; any contextual role adjustment
in a forecast needs its own evidence.

## Bonus and penalty forecasts

Historical bonus frequency is the share of evaluable observations containing
the specified event. It is distinct from event volume: a hat-trick is one
bonus-producing match and three goals. A future probability estimate should
account for sample size and be evaluated on later observations.

Penalty scoring can be decomposed as:

```text
expected penalty goals over the horizon
  = expected team penalty attempts
    * player's expected share of those attempts
    * player's conversion probability
```

These inputs are uncertain and need consistent horizons. Show penalties scored,
missed, attempted, and seasons separately. A 2/2 record does not establish
conversion superiority over 7/9, nor current first-choice penalty responsibility.
Historical attempts alone cannot establish current responsibility. Do not add
this component to a forecast of Fanta Voto that already captures it.

## From player score to squad contribution

A first approximation for comparing an upgrade is:

```text
added contribution
  ≈ expected usable starts in our fantasy lineup
    * (projected Fanta Voto - projected replacement Fanta Voto)
```

This assumes a replacement is available for the remaining opportunities. A
full squad model must account for replacement availability, legal assignments,
bench coverage, and different lineup opportunities. Expected usable starts are
not observed Serie A appearances; the current importer does not establish
minutes, starting status, or actual appearance status.

Choose replacements from plausible available alternatives for the formation
slot, considering league demand and acquisition assumptions. They are not
automatically the mean player in a role. A multi-role player can fill only one
slot at a time. Value flexibility through the extra legal coverage it provides,
rather than multiplying value by the number of listed roles.

## Auction valuation

- Apply the 500-credit constraint to a proposed squad, not to the entire catalogue.
- Reserve enough credits for every remaining roster place and goalkeeper
  requirement. Minimum bid and any additional roster restrictions are unconfirmed.
- Allocate spending according to improvement over alternatives and squad needs;
  do not convert average Fanta Voto to credits using an arbitrary multiplier.
- Reassess alternatives, coverage, and remaining budget as auction purchases occur.
- Keep suggested bid ranges, source quotations/FVM M, and actual auction prices
  in separate fields. Source reference values are not demonstrated market prices.
- Historical league auction prices have not been supplied. Until a conversion
  method is validated, leave model bid fields unavailable rather than inventing
  precise credit values.

## Validation and uncertainty

Evaluate score forecasts at historical cutoffs using only information available
at each cutoff, then compare with later observations. Tune parameters on earlier
windows and keep a later window for final evaluation. Compare against simple
baselines such as the previous-season mean and a comparable-player mean.

Report score prediction error (for example, mean absolute error), and assess
probability calibration for bonus forecasts if implemented. Analyse sparse
histories and transfers separately. A successful score forecast does not by
itself validate auction prices or an availability forecast.

Distinguish match-to-match variability from uncertainty about estimated ability.
Show sample sizes and the origin of any prediction intervals. Test how squad
recommendations change under plausible forecast and price assumptions before
presenting a bid range as robust.
