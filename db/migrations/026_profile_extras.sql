-- 026_profile_extras.sql — Profile extra fields

ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS units TEXT DEFAULT 'metric';
ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS language TEXT DEFAULT 'ro';
ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS week_start_day TEXT DEFAULT 'monday';
ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS currency TEXT DEFAULT 'RON';
ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS dietary_preferences TEXT;
ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS notification_config JSONB DEFAULT '{}';
