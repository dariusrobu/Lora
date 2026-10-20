CREATE TABLE IF NOT EXISTS receipt_product_rules (
    owner_id BIGINT NOT NULL,
    pattern TEXT NOT NULL,
    merchant_key TEXT NOT NULL DEFAULT '',
    clean_name TEXT NOT NULL,
    category TEXT NOT NULL,
    frequency INT NOT NULL DEFAULT 1,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (owner_id, pattern, merchant_key)
);

-- The complete old learning table is retained in the immutable snapshot.
-- Make its latest confirmed product categories available to the v2 parser.
INSERT INTO receipt_product_rules(owner_id,pattern,merchant_key,clean_name,category,frequency)
SELECT s.owner_id, lower(trim(item->>'raw_pattern')),
       lower(trim(coalesce(item->>'merchant',''))),
       item->>'clean_name', item->>'category',
       greatest(coalesce((item->>'frequency')::int,1),1)
FROM legacy_snapshot_tables t
JOIN legacy_snapshots s ON s.id=t.snapshot_id
CROSS JOIN LATERAL jsonb_array_elements(t.rows) item
WHERE t.table_name='receipt_product_memory'
  AND s.id=(SELECT id FROM legacy_snapshots WHERE owner_id=s.owner_id
            ORDER BY created_at DESC,id DESC LIMIT 1)
  AND length(trim(coalesce(item->>'raw_pattern','')))>=3
  AND length(trim(coalesce(item->>'category','')))>0
ON CONFLICT (owner_id,pattern,merchant_key) DO NOTHING;
