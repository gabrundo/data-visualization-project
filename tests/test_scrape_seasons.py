"""Offline parser and collector regression tests using historical source samples."""

import argparse
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from bs4 import BeautifulSoup
import requests

from project.etl.historical_parser import ParseError, number, parse_matchday
from project.etl.scrape_seasons import BASE_URL, Collector, collect

FIXTURES = Path(__file__).parent / "fixtures/fantacalcio"


def sample(season=2023, day=1):
    return gzip.decompress((FIXTURES / f"{season}-{day}.html.gz").read_bytes())


def response(content=None, status=200, headers=None):
    result = requests.Response()
    result.status_code = status
    result.url = f"{BASE_URL}/2023-24/1"
    result.headers.update({"Content-Type": "text/html", **(headers or {})})
    result._content = sample() if content is None else content
    result._content_consumed = True
    return result


class ParserTests(unittest.TestCase):
    def test_three_seasons_and_known_values(self):
        for season, day, count, name, rating, fv in [
            (2023, 1, 317, "Musso", "6.5", "6.5"),
            (2024, 1, 310, "Musso", "6", "6"),
            (2025, 38, 320, "Sportiello", "5.5", "4.5"),
        ]:
            with self.subTest(season=season):
                page = parse_matchday(sample(season, day), season, day)
                self.assertTrue(page.complete, page.issues)
                self.assertEqual(len(page.fixtures), 10)
                self.assertEqual(len(page.performances), count)
                row = page.performances[0]
                self.assertEqual((row["name"], str(row["match_rating"]), str(row["fanta_voto"])), (name, rating, fv))
                self.assertEqual(len({p["external_id"] for p in page.performances}), count)
                self.assertTrue(all(p["raw_values"]["role"] != "all" for p in page.performances))
                self.assertTrue(all(p["minutes"] is None and p["appeared"] is None for p in page.performances))

    def test_provider_events_cards_and_unrated(self):
        page = parse_matchday(sample(), 2023, 1)
        rows = {p["name"]: p for p in page.performances}
        # Ruggeri has a different statistical rating: 7 rather than editorial 6.5.
        self.assertEqual(str(rows["Ruggeri"]["match_rating"]), "6.5")
        self.assertEqual(rows["Ruggeri"]["assists"], 1)
        self.assertEqual(rows["Zortea"]["goals"], 1)
        self.assertEqual(str(rows["Zortea"]["fanta_voto"]), "10")
        self.assertEqual(rows["Corazza"]["rating_status"], "unrated")
        self.assertIsNone(rows["Corazza"]["match_rating"])
        self.assertIsNone(rows["Corazza"]["fanta_voto"])
        self.assertEqual(rows["Corazza"]["goals"], 0)
        self.assertEqual(rows["Corazza"]["raw_values"]["match_rating"], "55")
        self.assertEqual(sum(p["yellow_cards"] for p in page.performances), 36)
        newer = parse_matchday(sample(2024, 1), 2024, 1)
        self.assertEqual(sum(p["red_cards"] for p in newer.performances), 1)

    def test_provider_position_is_read_from_header(self):
        soup = BeautifulSoup(sample(), "html.parser")
        table = soup.select_one(".grades-table")
        headers = table.select("thead tr:nth-of-type(2) th:first-child .group img")
        headers[0]["title"], headers[1]["title"] = headers[1]["title"], headers[0]["title"]
        page = parse_matchday(str(soup).encode(), 2023, 1)
        self.assertEqual(str(next(p for p in page.performances if p["name"] == "Ruggeri")["match_rating"]), "7")

    def test_rejects_wrong_season_day_empty_and_malformed(self):
        for content, season, day in [(sample(), 2024, 1), (sample(), 2023, 2), (b"", 2023, 1), (b"<html>Login</html>", 2023, 1)]:
            with self.subTest(season=season, day=day), self.assertRaises(ParseError):
                parse_matchday(content, season, day)
        for selector in ["li.match", "li.team-table", "a.player-link", "thead tr:nth-of-type(2) th:first-child .group img"]:
            soup = BeautifulSoup(sample(), "html.parser")
            selected = soup.select_one(selector)
            if selector == "a.player-link":
                selected["href"] = "/invalid"
            elif "img" in selector:
                selected["title"] = "Unknown"
            else:
                selected.insert_after(BeautifulSoup(str(selected), "html.parser"))
            with self.subTest(selector=selector), self.assertRaises(ParseError):
                parse_matchday(str(soup).encode(), 2023, 1)

    def test_incomplete_page_and_invalid_numeric_are_reported(self):
        soup = BeautifulSoup(sample(), "html.parser")
        soup.select_one("li.team-table").decompose()
        page = parse_matchday(str(soup).encode(), 2023, 1)
        self.assertFalse(page.complete)
        self.assertIn("Missing rating table", page.issues[0])
        soup = BeautifulSoup(sample(), "html.parser")
        soup.select_one(".player-grade")["data-value"] = "broken"
        page = parse_matchday(str(soup).encode(), 2023, 1)
        self.assertFalse(page.complete)
        self.assertTrue(page.performances[0]["validation_issues"])
        self.assertEqual(page.performances[0]["raw_values"]["match_rating"], "broken")

    def test_numeric_semantics(self):
        self.assertEqual(number("0", integer=True), 0)
        self.assertEqual(number("55", integer=True), 55)
        for token in [None, "", "-", "55", "56", "s.v."]:
            self.assertIsNone(number(token, rating=True))
        for token in ["nan", "Infinity", "broken", "11"]:
            with self.assertRaises(ParseError):
                number(token, rating=True)
        with self.assertRaises(ParseError):
            number("1,5", integer=True)

    def test_placeholder_only_team_is_incomplete(self):
        soup = BeautifulSoup(sample(), "html.parser")
        for grade in soup.select_one(".grades-table").select(".player-grade"):
            grade["data-value"] = "55"
        page = parse_matchday(str(soup).encode(), 2023, 1)
        self.assertFalse(page.complete)
        self.assertIn("no published numeric ratings", page.issues[0])


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.session = Mock()
        self.session.get.return_value = response()
        self.sleep = Mock()
        self.collector = Collector(self.temp.name, session=self.session, sleep=self.sleep, monotonic=lambda: 0)

    def test_cache_resume_refresh_and_corrupt_cache(self):
        content, first = self.collector.fetch(2023, 1)
        again, second = self.collector.fetch(2023, 1)
        self.assertEqual((content, first), (again, second))
        self.session.get.assert_called_once()
        self.collector.fetch(2023, 1, refresh=True)
        self.assertEqual(self.session.get.call_count, 2)
        Path(first["cached_file"]).write_bytes(b"corrupt")
        self.collector.fetch(2023, 1)
        self.assertEqual(self.session.get.call_count, 3)
        self.sleep.assert_any_call(2)

    def test_retries_and_retry_after(self):
        self.session.get.side_effect = [requests.Timeout(), response(status=429, headers={"Retry-After": "9"}), response()]
        self.collector.fetch(2023, 1)
        self.assertEqual(self.session.get.call_count, 3)
        self.sleep.assert_any_call(9)

    def test_http_date_retry_after(self):
        from email.utils import format_datetime
        from datetime import timedelta
        retry = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=30))
        self.session.get.side_effect = [response(status=503, headers={"Retry-After": retry}), response()]
        self.collector.fetch(2023, 1)
        self.assertGreater(self.sleep.call_args_list[0].args[0], 25)

    def test_rejects_redirect_empty_non_html_and_permanent_failure(self):
        for r in [response(status=302), response(b""), response(headers={"Content-Type": "application/json"}), response(status=404)]:
            self.session.get.return_value = r
            with self.subTest(status=r.status_code), self.assertRaises((ValueError, requests.HTTPError)):
                self.collector.fetch(2023, 1)
        self.assertEqual(self.session.get.call_count, 4)

    def test_failure_after_three_attempts(self):
        self.session.get.side_effect = requests.ConnectionError("Disconnected")
        with self.assertRaises(requests.ConnectionError):
            self.collector.fetch(2023, 1)
        self.assertEqual(self.session.get.call_count, 3)

    def test_dry_run_report_and_incomplete_resume(self):
        args = argparse.Namespace(cache_dir=Path(self.temp.name), dry_run=True, seasons=[2023], matchdays=[1], refresh=False)
        self.session.get.return_value = response(b"<html>Unavailable</html>")
        first = collect(args, collector=self.collector)
        self.assertFalse(first["complete"])
        self.assertEqual(first["seasons"]["2023"]["missing_or_incomplete_matchdays"], [1])
        self.session.get.return_value = response()
        second = collect(args, collector=self.collector)
        self.assertTrue(second["complete"])
        self.assertEqual(self.session.get.call_count, 2)
        on_disk = json.loads((Path(self.temp.name) / "coverage.json").read_text())
        self.assertEqual(on_disk["seasons"]["2023"]["unique_fixtures"], 10)


if __name__ == "__main__":
    unittest.main()
