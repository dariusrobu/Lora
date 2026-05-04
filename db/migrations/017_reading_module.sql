-- db/migrations/017_reading_module.sql

CREATE TABLE IF NOT EXISTS books (
    id            SERIAL PRIMARY KEY,
    title         TEXT NOT NULL,
    author        TEXT,
    total_pages   INT,
    pages_read    INT DEFAULT 0,
    status        TEXT DEFAULT 'reading' CHECK (status IN ('reading', 'completed', 'wishlist', 'dropped')),
    rating        INT CHECK (rating >= 1 AND rating <= 5),
    started_at    DATE DEFAULT CURRENT_DATE,
    finished_at   DATE,
    notes         TEXT, -- general summary
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS book_notes (
    id            SERIAL PRIMARY KEY,
    book_id       INT REFERENCES books(id) ON DELETE CASCADE,
    content       TEXT NOT NULL,
    page_number   INT,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_books_status ON books(status);
CREATE INDEX IF NOT EXISTS idx_book_notes_book_id ON book_notes(book_id);
