-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Add embedding column to memory_facts
-- Gemini embeddings are typically 768 or 1536 dimensions. 
-- text-embedding-004 is 768.
ALTER TABLE memory_facts ADD COLUMN IF NOT EXISTS embedding vector(768);

-- Create index for fast retrieval
CREATE INDEX IF NOT EXISTS memory_facts_embedding_idx ON memory_facts USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
