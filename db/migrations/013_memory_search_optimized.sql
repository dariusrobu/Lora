-- Migration: 013_memory_search_optimized.sql
-- Date: 2026-04-27
-- Description: Adds GIN indexes for semantic search in memory and history.

CREATE INDEX IF NOT EXISTS idx_memory_facts_search_simple ON memory_facts USING GIN(to_tsvector('simple', fact));
CREATE INDEX IF NOT EXISTS idx_message_history_search_simple ON message_history USING GIN(to_tsvector('simple', content));
