-- 028_add_tigari_category.sql
-- Adds 'țigări' category for cigarettes, vape, and tobacco products
INSERT INTO finance_categories (name, icon, keywords, is_active)
VALUES (
    'țigări',
    '🚬',
    ARRAY['tigari', 'țigări', 'vape', 'vuse', 'glo', 'iqos', 'tutun', 'heets', 'terea', 'pods', 'capsule', 'fumat', 'bricheta'],
    TRUE
)
ON CONFLICT (name) DO UPDATE
SET is_active = TRUE,
    keywords = EXCLUDED.keywords;
