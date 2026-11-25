-- Applied at API startup; every statement must be safe to run again.
-- (Replace with a migration tool once a released schema has to change.)

CREATE TABLE IF NOT EXISTS documents (
    id           uuid PRIMARY KEY,
    kind         text NOT NULL CHECK (kind IN ('resume', 'job')),
    title        text NOT NULL,
    filename     text,
    content_hash text NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now()
);

-- There is only ever one resume.
CREATE UNIQUE INDEX IF NOT EXISTS one_resume ON documents (kind) WHERE kind = 'resume';

CREATE TABLE IF NOT EXISTS document_lines (
    document_id uuid    NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    line_no     integer NOT NULL,
    section     text,
    text        text    NOT NULL,
    PRIMARY KEY (document_id, line_no)
);
