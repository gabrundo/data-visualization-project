-- Correct the existing auction rule while preserving teams and recorded sales.
BEGIN;
LOCK TABLE auction_settings IN ACCESS EXCLUSIVE MODE;
ALTER TABLE auction_settings DROP CONSTRAINT IF EXISTS auction_settings_goalkeeper_slots_check;
ALTER TABLE auction_settings ALTER COLUMN goalkeeper_slots SET DEFAULT 3;
UPDATE auction_settings SET goalkeeper_slots = 3, revision = revision + 1 WHERE goalkeeper_slots <> 3;
ALTER TABLE auction_settings ADD CONSTRAINT auction_settings_goalkeeper_slots_check CHECK (goalkeeper_slots = 3);
COMMIT;
