BEGIN;
CREATE TABLE IF NOT EXISTS fantasy_team (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name text NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 80)
);
CREATE UNIQUE INDEX IF NOT EXISTS fantasy_team_name_idx ON fantasy_team (lower(trim(name)));
CREATE TABLE IF NOT EXISTS auction_settings (
    id integer PRIMARY KEY CHECK (id = 1),
    my_team_id bigint REFERENCES fantasy_team ON DELETE RESTRICT,
    budget integer NOT NULL DEFAULT 500 CHECK (budget = 500),
    goalkeeper_slots integer NOT NULL DEFAULT 3 CHECK (goalkeeper_slots = 3),
    minimum_outfield integer NOT NULL DEFAULT 20 CHECK (minimum_outfield = 20),
    maximum_outfield integer NOT NULL DEFAULT 25 CHECK (maximum_outfield = 25),
    revision bigint NOT NULL DEFAULT 0
);
INSERT INTO auction_settings (id) VALUES (1) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS auction_sale (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    auction_id integer NOT NULL DEFAULT 1 REFERENCES auction_settings,
    player_id bigint NOT NULL REFERENCES player,
    buyer_id bigint NOT NULL REFERENCES fantasy_team ON DELETE RESTRICT,
    price integer NOT NULL CHECK (price >= 1 AND price <= 500),
    recorded_at timestamptz NOT NULL DEFAULT now(),
    role_group text NOT NULL CHECK (role_group IN ('goalkeeper', 'outfield')),
    UNIQUE (auction_id, player_id)
);
-- Receipts survive edits/deletes/reset: an uncertain retry never resurrects a sale.
CREATE TABLE IF NOT EXISTS auction_request (
    key uuid PRIMARY KEY,
    payload jsonb NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS context_snapshot (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    content_sha256 text NOT NULL UNIQUE,
    source_uri text NOT NULL,
    retrieved_at timestamptz NOT NULL,
    observed_at timestamptz,
    verified boolean NOT NULL DEFAULT false,
    raw_values jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS context_entry (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    snapshot_id bigint NOT NULL REFERENCES context_snapshot,
    club text NOT NULL,
    supplied_name text,
    player_id bigint REFERENCES player,
    mapping_status text NOT NULL CHECK (mapping_status IN ('club', 'matched', 'ambiguous', 'unmatched', 'club_conflict')),
    fields jsonb NOT NULL,
    source_url text NOT NULL,
    observed_at timestamptz,
    retrieved_at timestamptz NOT NULL,
    verified boolean NOT NULL,
    mapping_note text
);
CREATE INDEX IF NOT EXISTS context_entry_player_idx ON context_entry (player_id);
COMMIT;
