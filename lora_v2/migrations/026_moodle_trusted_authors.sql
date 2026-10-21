ALTER TABLE moodle_posts ADD COLUMN IF NOT EXISTS filtered_out BOOLEAN NOT NULL DEFAULT false;

CREATE TABLE IF NOT EXISTS moodle_trusted_authors (
    owner_id BIGINT NOT NULL,
    course_url TEXT NOT NULL,
    author_key TEXT NOT NULL,
    author_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (owner_id, course_url, author_key)
);
