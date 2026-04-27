-- Migration: 012_user_profile_enhanced.sql
-- Date: 2026-04-27
-- Description: Enhances user_profile with behavioral and preference fields.

ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS preferred_tone VARCHAR(20) DEFAULT 'direct' CHECK (preferred_tone IN ('formal', 'casual', 'direct'));
ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS active_hours_start TIME DEFAULT '08:00';
ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS active_hours_end TIME DEFAULT '22:00';
ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS frequent_categories JSONB DEFAULT '{}';
ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS language_style JSONB DEFAULT '{}';
