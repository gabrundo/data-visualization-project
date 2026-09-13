"""Statistics view contracts in an isolated PostgreSQL schema.

Run with HISTORICAL_DB_TESTS=1, alongside the existing database tests.
"""

from datetime import datetime, timezone
import os
import unittest
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from project.etl.import_players import ROOT, database_engine


@unittest.skipUnless(os.environ.get("HISTORICAL_DB_TESTS") == "1", "Set HISTORICAL_DB_TESTS=1 for PostgreSQL integration")
class PlayerMetricsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin = database_engine(ROOT / ".env")
        cls.schema = "test_metrics_" + uuid4().hex
        with cls.admin.begin() as conn:
            conn.execute(text(f"CREATE SCHEMA {cls.schema}"))
        cls.engine = create_engine(cls.admin.url, connect_args={"options": f"-csearch_path={cls.schema}"}, hide_parameters=True)
        cls.addClassCleanup(cls.cleanup_schema)
        with cls.engine.connect() as conn:
            conn.exec_driver_sql((ROOT / "db/init/001_schema.sql").read_text())
            conn.exec_driver_sql((ROOT / "db/init/002_player_metrics.sql").read_text())
            conn.commit()
        cls.seed()

    @classmethod
    def cleanup_schema(cls):
        cls.engine.dispose()
        with cls.admin.begin() as conn:
            conn.execute(text(f"DROP SCHEMA {cls.schema} CASCADE"))
        cls.admin.dispose()

    @classmethod
    def seed(cls):
        with cls.engine.begin() as conn:
            conn.execute(text("INSERT INTO data_source (id, name) OVERRIDING SYSTEM VALUE VALUES (1, 'Fantacalcio.it'), (2, 'Other')"))
            conn.execute(text("INSERT INTO season VALUES (2025), (2026)"))
            conn.execute(text("""INSERT INTO collection_record (id, source_id, status, source_uri)
                OVERRIDING SYSTEM VALUE VALUES (1, 1, 'parsed', 'https://example.test/valid'),
                    (2, 1, 'failed', 'https://example.test/failed'),
                    (3, 2, 'parsed', 'https://example.test/other')"""))
            for i in range(1, 21):
                conn.execute(text("INSERT INTO team (id, name) OVERRIDING SYSTEM VALUE VALUES (:id, :name)"), {"id": i, "name": f"Team {i}"})
            names = ["Regular", "One-off", "Volatile", "Card-prone", "No history", "Missing events", "Ineligible", "Unrated only", "Other source only"]
            for i, name in enumerate(names, 1):
                conn.execute(text("INSERT INTO player (id, name) OVERRIDING SYSTEM VALUE VALUES (:id, :name)"), {"id": i, "name": name})
                if i != 7:
                    conn.execute(text("""INSERT INTO player_season_snapshot
                        (id, player_id, source_id, season, snapshot_at, team_id, collection_id)
                        OVERRIDING SYSTEM VALUE VALUES (:id, :id, 1, 2026, :at, 20, 1)"""),
                        {"id": i, "at": datetime(2026, 1, 1, tzinfo=timezone.utc)})
                    conn.execute(text("INSERT INTO player_snapshot_role VALUES (:id, 'M'), (:id, 'C')"), {"id": i})
            # Latest validated snapshot wins, not failed/future snapshots or old roles.
            conn.execute(text("""INSERT INTO player_season_snapshot
                (id, player_id, source_id, season, snapshot_at, team_id, collection_id)
                OVERRIDING SYSTEM VALUE VALUES (100, 1, 1, 2026, '2025-12-01T00:00:00Z', 1, 1),
                       (101, 1, 1, 2026, '2026-02-01T00:00:00Z', 1, 2),
                       (102, 1, 1, 2026, '2099-01-01T00:00:00Z', 1, 1)"""))
            conn.execute(text("INSERT INTO player_snapshot_role VALUES (100, 'Dd'), (101, 'Pc'), (102, 'Por')"))

            # Complete double round robin: 20 teams, 38 rounds, 380 fixtures.
            rotation = list(range(1, 21))
            first_half = []
            for _ in range(19):
                first_half.append([(rotation[i], rotation[-i-1]) for i in range(10)])
                rotation = [rotation[0], rotation[-1], *rotation[1:-1]]
            rounds = first_half + [[(away, home) for home, away in pairs] for pairs in first_half]
            cls.player_fixtures = []
            fixture_id = 0
            for day, pairs in enumerate(rounds, 1):
                for home, away in pairs:
                    fixture_id += 1
                    conn.execute(text("""INSERT INTO fixture
                        (id, season, matchday, home_team_id, away_team_id, home_goals, away_goals, status, collection_id)
                        OVERRIDING SYSTEM VALUE VALUES (:id, 2025, :day, :home, :away, 1, 0, 'completed', 1)"""),
                        {"id": fixture_id, "day": day, "home": home, "away": away})
                    if 1 in (home, away):
                        cls.player_fixtures.append(fixture_id)
            sql = text("""INSERT INTO player_fixture_performance
                (player_id, fixture_id, source_id, provider, team_id, collection_id,
                 match_rating, fanta_voto, rating_status, goals, assists, penalties_scored,
                 penalties_missed, yellow_cards, red_cards, own_goals, goals_conceded, penalties_saved)
                VALUES (:player, :fixture, 1, 'Redazione Fantacalcio', 1, 1,
                        6, :fv, 'rated', :goals, :assists, :ps, :pm, :yellow, :red, 0, 0, 0)""")
            for index, fixture in enumerate(cls.player_fixtures):
                for player in [1, 2, 3, 4, 6, 7]:
                    if player == 2 and index > 0 or player == 6 and index > 1:
                        continue
                    params = dict(player=player, fixture=fixture,
                                  fv=10 if player == 2 else (4 if index % 2 == 0 else 10) if player == 3 else 7,
                                  goals=0, assists=0, ps=0, pm=0,
                                  yellow=int(player == 4 and index < 19), red=int(player == 4 and index == 0))
                    if player == 6:
                        params.update(goals=None, assists=None, ps=None, pm=None, yellow=None, red=None)
                    if player == 1 and index == 0:
                        params.update(goals=1, assists=1, ps=1)
                    if player == 1 and index == 1:
                        params.update(pm=1)
                    conn.execute(sql, params)
            # These rows must never enter the sample or bonus/card denominators.
            conn.execute(text("""INSERT INTO player_fixture_performance
                (player_id, fixture_id, source_id, provider, team_id, collection_id, match_rating, fanta_voto, rating_status)
                VALUES (1, :f, 1, 'Other provider', 1, 1, 10, 20, 'rated'),
                       (1, :f, 2, 'Redazione Fantacalcio', 1, 3, 10, 20, 'rated'),
                       (8, :f, 1, 'Redazione Fantacalcio', 1, 1, NULL, NULL, 'unrated'),
                       (9, :f, 2, 'Redazione Fantacalcio', 1, 3, 10, 20, 'rated')"""),
                {"f": cls.player_fixtures[0]})

    def row(self, player, season=2025, view="role_m_statistics"):
        with self.engine.connect() as conn:
            return conn.execute(text(f"SELECT * FROM {view} WHERE player_id = :id AND performance_season = :season"),
                                {"id": player, "season": season}).mappings().one()

    def test_season_weight_prevents_one_off_leading(self):
        regular, one_off = self.row(1), self.row(2)
        self.assertEqual(regular["fv_matches"], 38)
        self.assertEqual(regular["fv_season_fraction"], 1)
        self.assertEqual(regular["candidate_score"], 7)
        self.assertEqual(one_off["mean_fv"], 10)
        self.assertAlmostEqual(float(one_off["observed_fv_per_season_game"]), 10 / 38)
        for percentile in (10, 25, 50, 75, 90):
            self.assertEqual(one_off[f"fv_p{percentile}"], 10)
        self.assertIsNone(one_off["season_weighted_score"])
        self.assertIsNone(one_off["candidate_score"])
        self.assertEqual(one_off["evidence_status"], "single_observation")

    def test_variation_is_not_penalized_and_card_preferences_remain(self):
        regular, volatile, cards = self.row(1), self.row(3), self.row(4)
        self.assertEqual(regular["mean_fv"], volatile["mean_fv"])
        self.assertEqual(regular["candidate_score"], volatile["candidate_score"])
        self.assertEqual(volatile["fv_p25"], 4)
        self.assertEqual(volatile["fv_p50"], 7)
        self.assertEqual(volatile["fv_p75"], 10)
        self.assertNotIn("sd_fv", regular)
        self.assertNotIn("consistency_adjusted_score", regular)
        self.assertNotIn("consistency_penalty", regular)
        self.assertEqual(cards["card_matches"], 19)  # Yellow + red is one match.
        self.assertEqual(float(cards["card_rate"]), 0.5)
        self.assertEqual(float(cards["candidate_score"]), 7 * (1 - 0.25 * 0.5))
        self.assertEqual(cards["mean_fv"], 7)  # Published FV is never recomputed.

    def test_roles_deduplication_and_current_identity(self):
        row = self.row(1, view="position_m_c_statistics")
        self.assertEqual(row["roles"], ["C", "M"])
        self.assertEqual(row["fv_matches"], 38)
        self.assertEqual(row["current_team"], "Team 20")
        self.assertEqual(row["candidate_score"], self.row(1)["candidate_score"])
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(text("SELECT count(*) FROM role_dd_statistics WHERE player_id = 1")).scalar_one(), 0)
            self.assertEqual(conn.execute(text("SELECT count(*) FROM player_season_metrics WHERE player_id = 7")).scalar_one(), 0)
            self.assertEqual(conn.execute(text("SELECT count(*) FROM current_eligible_player")).scalar_one(), 8)

    def test_missing_history_events_and_zero_attempts(self):
        missing = self.row(5)
        self.assertEqual(missing["fv_matches"], 0)
        for field in ["mean_fv", "fv_p10", "fv_p25", "fv_p50", "fv_p75", "fv_p90",
                      "season_weighted_score", "candidate_score", "card_rate",
                      "penalty_conversion_rate", "source_goals"]:
            self.assertIsNone(missing[field], field)
        events = self.row(6)
        self.assertEqual(events["fv_matches"], 2)
        self.assertEqual(events["bonus_sample"], 0)
        self.assertIsNone(events["bonus_rate"])
        self.assertIsNone(events["card_rate"])
        self.assertIsNone(events["candidate_score"])
        self.assertEqual(self.row(3)["penalty_attempts"], 0)
        self.assertIsNone(self.row(3)["penalty_conversion_rate"])
        self.assertEqual(self.row(8)["rated_matches"], 0)
        self.assertEqual(self.row(9)["rated_matches"], 0)

    def test_thresholds_events_and_coverage(self):
        row = self.row(1)
        self.assertEqual(row["coverage_status"], "complete")
        self.assertEqual(row["imported_fixtures"], 380)
        self.assertEqual(row["complete_matchdays"], 38)
        self.assertEqual(row["fv_lt6_matches"] + row["fv_ge6_matches"], 38)
        self.assertEqual(row["fv_ge7_rate"], 1)
        self.assertEqual(row["fv_ge8_rate"], 0)
        self.assertEqual(row["bonus_matches"], 1)
        self.assertEqual(row["bonus_sample"], 38)
        self.assertEqual(row["penalty_attempts"], 2)
        self.assertEqual(float(row["penalty_conversion_rate"]), 0.5)
        current = self.row(1, 2026)
        self.assertEqual(current["coverage_status"], "uncollected")
        self.assertIsNone(current["candidate_score"])

    def test_install_is_repeatable(self):
        before = dict(self.row(1))
        with self.engine.connect() as conn:
            conn.exec_driver_sql((ROOT / "db/init/002_player_metrics.sql").read_text())
            conn.commit()
        self.assertEqual(dict(self.row(1)), before)

    def test_legacy_columns_are_migrated_without_changing_observations(self):
        before = dict(self.row(1))
        with self.engine.connect() as conn:
            # Reproduce the removed columns and their dependent view graph.
            conn.execute(text("""CREATE OR REPLACE VIEW player_metric_settings AS
                SELECT 2026 AS eligibility_season, 2023 AS first_performance_season,
                       38 AS season_games, 0.25::numeric AS card_risk_weight,
                       0.5::numeric AS consistency_penalty"""))
            conn.execute(text("ALTER VIEW player_season_metrics RENAME COLUMN fv_p10 TO sd_fv"))
            conn.execute(text("""ALTER VIEW player_season_metrics
                RENAME COLUMN season_weighted_score TO consistency_adjusted_score"""))
            conn.exec_driver_sql((ROOT / "db/init/002_player_metrics.sql").read_text())
            conn.commit()
        self.assertEqual(dict(self.row(1)), before)

    def test_migration_protects_external_dependent_views(self):
        before = dict(self.row(1))
        with self.engine.connect() as conn:
            conn.execute(text("""CREATE OR REPLACE VIEW player_metric_settings AS
                SELECT 2026 AS eligibility_season, 2023 AS first_performance_season,
                       38 AS season_games, 0.25::numeric AS card_risk_weight,
                       0.5::numeric AS consistency_penalty"""))
            conn.execute(text("CREATE VIEW custom_shortlist AS SELECT * FROM role_m_statistics"))
            with self.assertRaises(DBAPIError):
                conn.exec_driver_sql((ROOT / "db/init/002_player_metrics.sql").read_text())
            conn.rollback()
        self.assertEqual(dict(self.row(1)), before)

    def test_percentiles_interpolate_and_ignore_null_fv(self):
        with self.engine.connect() as conn:
            conn.execute(text("""UPDATE player_fixture_performance
                SET fanta_voto = CASE WHEN fixture_id = :first THEN 4 ELSE 10 END
                WHERE player_id = 6"""), {"first": self.player_fixtures[0]})
            query = text("SELECT * FROM role_m_statistics WHERE player_id = 6 AND performance_season = 2025")
            row = conn.execute(query).mappings().one()
            for percentile, expected in [(10, 4.6), (25, 5.5), (50, 7), (75, 8.5), (90, 9.4)]:
                self.assertAlmostEqual(float(row[f"fv_p{percentile}"]), expected)
            self.assertEqual(row["median_fv"], row["fv_p50"])
            self.assertEqual(row["lower_quartile_fv"], row["fv_p25"])
            conn.execute(text("""UPDATE player_fixture_performance SET fanta_voto = NULL
                WHERE player_id = 6 AND fixture_id = :first"""), {"first": self.player_fixtures[0]})
            row = conn.execute(query).mappings().one()
            self.assertEqual(row["rated_matches"], 2)
            self.assertEqual(row["fv_matches"], 1)
            for percentile in (10, 25, 50, 75, 90):
                self.assertEqual(row[f"fv_p{percentile}"], 10)
            conn.execute(text("UPDATE player_fixture_performance SET fanta_voto = NULL WHERE player_id = 6"))
            row = conn.execute(query).mappings().one()
            self.assertEqual(row["fv_matches"], 0)
            for percentile in (10, 25, 50, 75, 90):
                self.assertIsNone(row[f"fv_p{percentile}"])
            conn.rollback()

    def test_all_roles_and_position_pools_without_duplicate_assignments(self):
        with self.engine.connect() as conn:
            for role in ["Por", "Dd", "Ds", "Dc", "B", "E", "W", "T", "A", "Pc"]:
                conn.execute(text("INSERT INTO player_snapshot_role VALUES (4, :role)"), {"role": role})
            roles = conn.execute(text("""SELECT role, candidate_score, card_weight_applies, fv_p25, fv_p50, fv_p75
                FROM player_role_statistics WHERE player_id = 4 AND performance_season = 2025""")).mappings().all()
            self.assertEqual(len(roles), 12)
            for row in roles:
                expected = 7 * 0.875 if row["role"] in {"Dd", "Ds", "Dc", "B", "E", "M", "C"} else 7
                self.assertEqual(float(row["candidate_score"]), expected)
                self.assertEqual((row["fv_p25"], row["fv_p50"], row["fv_p75"]), (7, 7, 7))
            positions = conn.execute(text("""SELECT position, starting_slots, fv_matches, fv_p25, fv_p50, fv_p75
                FROM player_position_statistics WHERE player_id = 4 AND performance_season = 2025""")).mappings().all()
            self.assertEqual(len(positions), 10)
            self.assertEqual(sum(row["starting_slots"] for row in positions), 11)
            self.assertTrue(all(row["fv_matches"] == 38 for row in positions))
            self.assertTrue(all((row["fv_p25"], row["fv_p50"], row["fv_p75"]) == (7, 7, 7)
                                for row in positions))
            conn.rollback()

    def test_partial_current_season_is_not_extrapolated(self):
        with self.engine.connect() as conn:
            conn.execute(text("""INSERT INTO fixture
                (id, season, matchday, home_team_id, away_team_id, home_goals, away_goals, status, collection_id)
                OVERRIDING SYSTEM VALUE VALUES (400, 2026, 1, 1, 2, 1, 0, 'completed', 1),
                                             (401, 2026, 2, 2, 1, 0, 1, 'completed', 1)"""))
            conn.execute(text("""INSERT INTO player_fixture_performance
                (player_id, fixture_id, source_id, provider, team_id, collection_id,
                 match_rating, fanta_voto, rating_status, yellow_cards, red_cards)
                VALUES (1, 400, 1, 'Redazione Fantacalcio', 1, 1, 6, 7, 'rated', 0, 0),
                       (1, 401, 1, 'Redazione Fantacalcio', 1, 1, 6, 7, 'rated', 0, 0)"""))
            row = conn.execute(text("SELECT * FROM role_m_statistics WHERE player_id = 1 AND performance_season = 2026")).mappings().one()
            self.assertEqual(row["coverage_status"], "partial")
            self.assertEqual(row["fv_matches"], 2)
            self.assertAlmostEqual(float(row["candidate_score"]), 14 / 38)
            self.assertAlmostEqual(float(row["fv_ge7_season_fraction"]), 2 / 38)
            self.assertEqual(row["fv_ge7_rate"], 1)
            conn.rollback()

    def test_invalid_records_and_missing_event_denominators(self):
        with self.engine.connect() as conn:
            conn.execute(text("""UPDATE player_fixture_performance SET validation_issues = '["bad token"]'
                WHERE player_id = 1 AND fixture_id = :id AND source_id = 1"""), {"id": self.player_fixtures[0]})
            conn.execute(text("""UPDATE player_fixture_performance SET assists = NULL
                WHERE player_id = 1 AND fixture_id = :id AND source_id = 1"""), {"id": self.player_fixtures[1]})
            conn.execute(text("""UPDATE player_fixture_performance SET collection_id = 2
                WHERE player_id = 1 AND fixture_id = :id AND source_id = 1"""), {"id": self.player_fixtures[2]})
            row = conn.execute(text("SELECT * FROM role_m_statistics WHERE player_id = 1 AND performance_season = 2025")).mappings().one()
            self.assertEqual(row["fv_matches"], 36)
            self.assertEqual(row["bonus_sample"], 35)
            self.assertEqual(row["assist_sample"], 35)
            self.assertEqual(row["bonus_matches"], 0)
            self.assertEqual(row["assists"], 0)
            conn.rollback()


if __name__ == "__main__":
    unittest.main()
