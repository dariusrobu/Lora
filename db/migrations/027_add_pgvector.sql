-- Migration 027: Add pgvector support for semantic memory search
-- Uses cosine similarity (<=> operator) for finding semantically similar facts.
-- Requires pgvector extension (available on Neon/Supabase/Railway Postgres).

-- 1. Enable pgvector extension (safe to re-run)
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Add vector column to memory_facts if not already present
-- Dimension: 768 matches gemini-embedding-001 and nomic-embed-text output size
ALTER TABLE memory_facts
    ADD COLUMN IF NOT EXISTS embedding_vec vector(768);

-- 3. Populate embedding_vec from existing TEXT embedding column (if data present)
-- Only converts rows that have text embeddings but not vector embeddings yet.
-- The text format is "[0.1, 0.2, ...]" from Python str(list).
UPDATE memory_facts
SET embedding_vec = embedding::vector
WHERE embedding IS NOT NULL
  AND embedding_vec IS NULL
  AND embedding ~ '^\[[-0-9.,\s]+\]$';

-- 4. Create HNSW index for fast approximate nearest-neighbor search
-- ef_construction=64 and m=16 are balanced defaults for < 1M rows.
CREATE INDEX IF NOT EXISTS idx_memory_facts_embedding_hnsw
    ON memory_facts USING hnsw (embedding_vec vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- 5. (Optional) Also create ivfflat index as fallback — better for exact search
-- CREATE INDEX IF NOT EXISTS idx_memory_facts_embedding_ivf
--     ON memory_facts USING ivfflat (embedding_vec vector_cosine_ops)
--     WITH (lists = 100);
