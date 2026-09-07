"""Collect historical Fantacalcio matchdays with cached, resumable imports."""

import argparse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
import json
from pathlib import Path
import time
from urllib.parse import urlparse

import requests
from sqlalchemy.exc import SQLAlchemyError

from project.etl.historical_parser import parse_matchday
from project.etl import historical_store as db
from project.etl.import_players import ROOT, database_engine

BASE_URL = "https://www.fantacalcio.it/voti-fantacalcio-serie-a"
DEFAULT_CACHE = ROOT / "data/cache/fantacalcio"


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


def write_json(path, value):
    atomic_write(path, (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode())


class Collector:
    def __init__(self, cache_dir, *, session=None, sleep=time.sleep, monotonic=time.monotonic):
        self.cache_dir = Path(cache_dir).resolve()
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": "FantacalcioUniversityResearch/0.1", "Accept": "text/html"})
        self.sleep = sleep
        self.monotonic = monotonic
        self.last_request = None

    def manifest(self, season, day):
        return self.cache_dir / str(season) / str(day) / "latest.json"

    def cached(self, season, day, url):
        try:
            meta = json.loads(self.manifest(season, day).read_text())
            if meta["url"] != url or not meta.get("reusable", True):
                return None
            path = Path(meta["cached_file"]).resolve()
            if not path.is_relative_to(self.cache_dir):
                return None
            content = path.read_bytes()
            at = datetime.fromisoformat(meta["retrieved_at"])
            if at.tzinfo is None or sha256(content).hexdigest() != meta["content_sha256"]:
                return None
            return content, meta
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def fetch(self, season, day, *, refresh=False):
        url = f"{BASE_URL}/{season}-{(season + 1) % 100:02}/{day}"
        cached = None if refresh else self.cached(season, day, url)
        if cached:
            return cached
        for attempt in range(3):
            if self.last_request is not None:
                self.sleep(max(0, 2 - (self.monotonic() - self.last_request)))
            self.last_request = self.monotonic()
            try:
                response = self.session.get(url, timeout=30, allow_redirects=False)
            except (requests.ConnectionError, requests.Timeout):
                if attempt == 2:
                    raise
                self.sleep(2 ** (attempt + 1))
                continue
            if response.status_code == 429 or 500 <= response.status_code < 600:
                if attempt == 2:
                    response.raise_for_status()
                delay = 2 ** (attempt + 1)
                retry = response.headers.get("Retry-After")
                if retry:
                    try:
                        delay = max(delay, float(retry))
                    except ValueError:
                        try:
                            delay = max(delay, (parsedate_to_datetime(retry) - datetime.now(timezone.utc)).total_seconds())
                        except (ValueError, TypeError, OverflowError):
                            pass
                response.close()
                self.sleep(delay)
                continue
            if 300 <= response.status_code < 400 or urlparse(response.url).path != urlparse(url).path:
                response.close()
                raise ValueError("Unexpected redirect from requested matchday")
            response.raise_for_status()
            if "text/html" not in response.headers.get("Content-Type", "").lower():
                response.close()
                raise ValueError("Expected an HTML response")
            content = response.content
            response.close()
            if not content.strip():
                raise ValueError("Empty matchday response")
            digest = sha256(content).hexdigest()
            path = self.manifest(season, day).parent / f"{digest}.html"
            atomic_write(path, content)
            meta = {"url": url, "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "content_sha256": digest, "cached_file": str(path), "reusable": True}
            write_json(self.manifest(season, day), meta)
            return content, meta
        raise RuntimeError("Download attempts exhausted")

    def mark_reusable(self, season, day, meta, reusable):
        write_json(self.manifest(season, day), {**meta, "reusable": reusable})


def collect(args, *, engine=None, collector=None):
    collector = collector or Collector(args.cache_dir)
    source = db.source_id(engine) if engine else None
    report = {"started_at": datetime.now(timezone.utc).isoformat(), "dry_run": args.dry_run,
              "parser_version": db.PARSER_VERSION, "pages": [], "seasons": {}, "complete": False}
    report_path = Path(args.cache_dir) / "coverage.json"
    try:
        for season in args.seasons:
            for day in args.matchdays:
                url = f"{BASE_URL}/{season}-{(season + 1) % 100:02}/{day}"
                entry = {"season": season, "matchday": day, "url": url, "status": "failed",
                         "fixtures": 0, "performances": 0, "issues": []}
                report["pages"].append(entry)
                collection = db.begin_collection(engine, source, url, season, day) if engine else None
                meta = None
                try:
                    content, meta = collector.fetch(season, day, refresh=args.refresh)
                    entry["content_sha256"] = meta["content_sha256"]
                    if engine:
                        db.update_collection(engine, collection, "downloaded", cache=meta)
                    page = parse_matchday(content, season, day)
                    entry.update(fixtures=len(page.fixtures), performances=len(page.performances),
                                 fixture_ids=[f["external_id"] for f in page.fixtures], issues=page.issues,
                                 unrated=sum(p["rating_status"] == "unrated" for p in page.performances))
                    collector.mark_reusable(season, day, meta, page.complete)
                    if not page.complete:
                        entry["status"] = "incomplete"
                        if engine:
                            db.update_collection(engine, collection, "incomplete", "\n".join(page.issues))
                    elif engine:
                        if not args.refresh and db.already_imported(engine, source, page, meta["content_sha256"]):
                            entry["status"] = "skipped"
                            db.update_collection(engine, collection, "parsed")
                        else:
                            entry.update(db.import_matchday(engine, source, collection, page))
                            entry["status"] = "imported"
                    else:
                        entry["status"] = "validated"
                except (ValueError, OSError, requests.RequestException, SQLAlchemyError) as exc:
                    error = "Database operation failed; matchday transaction rolled back" if isinstance(exc, SQLAlchemyError) else str(exc)
                    entry["issues"].append(error)
                    if meta and isinstance(exc, ValueError):
                        collector.mark_reusable(season, day, meta, False)
                    if engine:
                        db.update_collection(engine, collection, "failed", error)
                except KeyboardInterrupt:
                    entry["issues"].append("Collection interrupted")
                    if engine:
                        db.update_collection(engine, collection, "failed", "Collection interrupted")
                    raise
                print(f"{season}-{(season+1)%100:02} day {day:02}: {entry['status']}; "
                      f"{entry['fixtures']} fixtures, {entry['performances']} performances", flush=True)
                for issue in entry["issues"][:3]:
                    print(f"  {issue}", flush=True)
                write_json(report_path, report)
    finally:
        for season in args.seasons:
            pages = [p for p in report["pages"] if p["season"] == season]
            good = [p for p in pages if p["status"] in {"imported", "skipped", "validated"}]
            missing = sorted(set(args.matchdays) - {p["matchday"] for p in good})
            ids = [i for p in good for i in p.get("fixture_ids", [])]
            report["seasons"][str(season)] = {
                "requested_matchdays": len(args.matchdays), "complete_matchdays": len(good),
                "missing_or_incomplete_matchdays": missing,
                "expected_fixtures": 10 * len(args.matchdays), "unique_fixtures": len(set(ids)),
                "duplicate_fixture_ids": len(ids) - len(set(ids)),
                "performances": sum(p["performances"] for p in good),
            }
        report["complete"] = all(not s["missing_or_incomplete_matchdays"] and
                                 s["unique_fixtures"] == s["expected_fixtures"] and not s["duplicate_fixture_ids"]
                                 for s in report["seasons"].values())
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        write_json(report_path, report)
        collector.session.close()
        print(f"Coverage report: {report_path}", flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seasons", type=int, nargs="+", default=[2023, 2024, 2025], help="Season start years")
    parser.add_argument("--matchdays", type=int, nargs="+", default=list(range(1, 39)))
    parser.add_argument("--dry-run", action="store_true", help="Fetch/cache and validate without PostgreSQL")
    parser.add_argument("--refresh", action="store_true", help="Redownload and reconcile even successful pages")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    args = parser.parse_args()
    if any(s < 1900 or s > 9998 for s in args.seasons) or any(d < 1 or d > 38 for d in args.matchdays):
        parser.error("Seasons must be start years 1900–9998; matchdays must be 1–38")
    args.seasons = sorted(set(args.seasons))
    args.matchdays = sorted(set(args.matchdays))
    engine = None
    try:
        if not args.dry_run:
            engine = database_engine(args.env_file)
        report = collect(args, engine=engine)
    except KeyboardInterrupt:
        parser.exit(130, "Collection interrupted; rerun the same command to resume.\n")
    except SQLAlchemyError:
        parser.exit(1, "Database unavailable. Check PostgreSQL and .env connection settings.\n")
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Collection failed: {exc}\n")
    finally:
        if engine is not None:
            engine.dispose()
    if not report["complete"]:
        parser.exit(1, "Requested coverage is incomplete; see coverage.json.\n")


if __name__ == "__main__":
    main()
