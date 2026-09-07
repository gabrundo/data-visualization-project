"""Import Fantacalcio Excel player identities and dated Mantra eligibility."""

import argparse
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path

from dotenv import dotenv_values
import pandas as pd
from sqlalchemy import URL, create_engine, text
from sqlalchemy.exc import SQLAlchemyError


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FILE = ROOT / "data/Quotazioni_Fantacalcio_Stagione_2026_27.xlsx"
ROLES = {"Por", "Dc", "Ds", "Dd", "E", "M", "C", "W", "T", "A", "Pc", "B"}


def read_players(content: bytes) -> pd.DataFrame:
    """Read the second-row headers and validate before touching the database."""
    frame = pd.read_excel(BytesIO(content), skiprows=1, dtype="string")
    frame = frame.rename(columns={"Rm": "RM"})
    required = ["Id", "Nome", "RM", "Squadra"]
    missing = set(required) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing Excel columns: {', '.join(sorted(missing))}")
    frame = frame[required].dropna(how="all").copy()
    if frame.empty:
        raise ValueError("The workbook contains no players.")
    for column in required:
        frame[column] = frame[column].str.strip()
        if (frame[column].isna() | frame[column].eq("")).any():
            raise ValueError(f"Missing value in column {column}.")
    if not frame["Id"].str.fullmatch(r"[0-9]+").all():
        raise ValueError("Player IDs must be positive integers.")
    frame["Id"] = frame["Id"].map(lambda value: str(int(value)))
    if frame["Id"].eq("0").any() or frame["Id"].duplicated().any():
        raise ValueError("Player IDs must be positive and unique within the file.")
    frame["roles"] = frame["RM"].map(lambda value: sorted(set(value.split(";"))))
    for roles in frame["roles"]:
        if not set(roles) <= ROLES:
            raise ValueError(f"Unrecognized Mantra roles: {roles}")
    return frame


def database_engine(env_file: Path):
    settings = {**dotenv_values(env_file, interpolate=False), **os.environ}
    if not settings.get("POSTGRES_PASSWORD"):
        raise ValueError(f"Set POSTGRES_PASSWORD in {env_file} or the environment.")
    url = URL.create(
        "postgresql+psycopg",
        username=settings.get("POSTGRES_USER", "fantacalcio"),
        password=settings["POSTGRES_PASSWORD"],
        host=settings.get("POSTGRES_HOST", "127.0.0.1"),
        port=int(settings.get("POSTGRES_PORT", "5432")),
        database=settings.get("POSTGRES_DB", "fantacalcio"),
    )
    return create_engine(url, connect_args={"connect_timeout": 5}, hide_parameters=True)


def import_players(engine, frame, path, digest, season, snapshot_at=None):
    """Commit all players together; reuse a file's first snapshot on reimport."""
    with engine.begin() as conn:
        # Serialize this importer to avoid races while resolving external IDs.
        conn.execute(text("SELECT pg_advisory_xact_lock(202627, 1)"))

        def scalar(sql, **params):
            return conn.execute(text(sql), params).scalar_one()

        source_id = scalar("""
            INSERT INTO data_source (name, base_url)
            VALUES ('Fantacalcio.it', 'https://www.fantacalcio.it')
            ON CONFLICT (name) DO UPDATE SET base_url = EXCLUDED.base_url
            RETURNING id
        """)
        conn.execute(text("INSERT INTO season VALUES (:season) ON CONFLICT DO NOTHING"),
                     {"season": season})
        if snapshot_at is None:
            snapshot_at = conn.execute(text("""
                SELECT min(s.snapshot_at) FROM player_season_snapshot s
                JOIN collection_record c ON c.id = s.collection_id
                WHERE c.source_id = :source AND c.content_sha256 = :digest
                  AND s.season = :season
            """), {"source": source_id, "digest": digest, "season": season}).scalar()
            snapshot_at = snapshot_at or datetime.now(timezone.utc)
        collection_id = scalar("""
            INSERT INTO collection_record
                (source_id, source_uri, cached_file, content_sha256, requested_season, status)
            VALUES (:source, :uri, :path, :digest, :season, 'pending') RETURNING id
        """, source=source_id, uri=path.as_uri(), path=str(path), digest=digest, season=season)

        for row in frame.to_dict("records"):
            player_id = conn.execute(text("""
                SELECT player_id FROM player_source_id
                WHERE source_id = :source AND external_id = :external
            """), {"source": source_id, "external": row["Id"]}).scalar_one_or_none()
            if player_id is None:
                player_id = scalar("INSERT INTO player (name) VALUES (:name) RETURNING id",
                                   name=row["Nome"])
                conn.execute(text("""
                    INSERT INTO player_source_id (source_id, external_id, player_id)
                    VALUES (:source, :external, :player)
                """), {"source": source_id, "external": row["Id"], "player": player_id})
            else:
                conn.execute(text("UPDATE player SET name = :name WHERE id = :id"),
                             {"name": row["Nome"], "id": player_id})
            team_id = scalar("""
                INSERT INTO team (name) VALUES (:name)
                ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name RETURNING id
            """, name=row["Squadra"])
            snapshot_id = scalar("""
                INSERT INTO player_season_snapshot
                    (player_id, season, source_id, snapshot_at, team_id, collection_id, raw_values)
                VALUES (:player, :season, :source, :at, :team, :collection, CAST(:raw AS jsonb))
                ON CONFLICT (player_id, season, source_id, snapshot_at) DO UPDATE
                    SET team_id = EXCLUDED.team_id, collection_id = EXCLUDED.collection_id,
                        raw_values = EXCLUDED.raw_values
                RETURNING id
            """, player=player_id, season=season, source=source_id, at=snapshot_at,
                team=team_id, collection=collection_id,
                raw=json.dumps({key: row[key] for key in ("Id", "Nome", "RM", "Squadra")}))
            conn.execute(text("DELETE FROM player_snapshot_role WHERE snapshot_id = :id"),
                         {"id": snapshot_id})
            conn.execute(text("""
                INSERT INTO player_snapshot_role (snapshot_id, role) VALUES (:id, :role)
            """), [{"id": snapshot_id, "role": role} for role in row["roles"]])
        conn.execute(text("UPDATE collection_record SET status = 'parsed' WHERE id = :id"),
                     {"id": collection_id})
    return len(frame)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", nargs="?", type=Path, default=DEFAULT_FILE)
    parser.add_argument("--season", type=int, default=2026, help="Season start year (default: 2026)")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--snapshot-at", help="Source timestamp in ISO 8601, including timezone")
    parser.add_argument("--dry-run", action="store_true", help="Validate Excel without connecting")
    args = parser.parse_args()
    engine = None
    try:
        if not 1900 <= args.season <= 32767:
            raise ValueError("Season must be a start year between 1900 and 32767.")
        at = datetime.fromisoformat(args.snapshot_at) if args.snapshot_at else None
        if at is not None and at.tzinfo is None:
            raise ValueError("--snapshot-at must include a timezone, e.g. 2026-09-07T12:00:00+02:00")
        path = args.file.resolve()
        content = path.read_bytes()
        frame = read_players(content)
        if args.dry_run:
            print(frame[["Id", "Nome", "RM", "Squadra"]].head(10).to_string(index=False))
            print(f"Validated {len(frame)} players for {args.season}–{args.season + 1}.")
            return
        engine = database_engine(args.env_file)
        count = import_players(engine, frame, path, sha256(content).hexdigest(), args.season, at)
        print(f"Imported {count} players for {args.season}–{args.season + 1}.")
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Import failed: {exc}\n")
    except SQLAlchemyError:
        parser.exit(1, "Database import failed; transaction rolled back. Check PostgreSQL is "
                    "running, .env credentials are correct, and the schema includes role B.\n")
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    main()
