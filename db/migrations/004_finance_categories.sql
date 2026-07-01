-- Finance Categories Management
-- Run: psql $DATABASE_URL -f db/migrations/004_finance_categories.sql

-- Create finance_categories table
CREATE TABLE IF NOT EXISTS finance_categories (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    icon TEXT DEFAULT '💰',
    keywords TEXT[],
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed default categories (only if table is empty)
INSERT INTO finance_categories (name, icon, keywords, is_active) VALUES
('mâncare', '🍔', ARRAY['mancare', 'mâncare', 'restaurant', 'pizza', 'shaorma', 'burger', 'mic dejun', 'prânz', 'cina', 'cafea', 'cafe', 'coffee', 'ceai', 'tea', 'băuturi', 'bauturi'], TRUE),
('transport', '🚗', ARRAY['uber', 'taxi', 'benzin', 'metrou', 'bus', 'transport'], TRUE),
('utilități', '🏠', ARRAY['chirie', 'internet', 'curent', 'gaz', 'utilitat'], TRUE),
('sănătate', '💊', ARRAY['medicament', 'doctor', 'farmacie', 'sanatate', 'sport', 'gym'], TRUE),
('shopping', '🛍️', ARRAY['haine', 'magazin', 'amazon', 'shopping', 'cadouri'], TRUE),
('distracție', '🎬', ARRAY['cinema', 'bar', 'concert', 'iesire', 'petrecere'], TRUE),
('educație', '📚', ARRAY['carti', 'carte', 'curs', 'training'], TRUE),
('altele', '💰', ARRAY['altele', 'diverse'], TRUE)
ON CONFLICT (name) DO NOTHING;

-- Rename budget_limits to use consistent naming (already exists but ensure it)
-- Add icon column to budget_limits for UI
ALTER TABLE budget_limits ADD COLUMN IF NOT EXISTS icon TEXT DEFAULT '💰';