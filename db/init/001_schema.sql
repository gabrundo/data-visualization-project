BEGIN;

CREATE TABLE data_source (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name text NOT NULL UNIQUE,
    base_url text
);

CREATE TABLE collection_record (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_id bigint NOT NULL REFERENCES data_source,
    source_uri text NOT NULL,
    retrieved_at timestamptz NOT NULL DEFAULT now(),
    content_sha256 text,c
    cached_file text,
    requested_season smallint,
    requested_matchday smallint CHECK (requested_matchday > 0),
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'downloaded', 'parsed', 'incomplete', 'failed')),
    error_details text,
    UNIQUE (id, source_id)
);

-- The start year identifies a season: 2026 means 2026–27.
CREATE TABLE season (
    start_year smallint PRIMARY KEY CHECK (start_year >= 1900)
);

CREATE TABLE player (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name text NOT NULL
);

-- IDs belong to a source namespace; names alone must never drive joins.
CREATE TABLE player_source_id (
    source_id bigint NOT NULL REFERENCES data_source,
    external_id text NOT NULL,
    player_id bigint NOT NULL REFERENCES player,
    PRIMARY KEY (source_id, external_id)
);

CREATE TABLE team (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name text NOT NULL UNIQUE
);

CREATE TABLE player_season_snapshot (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    player_id bigint NOT NULL REFERENCES player,
    season smallint NOT NULL REFERENCES season,
    source_id bigint NOT NULL REFERENCES data_source,
    snapshot_at timestamptz NOT NULL,
    team_id bigint REFERENCES team,
    collection_id bigint NOT NULL,
    raw_values jsonb NOT NULL DEFAULT '{}',
    FOREIGN KEY (collection_id, source_id) REFERENCES collection_record (id, source_id),
    UNIQUE (player_id, season, source_id, snapshot_at)
);

CREATE TABLE player_snapshot_role (
    snapshot_id bigint NOT NULL REFERENCES player_season_snapshot ON DELETE CASCADE,
    role text NOT NULL CHECK (role IN ('Por', 'Dc', 'Ds', 'Dd', 'E', 'M', 'C', 'W', 'T', 'A', 'Pc')),
    PRIMARY KEY (snapshot_id, role)
);

CREATE TABLE fixture (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    season smallint NOT NULL REFERENCES season,
    matchday smallint NOT NULL CHECK (matchday > 0),
    played_at timestamptz,
    home_team_id bigint NOT NULL REFERENCES team,
    away_team_id bigint NOT NULL REFERENCES team,
    home_goals smallint CHECK (home_goals >= 0),
    away_goals smallint CHECK (away_goals >= 0),
    status text NOT NULL DEFAULT 'unknown'
        CHECK (status IN ('unknown', 'scheduled', 'postponed', 'in_progress', 'completed', 'abandoned')),
    collection_id bigint NOT NULL REFERENCES collection_record,
    CHECK (home_team_id <> away_team_id),
    UNIQUE (season, home_team_id, away_team_id)
);

CREATE TABLE fixture_source_id (
    source_id bigint NOT NULL REFERENCES data_source,
    external_id text NOT NULL,
    fixture_id bigint NOT NULL REFERENCES fixture,
    PRIMARY KEY (source_id, external_id)
);

CREATE TABLE player_fixture_performance (
    player_id bigint NOT NULL REFERENCES player,
    fixture_id bigint NOT NULL REFERENCES fixture,
    source_id bigint NOT NULL REFERENCES data_source,
    provider text NOT NULL,
    team_id bigint NOT NULL REFERENCES team,
    collection_id bigint NOT NULL,
    match_rating numeric(5,2),
    fanta_voto numeric(6,2),
    rating_status text NOT NULL DEFAULT 'unknown'
        CHECK (rating_status IN ('unknown', 'rated', 'unrated')),
    appeared boolean,
    started boolean,
    minutes smallint CHECK (minutes >= 0),
    goals smallint CHECK (goals >= 0),
    goals_conceded smallint CHECK (goals_conceded >= 0),
    own_goals smallint CHECK (own_goals >= 0),
    penalties_scored smallint CHECK (penalties_scored >= 0),
    penalties_missed smallint CHECK (penalties_missed >= 0),
    penalties_saved smallint CHECK (penalties_saved >= 0),
    assists smallint CHECK (assists >= 0),
    yellow_cards smallint CHECK (yellow_cards >= 0),
    red_cards smallint CHECK (red_cards >= 0),
    raw_values jsonb NOT NULL DEFAULT '{}',
    validation_issues jsonb NOT NULL DEFAULT '[]',
    FOREIGN KEY (collection_id, source_id) REFERENCES collection_record (id, source_id),
    PRIMARY KEY (player_id, fixture_id, source_id, provider)
);

CREATE TABLE valuation_snapshot (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    player_id bigint NOT NULL REFERENCES player,
    season smallint NOT NULL REFERENCES season,
    source_id bigint NOT NULL REFERENCES data_source,
    snapshot_at timestamptz NOT NULL,
    collection_id bigint NOT NULL,
    -- Preserve original quotation/FVM column names, including Classic/Mantra.
    values jsonb NOT NULL,
    FOREIGN KEY (collection_id, source_id) REFERENCES collection_record (id, source_id),
    UNIQUE (player_id, season, source_id, snapshot_at)
);

CREATE TABLE season_statistics_snapshot (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    player_id bigint NOT NULL REFERENCES player,
    season smallint NOT NULL REFERENCES season,
    source_id bigint NOT NULL REFERENCES data_source,
    snapshot_at timestamptz NOT NULL,
    provider text NOT NULL,
    collection_id bigint NOT NULL,
    -- Workbook totals are reconciliation inputs, not fixture observations.
    values jsonb NOT NULL,
    FOREIGN KEY (collection_id, source_id) REFERENCES collection_record (id, source_id),
    UNIQUE (player_id, season, source_id, snapshot_at, provider)
);

CREATE INDEX fixture_season_matchday_idx ON fixture (season, matchday);
CREATE INDEX performance_fixture_idx ON player_fixture_performance (fixture_id);
CREATE INDEX snapshot_season_idx ON player_season_snapshot (season, player_id, snapshot_at DESC);
CREATE INDEX collection_source_status_idx ON collection_record (source_id, status);

COMMIT;
