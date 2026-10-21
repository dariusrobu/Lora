CREATE TABLE IF NOT EXISTS moodle_course_sync (
    owner_id BIGINT NOT NULL,
    course_url TEXT NOT NULL,
    course_title TEXT NOT NULL,
    folder_name TEXT NOT NULL,
    material_count INT NOT NULL DEFAULT 0,
    last_synced_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (owner_id, course_url)
);

CREATE TABLE IF NOT EXISTS moodle_materials (
    id UUID PRIMARY KEY,
    owner_id BIGINT NOT NULL,
    course_url TEXT NOT NULL,
    source_url TEXT NOT NULL,
    title TEXT NOT NULL,
    section_title TEXT NOT NULL,
    filename TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (owner_id, course_url, source_url)
);
CREATE INDEX IF NOT EXISTS moodle_materials_course ON moodle_materials(owner_id, course_url);

CREATE TABLE IF NOT EXISTS moodle_posts (
    id UUID PRIMARY KEY,
    owner_id BIGINT NOT NULL,
    course_url TEXT NOT NULL,
    course_title TEXT NOT NULL,
    forum_title TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('announcement', 'forum')),
    discussion_url TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    is_read BOOLEAN NOT NULL DEFAULT false,
    archived_at TIMESTAMPTZ,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (owner_id, discussion_url)
);
CREATE INDEX IF NOT EXISTS moodle_posts_recent ON moodle_posts(owner_id, updated_at DESC);
