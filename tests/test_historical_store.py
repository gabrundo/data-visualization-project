"""Opt-in PostgreSQL tests; use a disposable schema, never the imported dataset.

Run: HISTORICAL_DB_TESTS=1 uv run python -m unittest discover -s tests -v
"""

from copy import deepcopy
from datetime import datetime, timezone
import gzip
import os
from pathlib import Path
import unittest
from uuid import uuid4

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from project.etl import historical_store as db
from project.etl.historical_parser import parse_matchday
from project.etl.import_players import ROOT, database_engine, import_players


@unittest.skipUnless(os.environ.get("HISTORICAL_DB_TESTS") == "1", "Set HISTORICAL_DB_TESTS=1 for PostgreSQL integration")
class StoreTests(unittest.TestCase):
    def setUp(self):
        self.admin = database_engine(ROOT / ".env")
        self.schema = "test_historical_" + uuid4().hex
        with self.admin.begin() as conn:
            conn.execute(text(f"CREATE SCHEMA {self.schema}"))
        self.engine = create_engine(self.admin.url, connect_args={"options": f"-csearch_path={self.schema}"}, hide_parameters=True)
        self.addCleanup(self.cleanup_schema)
        with self.engine.connect() as conn:
            conn.exec_driver_sql((ROOT / "db/init/001_schema.sql").read_text())
            conn.commit()
        frame = pd.DataFrame([{"Id": "554", "Nome": "Current Zappacosta*", "RM": "Dd;E", "Squadra": "Current team", "roles": ["Dd", "E"]}])
        import_players(self.engine, frame, ROOT / "tests/current.xlsx", "current-workbook", 2026,
                       datetime(2026, 9, 7, tzinfo=timezone.utc))
        self.source = db.source_id(self.engine)

    def cleanup_schema(self):
        self.engine.dispose()
        with self.admin.begin() as conn:
            conn.execute(text(f"DROP SCHEMA {self.schema} CASCADE"))
        self.admin.dispose()

    def page(self, season=2023, day=1):
        path = Path(__file__).parent / f"fixtures/fantacalcio/{season}-{day}.html.gz"
        return parse_matchday(gzip.decompress(path.read_bytes()), season, day)

    def collection(self, page, digest="sample"):
        collection = db.begin_collection(self.engine, self.source, "https://example.test/sample", page.season, page.matchday)
        db.update_collection(self.engine, collection, "downloaded", cache={
            "retrieved_at": datetime(2026, 9, 7, tzinfo=timezone.utc), "cached_file": "/tmp/sample.html", "content_sha256": digest})
        return collection

    def scalar(self, sql):
        with self.engine.connect() as conn:
            return conn.execute(text(sql)).scalar_one()

    def test_repeat_import_preserves_identity_current_roles_and_transfers(self):
        page = self.page()
        first = self.collection(page)
        stats = db.import_matchday(self.engine, self.source, first, page)
        self.assertEqual(stats["new_players"], 316)
        self.assertTrue(stats["name_differences"])
        self.assertTrue(db.already_imported(self.engine, self.source, page, "sample"))
        second = self.collection(page)
        db.import_matchday(self.engine, self.source, second, page)
        self.assertEqual(self.scalar("SELECT count(*) FROM player"), 317)
        self.assertEqual(self.scalar("SELECT count(*) FROM fixture"), 10)
        self.assertEqual(self.scalar("SELECT count(*) FROM player_fixture_performance"), 317)
        self.assertEqual(self.scalar("SELECT count(*) FROM player_season_snapshot"), 1)
        self.assertEqual(self.scalar("SELECT count(*) FROM player_snapshot_role"), 2)
        self.assertEqual(self.scalar("SELECT name FROM player p JOIN player_source_id i ON p.id=i.player_id WHERE i.external_id='554'"), "Current Zappacosta*")
        self.assertEqual(self.scalar("SELECT t.name FROM player_season_snapshot s JOIN team t ON t.id=s.team_id"), "Current team")
        newer = self.page(2025, 38)
        db.import_matchday(self.engine, self.source, self.collection(newer, "newer"), newer)
        # Bellanova: Torino in 2023, Atalanta in 2025. One canonical identity.
        self.assertEqual(self.scalar("""SELECT count(DISTINCT team_id) FROM player_fixture_performance p
            JOIN player_source_id i USING (player_id, source_id) WHERE i.external_id='4887'"""), 2)
        self.assertEqual(self.scalar("SELECT count(*) FROM player_source_id WHERE external_id='4887'"), 1)

    def test_constraint_failure_rolls_back_batch_and_retains_failed_attempt(self):
        page = self.page()
        broken = deepcopy(page)
        broken.performances[-1]["goals"] = -1
        collection = self.collection(page)
        with self.assertRaises(IntegrityError):
            db.import_matchday(self.engine, self.source, collection, broken)
        db.update_collection(self.engine, collection, "failed", "Test invalid goals")
        self.assertEqual(self.scalar("SELECT count(*) FROM player"), 1)
        self.assertEqual(self.scalar("SELECT count(*) FROM fixture"), 0)
        self.assertEqual(self.scalar("SELECT count(*) FROM player_fixture_performance"), 0)
        self.assertEqual(self.scalar(f"SELECT status FROM collection_record WHERE id={collection}"), "failed")
        db.import_matchday(self.engine, self.source, self.collection(page), page)
        self.assertEqual(self.scalar("SELECT count(*) FROM fixture"), 10)

    def test_incomplete_refresh_cannot_replace_successful_data(self):
        page = self.page()
        db.import_matchday(self.engine, self.source, self.collection(page), page)
        page.issues.append("Missing table")
        with self.assertRaises(ValueError):
            db.import_matchday(self.engine, self.source, self.collection(page), page)
        self.assertEqual(self.scalar("SELECT count(*) FROM player_fixture_performance"), 317)


if __name__ == "__main__":
    unittest.main()
