BEGIN;

-- Removing legacy columns requires rebuilding their dependent views. Do this
-- only for the SD-based schema; later installations use CREATE OR REPLACE.
-- Explicit drops (no CASCADE) protect any additional user-defined dependents.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'player_metric_settings'
          AND column_name = 'consistency_penalty'
    ) THEN
        DROP VIEW IF EXISTS
            role_por_statistics, role_dd_statistics, role_ds_statistics,
            role_dc_statistics, role_b_statistics, role_e_statistics,
            role_m_statistics, role_c_statistics, role_w_statistics,
            role_t_statistics, role_a_statistics, role_pc_statistics,
            position_por_statistics, position_dd_statistics, position_ds_statistics,
            position_dc_statistics, position_m_statistics, position_m_c_statistics,
            position_w_t_statistics, position_t_statistics, position_w_a_statistics,
            position_a_pc_statistics;
        DROP VIEW IF EXISTS player_role_statistics, player_position_statistics;
        DROP VIEW IF EXISTS player_season_metrics;
        DROP VIEW IF EXISTS current_eligible_player;
        DROP VIEW IF EXISTS player_metric_settings;
    END IF;
END $$;

-- Heuristic ranking preferences, not fitted forecasting parameters.
CREATE OR REPLACE VIEW player_metric_settings AS
SELECT 2026::integer AS eligibility_season,
       2023::integer AS first_performance_season,
       38::integer AS season_games,
       0.25::numeric AS card_risk_weight;

CREATE OR REPLACE VIEW current_eligible_player AS
WITH latest AS (
    SELECT DISTINCT ON (s.player_id, s.source_id) s.*
    FROM player_season_snapshot s
    JOIN collection_record c ON c.id = s.collection_id AND c.source_id = s.source_id
    JOIN data_source d ON d.id = s.source_id
    CROSS JOIN player_metric_settings cfg
    WHERE s.season = cfg.eligibility_season AND c.status = 'parsed'
      AND d.name = 'Fantacalcio.it' AND s.snapshot_at <= CURRENT_TIMESTAMP
    ORDER BY s.player_id, s.source_id, s.snapshot_at DESC, s.id DESC
)
SELECT s.player_id, s.source_id, p.name AS player_name,
       t.name AS current_team, s.season AS eligibility_season,
       s.snapshot_at AS eligibility_at,
       ARRAY(SELECT r.role FROM player_snapshot_role r
             WHERE r.snapshot_id = s.id ORDER BY r.role) AS roles
FROM latest s
JOIN player p ON p.id = s.player_id
LEFT JOIN team t ON t.id = s.team_id;

-- Only validated observations from the selected publisher/provider enter metrics.
CREATE OR REPLACE VIEW validated_player_rating AS
SELECT pf.*, f.season AS performance_season, f.matchday, f.played_at
FROM player_fixture_performance pf
JOIN fixture f ON f.id = pf.fixture_id
JOIN collection_record pc ON pc.id = pf.collection_id AND pc.source_id = pf.source_id
JOIN collection_record fc ON fc.id = f.collection_id AND fc.source_id = pf.source_id
JOIN data_source d ON d.id = pf.source_id
WHERE pf.provider = 'Redazione Fantacalcio' AND d.name = 'Fantacalcio.it'
  AND pc.status = 'parsed' AND fc.status = 'parsed' AND f.status = 'completed'
  AND (f.played_at IS NULL OR f.played_at <= CURRENT_TIMESTAMP)
  AND pf.team_id IN (f.home_team_id, f.away_team_id)
  AND pf.validation_issues = '[]'::jsonb
  AND pf.rating_status = 'rated' AND pf.match_rating IS NOT NULL;

CREATE OR REPLACE VIEW player_season_metrics AS
WITH seasons AS (
    SELECT generate_series(first_performance_season, eligibility_season) AS performance_season
    FROM player_metric_settings
), matchday_coverage AS (
    SELECT c.source_id, f.season AS performance_season, f.matchday,
           count(*) AS fixture_count
    FROM fixture f
    JOIN collection_record c ON c.id = f.collection_id
    JOIN data_source d ON d.id = c.source_id
    WHERE f.status = 'completed' AND c.status = 'parsed' AND d.name = 'Fantacalcio.it'
      AND f.home_goals IS NOT NULL AND f.away_goals IS NOT NULL
      AND (f.played_at IS NULL OR f.played_at <= CURRENT_TIMESTAMP)
    GROUP BY c.source_id, f.season, f.matchday
), coverage AS (
    SELECT source_id, performance_season, sum(fixture_count)::bigint AS imported_fixtures,
           count(*) FILTER (WHERE fixture_count = 10 AND matchday BETWEEN 1 AND 38) AS complete_matchdays
    FROM matchday_coverage GROUP BY source_id, performance_season
), agg AS (
    SELECT player_id, source_id, performance_season,
           count(*) AS rated_matches,
           count(fanta_voto) AS fv_matches,
           avg(match_rating) AS mean_voto,
           avg(fanta_voto) AS mean_fv,
           -- Within-player FV percentiles, not ranks within the eligible pool.
           -- Ordered-set aggregates ignore NULL FV; interpolation may yield
           -- values not present in the original observations.
           percentile_cont(0.10) WITHIN GROUP (ORDER BY fanta_voto)::numeric AS fv_p10,
           percentile_cont(0.25) WITHIN GROUP (ORDER BY fanta_voto)::numeric AS fv_p25,
           percentile_cont(0.50) WITHIN GROUP (ORDER BY fanta_voto)::numeric AS fv_p50,
           percentile_cont(0.75) WITHIN GROUP (ORDER BY fanta_voto)::numeric AS fv_p75,
           percentile_cont(0.90) WITHIN GROUP (ORDER BY fanta_voto)::numeric AS fv_p90,
           sum(fanta_voto) AS observed_fv_total,
           count(*) FILTER (WHERE fanta_voto < 6) AS fv_lt6_matches,
           count(*) FILTER (WHERE fanta_voto >= 6) AS fv_ge6_matches,
           count(*) FILTER (WHERE fanta_voto >= 7) AS fv_ge7_matches,
           count(*) FILTER (WHERE fanta_voto >= 8) AS fv_ge8_matches,
           count(goals) AS goal_sample,
           sum(goals) AS source_goals,
           avg(goals) AS source_goals_per_rated_match,
           avg((goals > 0)::integer)::numeric AS source_goal_rate,
           count(assists) AS assist_sample,
           sum(assists) AS assists,
           avg(assists) AS assists_per_rated_match,
           avg((assists > 0)::integer)::numeric AS assist_rate,
           count(*) FILTER (WHERE goals IS NOT NULL AND penalties_scored IS NOT NULL
                           AND assists IS NOT NULL) AS bonus_sample,
           count(*) FILTER (WHERE goals IS NOT NULL AND penalties_scored IS NOT NULL
                           AND assists IS NOT NULL
                           AND (goals > 0 OR penalties_scored > 0 OR assists > 0)) AS bonus_matches,
           count(*) FILTER (WHERE penalties_scored IS NOT NULL AND penalties_missed IS NOT NULL) AS penalty_sample,
           sum(penalties_scored) FILTER (WHERE penalties_missed IS NOT NULL) AS penalties_scored,
           sum(penalties_missed) FILTER (WHERE penalties_scored IS NOT NULL) AS penalties_missed,
           sum(penalties_scored + penalties_missed) AS penalty_attempts,
           count(*) FILTER (WHERE yellow_cards IS NOT NULL AND red_cards IS NOT NULL) AS card_sample,
           count(*) FILTER (WHERE yellow_cards IS NOT NULL AND red_cards IS NOT NULL
                           AND (yellow_cards > 0 OR red_cards > 0)) AS card_matches,
           count(yellow_cards) AS yellow_card_sample,
           sum(yellow_cards) AS yellow_cards,
           avg((yellow_cards > 0)::integer)::numeric AS yellow_card_rate,
           count(red_cards) AS red_card_sample,
           sum(red_cards) AS red_cards,
           avg((red_cards > 0)::integer)::numeric AS red_card_rate,
           count(own_goals) AS own_goal_sample,
           sum(own_goals) AS own_goals,
           avg((own_goals > 0)::integer)::numeric AS own_goal_rate,
           count(goals_conceded) AS goals_conceded_sample,
           sum(goals_conceded) AS goals_conceded,
           avg(goals_conceded) AS goals_conceded_per_rated_match,
           count(penalties_saved) AS penalty_save_sample,
           sum(penalties_saved) AS penalties_saved
    FROM validated_player_rating
    CROSS JOIN player_metric_settings cfg
    WHERE performance_season BETWEEN cfg.first_performance_season AND cfg.eligibility_season
    GROUP BY player_id, source_id, performance_season
), base AS (
    SELECT p.*, s.performance_season, 'Redazione Fantacalcio'::text AS provider,
           cfg.season_games, cfg.card_risk_weight,
           coalesce(c.imported_fixtures, 0) AS imported_fixtures,
           coalesce(c.complete_matchdays, 0) AS complete_matchdays,
           CASE WHEN c.imported_fixtures = 380 AND c.complete_matchdays = 38 THEN 'complete'
                WHEN c.imported_fixtures > 0 THEN 'partial' ELSE 'uncollected' END AS coverage_status,
           coalesce(a.rated_matches, 0) AS rated_matches,
           coalesce(a.fv_matches, 0) AS fv_matches,
           a.mean_voto, a.mean_fv,
           a.fv_p50 AS median_fv, a.fv_p25 AS lower_quartile_fv,
           a.fv_p10, a.fv_p25, a.fv_p50, a.fv_p75, a.fv_p90, a.observed_fv_total,
           coalesce(a.fv_lt6_matches, 0) AS fv_lt6_matches,
           coalesce(a.fv_ge6_matches, 0) AS fv_ge6_matches,
           coalesce(a.fv_ge7_matches, 0) AS fv_ge7_matches,
           coalesce(a.fv_ge8_matches, 0) AS fv_ge8_matches,
           coalesce(a.goal_sample, 0) AS goal_sample,
           a.source_goals, a.source_goals_per_rated_match, a.source_goal_rate,
           coalesce(a.assist_sample, 0) AS assist_sample,
           a.assists, a.assists_per_rated_match, a.assist_rate,
           coalesce(a.bonus_sample, 0) AS bonus_sample,
           coalesce(a.bonus_matches, 0) AS bonus_matches,
           coalesce(a.penalty_sample, 0) AS penalty_sample,
           a.penalties_scored, a.penalties_missed, a.penalty_attempts,
           coalesce(a.card_sample, 0) AS card_sample,
           coalesce(a.card_matches, 0) AS card_matches,
           coalesce(a.yellow_card_sample, 0) AS yellow_card_sample,
           a.yellow_cards, a.yellow_card_rate,
           coalesce(a.red_card_sample, 0) AS red_card_sample,
           a.red_cards, a.red_card_rate,
           coalesce(a.own_goal_sample, 0) AS own_goal_sample,
           a.own_goals, a.own_goal_rate,
           coalesce(a.goals_conceded_sample, 0) AS goals_conceded_sample,
           a.goals_conceded, a.goals_conceded_per_rated_match,
           coalesce(a.penalty_save_sample, 0) AS penalty_save_sample,
           a.penalties_saved
    FROM current_eligible_player p CROSS JOIN seasons s CROSS JOIN player_metric_settings cfg
    LEFT JOIN agg a ON a.player_id = p.player_id AND a.source_id = p.source_id
                   AND a.performance_season = s.performance_season
    LEFT JOIN coverage c ON c.source_id = p.source_id AND c.performance_season = s.performance_season
)
SELECT base.*,
       CASE WHEN fv_matches = 0 THEN 'no_fv_history'
            WHEN fv_matches = 1 THEN 'single_observation'
            WHEN fv_matches > season_games THEN 'over_season_limit'
            WHEN fv_matches < 15 THEN 'limited_sample' ELSE 'larger_sample' END AS evidence_status,
       rated_matches::numeric / season_games AS rated_season_fraction,
       fv_matches::numeric / season_games AS fv_season_fraction,
       fv_lt6_matches::numeric / nullif(fv_matches, 0) AS fv_lt6_rate,
       fv_ge6_matches::numeric / nullif(fv_matches, 0) AS fv_ge6_rate,
       fv_ge7_matches::numeric / nullif(fv_matches, 0) AS fv_ge7_rate,
       fv_ge8_matches::numeric / nullif(fv_matches, 0) AS fv_ge8_rate,
       CASE WHEN fv_matches > 0 THEN fv_ge6_matches::numeric / season_games END AS fv_ge6_season_fraction,
       CASE WHEN fv_matches > 0 THEN fv_ge7_matches::numeric / season_games END AS fv_ge7_season_fraction,
       CASE WHEN fv_matches > 0 THEN fv_ge8_matches::numeric / season_games END AS fv_ge8_season_fraction,
       bonus_matches::numeric / nullif(bonus_sample, 0) AS bonus_rate,
       penalties_scored::numeric / nullif(penalty_attempts, 0) AS penalty_conversion_rate,
       card_matches::numeric / nullif(card_sample, 0) AS card_rate,
       CASE WHEN fv_matches BETWEEN 1 AND season_games
            THEN observed_fv_total / season_games END AS observed_fv_per_season_game,
       CASE WHEN fv_matches BETWEEN 2 AND season_games
            THEN fv_matches::numeric / season_games
                 * greatest(mean_fv, 0)
       END AS season_weighted_score
FROM base;

-- Direct role membership only. A role-specific preference is not a match score.
CREATE OR REPLACE VIEW player_role_statistics AS
SELECT m.*, r.role,
       r.role IN ('Dd', 'Ds', 'Dc', 'B', 'E', 'M', 'C') AS card_weight_applies,
       CASE WHEN r.role IN ('Dd', 'Ds', 'Dc', 'B', 'E', 'M', 'C')
            THEN m.season_weighted_score * (1 - m.card_risk_weight * m.card_rate)
            ELSE m.season_weighted_score END AS candidate_score
FROM player_season_metrics m
CROSS JOIN LATERAL unnest(m.roles) AS r(role);

CREATE OR REPLACE VIEW player_position_statistics AS
SELECT m.*, positions.position,
       positions.starting_slots, positions.card_weight_applies,
       CASE WHEN positions.card_weight_applies
            THEN m.season_weighted_score * (1 - m.card_risk_weight * m.card_rate)
            ELSE m.season_weighted_score END AS candidate_score
FROM player_season_metrics m
JOIN (VALUES
    ('por', ARRAY['Por'], 1, false),
    ('dd', ARRAY['Dd'], 1, true),
    ('dc', ARRAY['Dc'], 2, true),
    ('ds', ARRAY['Ds'], 1, true),
    ('m', ARRAY['M'], 1, true),
    ('m_c', ARRAY['M', 'C'], 1, true),
    ('w_t', ARRAY['W', 'T'], 1, false),
    ('t', ARRAY['T'], 1, false),
    ('w_a', ARRAY['W', 'A'], 1, false),
    ('a_pc', ARRAY['A', 'Pc'], 1, false)
) AS positions(position, eligible_roles, starting_slots, card_weight_applies)
ON m.roles && positions.eligible_roles;

CREATE OR REPLACE VIEW role_por_statistics AS SELECT * FROM player_role_statistics WHERE role = 'Por';
CREATE OR REPLACE VIEW role_dd_statistics AS SELECT * FROM player_role_statistics WHERE role = 'Dd';
CREATE OR REPLACE VIEW role_ds_statistics AS SELECT * FROM player_role_statistics WHERE role = 'Ds';
CREATE OR REPLACE VIEW role_dc_statistics AS SELECT * FROM player_role_statistics WHERE role = 'Dc';
CREATE OR REPLACE VIEW role_b_statistics AS SELECT * FROM player_role_statistics WHERE role = 'B';
CREATE OR REPLACE VIEW role_e_statistics AS SELECT * FROM player_role_statistics WHERE role = 'E';
CREATE OR REPLACE VIEW role_m_statistics AS SELECT * FROM player_role_statistics WHERE role = 'M';
CREATE OR REPLACE VIEW role_c_statistics AS SELECT * FROM player_role_statistics WHERE role = 'C';
CREATE OR REPLACE VIEW role_w_statistics AS SELECT * FROM player_role_statistics WHERE role = 'W';
CREATE OR REPLACE VIEW role_t_statistics AS SELECT * FROM player_role_statistics WHERE role = 'T';
CREATE OR REPLACE VIEW role_a_statistics AS SELECT * FROM player_role_statistics WHERE role = 'A';
CREATE OR REPLACE VIEW role_pc_statistics AS SELECT * FROM player_role_statistics WHERE role = 'Pc';

CREATE OR REPLACE VIEW position_por_statistics AS SELECT * FROM player_position_statistics WHERE position = 'por';
CREATE OR REPLACE VIEW position_dd_statistics AS SELECT * FROM player_position_statistics WHERE position = 'dd';
CREATE OR REPLACE VIEW position_ds_statistics AS SELECT * FROM player_position_statistics WHERE position = 'ds';
CREATE OR REPLACE VIEW position_dc_statistics AS SELECT * FROM player_position_statistics WHERE position = 'dc';
CREATE OR REPLACE VIEW position_m_statistics AS SELECT * FROM player_position_statistics WHERE position = 'm';
CREATE OR REPLACE VIEW position_m_c_statistics AS SELECT * FROM player_position_statistics WHERE position = 'm_c';
CREATE OR REPLACE VIEW position_w_t_statistics AS SELECT * FROM player_position_statistics WHERE position = 'w_t';
CREATE OR REPLACE VIEW position_t_statistics AS SELECT * FROM player_position_statistics WHERE position = 't';
CREATE OR REPLACE VIEW position_w_a_statistics AS SELECT * FROM player_position_statistics WHERE position = 'w_a';
CREATE OR REPLACE VIEW position_a_pc_statistics AS SELECT * FROM player_position_statistics WHERE position = 'a_pc';

COMMIT;
