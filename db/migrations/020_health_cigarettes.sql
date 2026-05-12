-- Migration: 020_health_cigarettes.sql
-- Date: 2026-05-12
-- Description: Adds cigarette tracking to health logs.

ALTER TABLE health_logs ADD COLUMN IF NOT EXISTS cigarettes INT DEFAULT 0;
