-- Migration: 010_memory_facts_enhanced.sql
-- Date: 2026-04-27
-- Description: Enhances memory_facts table with source and expiration.

ALTER TABLE memory_facts ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'manual';
ALTER TABLE memory_facts ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;

-- Ensure category column exists (it should, but just in case)
-- ALTER TABLE memory_facts ADD COLUMN IF NOT EXISTS category TEXT DEFAULT 'general';
