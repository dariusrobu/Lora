-- Expand the built-in taxonomy used by deterministic and Ollama categorization.
INSERT INTO finance_categories (name, icon, keywords, is_active) VALUES
('electronice', '💻', ARRAY['monitor', 'laptop', 'calculator', 'telefon', 'iphone', 'android', 'mouse', 'tastatura', 'tastatură', 'casti', 'căști', 'boxe', 'imprimanta', 'cablu', 'incarcator', 'încărcător', 'electronic'], TRUE),
('haine', '👕', ARRAY['haine', 'tricou', 'pantaloni', 'pantofi', 'incaltaminte', 'încălțăminte', 'geaca', 'jacheta', 'fashion'], TRUE),
('abonamente', '🔁', ARRAY['abonament', 'subscription', 'netflix', 'spotify', 'youtube premium', 'icloud', 'software'], TRUE),
('cadouri', '🎁', ARRAY['cadou', 'cadouri', 'gift'], TRUE)
ON CONFLICT (name) DO UPDATE
SET icon = EXCLUDED.icon, keywords = EXCLUDED.keywords, is_active = TRUE;
