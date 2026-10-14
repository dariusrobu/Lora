ALTER TABLE finances
    ADD COLUMN IF NOT EXISTS receipt_telegram_file_id TEXT,
    ADD COLUMN IF NOT EXISTS receipt_local_path TEXT;

CREATE INDEX IF NOT EXISTS idx_finances_receipt_file
    ON finances(receipt_telegram_file_id)
    WHERE receipt_telegram_file_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_finances_receipt_local_path
    ON finances(receipt_local_path)
    WHERE receipt_local_path IS NOT NULL;
