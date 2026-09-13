# Fantacalcio Mantra player analysis — PRD

## Project goal

Build a reproducible data analysis project that helps its owner identify and compare auction targets for the 2026–27 Serie A season in Fantacalcio.it's Mantra game. Use historical and available current-season matchday performances to assess player quality, consistency, availability, and role coverage within a 500-credit squad budget.

The project also supports a master's degree data visualization exam. Its eventual academic deliverable is an English PDF presenting the results, approximately 5–6 pages long. Report structure and visualization design are deferred while data collection and auction analysis take priority.

## Timing and priorities

At the time requirements were discussed, the auction was four days away and the exam deadline was approximately two weeks away. Exact calendar deadlines have not been confirmed.

1. Obtain and validate matchday data.
2. Analyse and compare players within each current Mantra role for the auction.
3. Assess how shortlisted players cover the preferred formation and alternatives.
4. Prepare the academic report after the data and analysis are established.

## Confirmed context

- Platform and variant: Fantacalcio.it, Mantra.
- Target season: Serie A 2026–27.
- League size: eight fantasy managers.
- Budget: 500 credits per manager.
- Squad: at least 25 players, including at least three goalkeepers.
- Auction: once per season; the highest bidder obtains the player and the price is deducted from their remaining budget.
- Weekly play: field 11 players in an allowed formation, respecting positional eligibility.
- Ratings provider: **Redazione Fantacalcio**, consistently across seasons.
- Analysis period: 2023–24, 2024–25, 2025–26, and available early 2026–27 fixtures.
- Historical coverage varies: some current players will have no records in one or more previous Serie A seasons.

## Preferred formation

The user's preferred formation is 4-2-3-1, with the following slot eligibility as supplied by the user:

| Slot | Eligible role(s) |
| --- | --- |
| Goalkeeper | Por |
| Centre-back 1 | Dc |
| Centre-back 2 | Dc |
| Left-back | Ds |
| Right-back | Dd |
| Defensive midfield | M |
| Second central midfield | M or C |
| Attacking midfield | T |
| Attacking slot 2 | W or T |
| Attacking slot 3 | A or W |
| Forward | Pc or A |

Analyse all Mantra roles, rather than restricting the shortlist to this formation. Alternative formations should be assessed against official slot rules before implementation. A player with multiple eligible roles can fill only one slot in a lineup.

## Scoring

**Match rating** is the underlying performance rating. **Fanta Voto** includes the applicable positive and negative event adjustments; do not add these adjustments to the published Fanta Voto a second time.

| Event | User-specified adjustment |
| --- | ---: |
| Goal scored | +3 |
| Assist | +1 |
| Yellow card | -0.5 |
| Red card | -1 |
| Own goal | -2 |
| Goal conceded by goalkeeper | -1 |
| Penalty saved by goalkeeper | +3 |

These are the rules supplied so far, not a complete finalized scoring configuration. Preserve published ratings, published Fanta Voti, and raw event counts separately to allow later recalculation under the confirmed league rules.

### Defensive factor

The league may enable **D-Factor**, the Mantra defensive factor. The official guide describes five defensive players and optional goalkeeper inclusion. The user expects bonuses around average-rating thresholds of 6 and 6.25, but exact thresholds, bonus amounts, goalkeeper inclusion, and activation remain unconfirmed.

Treat D-Factor as an optional scenario until settings are finalized. It is a lineup-level calculation, not a fixed bonus to every defensive player's Fanta Voto. Do not substitute the Classic defensive modifier's calculation.

Source: [Fantacalcio modifier settings, including Mantra D-Factor](https://leghe.fantacalcio.it/guide-leghe-fantacalcio/gestione-lega/impostazioni-delle-opzioni-calcolo-avanzato---modificatori-90).

## Scope boundaries

The immediate scope is data collection and auction-oriented player analysis. A production website, automated bidding, and weekly lineup recommendations are not currently required. The PDF remains an eventual deliverable, but its layout and chart choices are not yet decided.

## Open questions

- Exact auction and exam dates.
- Final D-Factor settings and any additional scoring rules, including missed penalties.
- Availability of historical auction prices from this league.
- Additional squad constraints, maximum squad size, and minimum bid.
- Complete official formation eligibility and substitution rules if formation analysis is implemented.
- Availability of minutes played and reliable appearance status in the selected source.

See [data requirements](data-requirements.md) and [analysis requirements](analysis-requirements.md) for the proposed implementation requirements. The next analysis design is detailed in [position metrics and candidate comparison](position-metrics.md). Future prediction and pricing ideas are recorded separately in [score forecasting and auction valuation](score-forecasting.md). These documents record requirements and findings; they do not imply that collection or analysis has already been implemented.
