-- Migration 005: Fix week_type CHECK constraint to match code values
-- Schema had ('par', 'impar', 'both') but code uses ('odd', 'even', 'both')
-- This migration drops the old constraint and adds the correct one.
-- Also migrates any existing rows with old Romanian values.

-- 1. Migrate existing rows
UPDATE schedule SET week_type = 'odd'  WHERE week_type = 'impar';
UPDATE schedule SET week_type = 'even' WHERE week_type = 'par';

-- 2. Drop old constraint and add corrected one
ALTER TABLE schedule DROP CONSTRAINT IF EXISTS schedule_week_type_check;
ALTER TABLE schedule ADD CONSTRAINT schedule_week_type_check
    CHECK (week_type IN ('odd', 'even', 'both'));
