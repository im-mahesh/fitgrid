-- Applied at API startup; every statement must be safe to run again.
-- (Replace with a migration tool once a released schema has to change.)

CREATE EXTENSION IF NOT EXISTS vector;

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

-- One extraction per job; it is replaced when the prompt or model changes.
CREATE TABLE IF NOT EXISTS extractions (
    document_id    uuid PRIMARY KEY REFERENCES documents (id) ON DELETE CASCADE,
    prompt_version text NOT NULL,
    model          text NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS requirements (
    document_id  uuid      NOT NULL REFERENCES extractions (document_id) ON DELETE CASCADE,
    position     integer   NOT NULL,
    text         text      NOT NULL,
    importance   text      NOT NULL CHECK (importance IN ('must', 'nice')),
    category     text      NOT NULL,
    line_numbers integer[] NOT NULL,
    PRIMARY KEY (document_id, position)
);

-- Metrics only, never document text, so it is kept when documents are deleted.
CREATE TABLE IF NOT EXISTS llm_calls (
    id             bigserial PRIMARY KEY,
    created_at     timestamptz NOT NULL DEFAULT now(),
    stage          text    NOT NULL,
    model          text    NOT NULL,
    prompt_version text    NOT NULL,
    request_id     text,
    input_tokens   integer,
    output_tokens  integer,
    duration_ms    integer NOT NULL,
    outcome        text    NOT NULL,
    rejected_items integer NOT NULL DEFAULT 0,
    cost_usd       numeric(12, 6)
);

-- Results of one job against one resume. Deleting or replacing the resume, or
-- re-extracting the job's requirements, removes them, so they can't go stale.
CREATE TABLE IF NOT EXISTS match_runs (
    job_id         uuid PRIMARY KEY REFERENCES extractions (document_id) ON DELETE CASCADE,
    resume_id      uuid NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    prompt_version text NOT NULL,
    model          text NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS matches (
    job_id       uuid      NOT NULL REFERENCES match_runs (job_id) ON DELETE CASCADE,
    position     integer   NOT NULL,
    verdict      text      NOT NULL,
    reason       text      NOT NULL,
    line_numbers integer[] NOT NULL,
    PRIMARY KEY (job_id, position)
);

-- Embeddings of document lines, filled in on first search. The size must match
-- embeddings.DIMENSIONS.
CREATE TABLE IF NOT EXISTS line_embeddings (
    document_id uuid        NOT NULL,
    line_no     integer     NOT NULL,
    model       text        NOT NULL,
    embedding   vector(384) NOT NULL,
    PRIMARY KEY (document_id, line_no),
    FOREIGN KEY (document_id, line_no)
        REFERENCES document_lines (document_id, line_no) ON DELETE CASCADE
);
