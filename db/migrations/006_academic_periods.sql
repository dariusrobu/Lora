-- Migration 006: Add academic_periods table (moved from inline handler DDL)
CREATE TABLE IF NOT EXISTS academic_periods (
    id SERIAL PRIMARY KEY,
    academic_year VARCHAR(10),
    semester INTEGER,
    period_type VARCHAR(50),
    start_date DATE,
    end_date DATE,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (academic_year, semester, period_type, start_date)
);
CREATE INDEX IF NOT EXISTS idx_academic_periods_year ON academic_periods(academic_year, semester);
