-- NULL denotes no outfield maximum; goalkeeper_slots is the minimum requirement.
BEGIN;
LOCK TABLE auction_settings IN ACCESS EXCLUSIVE MODE;
ALTER TABLE auction_settings DROP CONSTRAINT IF EXISTS auction_settings_maximum_outfield_check;
ALTER TABLE auction_settings ALTER COLUMN maximum_outfield DROP NOT NULL;
ALTER TABLE auction_settings ALTER COLUMN maximum_outfield DROP DEFAULT;
UPDATE auction_settings SET maximum_outfield = NULL, revision = revision + 1 WHERE maximum_outfield IS NOT NULL;
ALTER TABLE auction_settings ADD CONSTRAINT auction_settings_maximum_outfield_check CHECK (maximum_outfield IS NULL);
COMMENT ON COLUMN auction_settings.goalkeeper_slots IS 'Minimum goalkeeper requirement; no upper limit.';
COMMENT ON COLUMN auction_settings.maximum_outfield IS 'NULL means no upper limit.';
COMMIT;
