"""Transactional persistence against db/init/001_schema.sql."""

import json

from sqlalchemy import text

from project.etl.historical_parser import EVENTS, PROVIDER

PARSER_VERSION = "1"


def scalar(conn, sql, **params):
    return conn.execute(text(sql), params).scalar_one()


def source_id(engine):
    with engine.begin() as conn:
        return scalar(conn, """
            INSERT INTO data_source (name, base_url)
            VALUES ('Fantacalcio.it', 'https://www.fantacalcio.it')
            ON CONFLICT (name) DO UPDATE SET base_url = EXCLUDED.base_url RETURNING id
        """)


def begin_collection(engine, source, url, season, day):
    with engine.begin() as conn:
        return scalar(conn, """
            INSERT INTO collection_record (source_id, source_uri, requested_season, requested_matchday)
            VALUES (:source, :url, :season, :day) RETURNING id
        """, source=source, url=url, season=season, day=day)


def update_collection(engine, collection, status, error=None, cache=None):
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE collection_record SET status = :status, error_details = :error WHERE id = :id
        """), {"id": collection, "status": status, "error": error})
        if cache:
            conn.execute(text("""
                UPDATE collection_record SET retrieved_at = :at, cached_file = :path,
                    content_sha256 = :digest WHERE id = :id
            """), {"id": collection, "at": cache["retrieved_at"], "path": cache["cached_file"],
                   "digest": cache["content_sha256"]})


def already_imported(engine, source, page, digest):
    """Only skip if this parser's complete batch still owns all its observations."""
    with engine.connect() as conn:
        count = scalar(conn, """
            SELECT count(*) FROM player_fixture_performance p
            JOIN collection_record c ON c.id = p.collection_id
            JOIN fixture f ON f.id = p.fixture_id
            WHERE c.source_id = :source AND c.content_sha256 = :digest AND c.status = 'parsed'
              AND f.season = :season AND f.matchday = :day AND p.provider = :provider
              AND p.raw_values ->> 'parser_version' = :version
        """, source=source, digest=digest, season=page.season, day=page.matchday,
                       provider=PROVIDER, version=PARSER_VERSION)
        return count == len(page.performances) and count > 0


def import_matchday(engine, source, collection, page):
    if not page.complete:
        raise ValueError("Incomplete pages must not replace validated database observations")
    stats = {"new_players": 0, "linked_players": 0, "name_differences": []}
    with engine.begin() as conn:
        # Share the identity lock with the workbook importer.
        conn.execute(text("SELECT pg_advisory_xact_lock(202627, 1)"))
        conn.execute(text("INSERT INTO season VALUES (:year) ON CONFLICT DO NOTHING"), {"year": page.season})
        team_ids = {}
        for row in conn.execute(text("SELECT id, name FROM team")):
            key = row.name.casefold().strip()
            if key in team_ids:
                raise ValueError(f"Ambiguous canonical team name: {row.name}")
            team_ids[key] = row.id
        for fixture in page.fixtures:
            for side in ("home", "away"):
                name = fixture[f"{side}_team"]
                key = name.casefold().strip()
                if key not in team_ids:
                    team_ids[key] = scalar(conn, "INSERT INTO team (name) VALUES (:name) RETURNING id", name=name)
        fixture_ids = {}
        for fixture in page.fixtures:
            params = {**fixture, "collection": collection,
                      "home": team_ids[fixture["home_team"].casefold().strip()],
                      "away": team_ids[fixture["away_team"].casefold().strip()]}
            fixture_id = scalar(conn, """
                INSERT INTO fixture (season, matchday, played_at, home_team_id, away_team_id,
                                     home_goals, away_goals, status, collection_id)
                VALUES (:season, :matchday, :played_at, :home, :away,
                        :home_goals, :away_goals, :status, :collection)
                ON CONFLICT (season, home_team_id, away_team_id) DO UPDATE SET
                    matchday = EXCLUDED.matchday, played_at = EXCLUDED.played_at,
                    home_goals = EXCLUDED.home_goals, away_goals = EXCLUDED.away_goals,
                    status = EXCLUDED.status, collection_id = EXCLUDED.collection_id
                RETURNING id
            """, **params)
            mapped = conn.execute(text("""
                SELECT fixture_id FROM fixture_source_id WHERE source_id = :source AND external_id = :external
            """), {"source": source, "external": fixture["external_id"]}).scalar_one_or_none()
            if mapped is not None and mapped != fixture_id:
                raise ValueError(f"Conflicting fixture source ID: {fixture['external_id']}")
            conn.execute(text("""
                INSERT INTO fixture_source_id VALUES (:source, :external, :fixture)
                ON CONFLICT DO NOTHING
            """), {"source": source, "external": fixture["external_id"], "fixture": fixture_id})
            fixture_ids[fixture["external_id"]] = fixture_id
        players = {row.external_id: (row.player_id, row.name) for row in conn.execute(text("""
            SELECT i.external_id, i.player_id, p.name FROM player_source_id i
            JOIN player p ON p.id = i.player_id WHERE i.source_id = :source
        """), {"source": source})}
        observations = []
        for row in page.performances:
            external = row["external_id"]
            if external not in players:
                player = scalar(conn, "INSERT INTO player (name) VALUES (:name) RETURNING id", name=row["name"])
                conn.execute(text("""
                    INSERT INTO player_source_id VALUES (:source, :external, :player)
                """), {"source": source, "external": external, "player": player})
                players[external] = (player, row["name"])
                stats["new_players"] += 1
            else:
                stats["linked_players"] += 1
            player, name = players[external]
            if name.strip().rstrip("*").casefold() != row["name"].casefold():
                stats["name_differences"].append({"external_id": external, "canonical": name, "historical": row["name"]})
            observations.append({**row, "player_id": player,
                                 "fixture_id": fixture_ids[row["fixture_external_id"]],
                                 "source_id": source, "provider": PROVIDER,
                                 "team_id": team_ids[row["team"].casefold().strip()], "collection_id": collection,
                                 "raw_values": json.dumps({**row["raw_values"], "parser_version": PARSER_VERSION}),
                                 "validation_issues": json.dumps(row["validation_issues"])})
        columns = ["player_id", "fixture_id", "source_id", "provider", "team_id", "collection_id",
                   "match_rating", "fanta_voto", "rating_status", "appeared", "started", "minutes",
                   *EVENTS.values(), "yellow_cards", "red_cards", "raw_values", "validation_issues"]
        values = [f"CAST(:{c} AS jsonb)" if c in {"raw_values", "validation_issues"} else f":{c}" for c in columns]
        updates = [f"{c} = EXCLUDED.{c}" for c in columns[4:]]
        conn.execute(text(f"""
            INSERT INTO player_fixture_performance ({', '.join(columns)}) VALUES ({', '.join(values)})
            ON CONFLICT (player_id, fixture_id, source_id, provider) DO UPDATE SET {', '.join(updates)}
        """), observations)
        # A corrected complete page may remove an erroneous source row. Reconcile
        # only this source/provider and the ten validated fixtures in this batch.
        conn.execute(text("""
            DELETE FROM player_fixture_performance WHERE fixture_id = ANY(:fixtures)
              AND source_id = :source AND provider = :provider AND collection_id <> :collection
        """), {"fixtures": list(fixture_ids.values()), "source": source,
               "provider": PROVIDER, "collection": collection})
        conn.execute(text("UPDATE collection_record SET status = 'parsed', error_details = NULL WHERE id = :id"),
                     {"id": collection})
    return stats
