-- db/migrations/016_weekly_reviews.sql
CREATE TABLE IF NOT EXISTS weekly_reviews (
    id          SERIAL PRIMARY KEY,
    week_start  DATE NOT NULL,
    week_end    DATE NOT NULL,
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_weekly_reviews_dates ON weekly_reviews(week_start, week_end);
