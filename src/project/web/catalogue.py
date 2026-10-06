"""Fixed-window evidence and dated context; no eligibility changes."""
from sqlalchemy import text

OPENING_SQL = """
WITH coverage_day AS (
 SELECT c.source_id, f.matchday, count(*) AS n FROM fixture f
 JOIN collection_record c ON c.id=f.collection_id JOIN data_source d ON d.id=c.source_id
 WHERE f.season=2026 AND f.matchday BETWEEN 1 AND 5 AND f.status='completed'
 AND c.status='parsed' AND d.name='Fantacalcio.it'
 AND f.home_goals IS NOT NULL AND f.away_goals IS NOT NULL
 AND (f.played_at IS NULL OR f.played_at <= CURRENT_TIMESTAMP)
 GROUP BY c.source_id,f.matchday
), coverage AS (
 SELECT source_id, sum(n) AS imported_fixtures, count(*) FILTER (WHERE n=10) AS complete_matchdays
 FROM coverage_day GROUP BY source_id
), agg AS (
 SELECT player_id,source_id,count(*) AS rated_matches,count(fanta_voto) AS fv_matches,
 avg(fanta_voto) AS mean_fv,sum(goals) AS goals,sum(assists) AS assists
 FROM validated_player_rating WHERE performance_season=2026 AND matchday BETWEEN 1 AND 5
 GROUP BY player_id,source_id
)
SELECT p.player_id, a.rated_matches,a.fv_matches,a.mean_fv,a.goals,a.assists,
 coalesce(c.imported_fixtures,0) AS imported_fixtures,
 coalesce(c.complete_matchdays,0) AS complete_matchdays
FROM current_eligible_player p LEFT JOIN agg a USING (player_id,source_id)
LEFT JOIN coverage c USING (source_id)
"""


def evidence(history, opening):
    weights = {2025: .60, 2024: .30, 2023: .10}
    usable = [h for h in history if h['season_weighted_score'] is not None]
    h_score = sum(weights.get(h['performance_season'], 0) * float(h['season_weighted_score'] or 0) for h in history)
    n = opening.get('fv_matches') or 0
    current = max(float(opening['mean_fv']), 0) * n / 5 if 2 <= n <= 5 and opening['mean_fv'] is not None else None
    ranked = bool(usable) or current is not None
    provisional = opening['complete_matchdays'] != 5 or any(h['coverage_status'] != 'complete' for h in history)
    return dict(historical_contribution=h_score, opening_contribution=current,
                score=.8*h_score+.2*(current or 0) if ranked else None, provisional=provisional)


def resolved_context(entries, club, player_id):
    """Latest verified observation wins per field, then latest supplied expectation.

    Club conflicts are never displayed on a player's current club. An explicit
    null in a newer verified record clears an outdated field.
    """
    relevant = [e for e in entries if e['club'].casefold() == (club or '').casefold()
                and (e['mapping_status'] == 'club' or e['mapping_status'] == 'matched' and e['player_id'] == player_id)]
    def order(e):
        return (e['verified'], e['observed_at'] or e['retrieved_at'], e['retrieved_at'], e['id'])
    fields = {}
    for entry in sorted(relevant, key=order):
        for key, value in entry['fields'].items():
            fields[key] = dict(value=value, verified=entry['verified'], source_url=entry['source_url'],
                               observed_at=entry['observed_at'], retrieved_at=entry['retrieved_at'])
    return fields


def catalogue(conn):
    players = [dict(r) for r in conn.execute(text('SELECT * FROM current_eligible_player ORDER BY player_name')).mappings()]
    history = {}
    for row in conn.execute(text('''SELECT player_id, performance_season, mean_fv, rated_matches,
        fv_matches, source_goals AS goals, assists, season_weighted_score, coverage_status,
        imported_fixtures, complete_matchdays FROM player_season_metrics
        WHERE performance_season BETWEEN 2023 AND 2025 ORDER BY performance_season DESC''')).mappings():
        history.setdefault(row['player_id'], []).append(dict(row))
    opening = {r['player_id']:dict(r) for r in conn.execute(text(OPENING_SQL)).mappings()}
    entries = [dict(r) for r in conn.execute(text('''SELECT * FROM context_entry
        WHERE retrieved_at <= CURRENT_TIMESTAMP
        AND (observed_at IS NULL OR observed_at <= CURRENT_TIMESTAMP)''')).mappings()]
    for p in players:
        p['history'] = history.get(p['player_id'], [])
        p['opening'] = opening[p['player_id']]
        p.update(evidence(p['history'], p['opening']))
        p['context'] = resolved_context(entries, p['current_team'], p['player_id'])
    return players
