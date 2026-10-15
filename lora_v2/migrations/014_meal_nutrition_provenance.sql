ALTER TABLE meal_items ADD COLUMN IF NOT EXISTS nutrition_provider TEXT;
ALTER TABLE meal_items ADD COLUMN IF NOT EXISTS nutrition_source_id TEXT;
ALTER TABLE meal_items ADD COLUMN IF NOT EXISTS nutrition_source_title TEXT;
ALTER TABLE meal_items ADD COLUMN IF NOT EXISTS nutrition_source_url TEXT;
