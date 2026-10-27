CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============ core assets ============
CREATE TABLE assets (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  kind            TEXT NOT NULL CHECK (kind IN ('video','image','document')),
  title           TEXT NOT NULL,
  source_uri      TEXT,                 -- original URL or 'self-filmed'
  storage_key     TEXT NOT NULL,        -- object-store key
  license         TEXT NOT NULL,        -- 'CC0','CC-BY-4.0','self','private-use'
  redistributable BOOLEAN NOT NULL DEFAULT false,
  equipment_family TEXT,                -- 'hydraulic','rotating','cnc'
  duration_s      REAL,                 -- video only
  width           INT, height INT, fps  REAL,
  page_count      INT,                  -- document only
  checksum_sha256 TEXT NOT NULL,
  ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  meta            JSONB NOT NULL DEFAULT '{}'
);
CREATE UNIQUE INDEX ON assets (checksum_sha256);

-- ============ video segments ============
CREATE TABLE segments (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  asset_id        UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
  idx             INT NOT NULL,          -- ordinal within the video
  start_s         REAL NOT NULL,
  end_s           REAL NOT NULL,
  method          TEXT NOT NULL,         -- 'shot','fixed-30s','merged','manual'
  keyframe_key    TEXT,                  -- object-store key of representative frame
  caption         TEXT,                  -- VLM-generated, the retrieval payload
  caption_model   TEXT,
  caption_prompt_v TEXT,                 -- prompt version, e.g. 'cap-v3'
  transcript      TEXT,                  -- ASR for this span, may be null/empty
  human_verified  BOOLEAN NOT NULL DEFAULT false,
  human_caption   TEXT,                  -- overrides caption when present
  CONSTRAINT span_valid CHECK (end_s > start_s)
);
CREATE INDEX ON segments (asset_id, start_s);

-- ============ document chunks ============
CREATE TABLE chunks (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  asset_id        UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
  idx             INT NOT NULL,
  doc_type        TEXT NOT NULL CHECK (doc_type IN ('manual','sop','report')),
  section_path    TEXT,                  -- '4.2 > Hydraulic Pump > Inspection'
  page_from       INT, page_to INT,
  text            TEXT NOT NULL,
  token_count     INT NOT NULL,
  tsv             TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', text)) STORED
);
CREATE INDEX ON chunks USING GIN (tsv);
CREATE INDEX ON chunks (asset_id, idx);

-- ============ images ============
CREATE TABLE images (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  asset_id        UUID REFERENCES assets(id) ON DELETE CASCADE,
  segment_id      UUID REFERENCES segments(id) ON DELETE SET NULL, -- if frame-derived
  storage_key     TEXT NOT NULL,
  caption         TEXT,
  ocr_text        TEXT,
  source          TEXT NOT NULL CHECK (source IN ('frame','standalone'))
);

-- ============ THE CONNECTIVE LAYER — the actual contribution ============
CREATE TABLE evidence_links (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  segment_id      UUID REFERENCES segments(id) ON DELETE CASCADE,
  chunk_id        UUID REFERENCES chunks(id) ON DELETE CASCADE,
  image_id        UUID REFERENCES images(id) ON DELETE CASCADE,
  relation        TEXT NOT NULL,   -- 'documents','specifies','depicts','contradicts'
  confidence      REAL NOT NULL DEFAULT 1.0,
  author          TEXT NOT NULL,   -- 'human' | 'llm-proposed'
  note            TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (num_nonnulls(segment_id, chunk_id, image_id) >= 2)
);

-- ============ vectors (one table per space, all pgvector) ============
CREATE TABLE vec_segment_text  (segment_id UUID PRIMARY KEY REFERENCES segments(id) ON DELETE CASCADE, model TEXT NOT NULL, embedding vector(1024) NOT NULL);
CREATE TABLE vec_segment_visual(segment_id UUID PRIMARY KEY REFERENCES segments(id) ON DELETE CASCADE, model TEXT NOT NULL, embedding vector(1152) NOT NULL);
CREATE TABLE vec_chunk         (chunk_id   UUID PRIMARY KEY REFERENCES chunks(id)   ON DELETE CASCADE, model TEXT NOT NULL, embedding vector(1024) NOT NULL);
CREATE TABLE vec_image         (image_id   UUID PRIMARY KEY REFERENCES images(id)   ON DELETE CASCADE, model TEXT NOT NULL, embedding vector(1152) NOT NULL);

CREATE INDEX ON vec_segment_text   USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64);
CREATE INDEX ON vec_segment_visual USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64);
CREATE INDEX ON vec_chunk          USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64);
CREATE INDEX ON vec_image          USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64);

-- ============ evaluation ============
CREATE TABLE eval_queries (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  text          TEXT NOT NULL,
  query_type    TEXT NOT NULL,  -- 'video-only','doc-only','multi-hop','visual','unanswerable'
  difficulty    TEXT NOT NULL CHECK (difficulty IN ('easy','medium','hard')),
  split         TEXT NOT NULL CHECK (split IN ('dev','test')),
  author        TEXT NOT NULL,
  reference_answer TEXT
);

CREATE TABLE eval_gold (            -- ground-truth evidence for a query
  query_id      UUID NOT NULL REFERENCES eval_queries(id) ON DELETE CASCADE,
  segment_id    UUID REFERENCES segments(id),
  chunk_id      UUID REFERENCES chunks(id),
  image_id      UUID REFERENCES images(id),
  gold_start_s  REAL, gold_end_s REAL,   -- human-marked true span, for IoU
  grade         SMALLINT NOT NULL DEFAULT 2 CHECK (grade IN (1,2)) -- 2=essential,1=helpful
);

CREATE TABLE eval_runs (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  config_name   TEXT NOT NULL,     -- one of the ablation config ids in §13.5: 'A0'…'A10'
  git_sha       TEXT NOT NULL,
  params        JSONB NOT NULL,
  started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  metrics       JSONB
);

CREATE TABLE eval_results (
  run_id        UUID NOT NULL REFERENCES eval_runs(id) ON DELETE CASCADE,
  query_id      UUID NOT NULL REFERENCES eval_queries(id),
  retrieved     JSONB NOT NULL,    -- ranked evidence ids + scores
  answer        TEXT,
  judge         JSONB,             -- faithfulness, correctness, citation scores + rationale
  latency_ms    INT
);

CREATE TABLE stage_status (
  asset_id   UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
  stage      TEXT NOT NULL,
  status     TEXT NOT NULL CHECK (status IN ('pending','running','done','failed')),
  input_hash TEXT NOT NULL,   -- hash of (upstream outputs + stage config + model + prompt version)
  error      TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (asset_id, stage)
);

ALTER TABLE segments ADD COLUMN annotation_author TEXT;
ALTER TABLE segments ADD CONSTRAINT segment_start_valid CHECK (start_s >= 0);
ALTER TABLE segments ADD CONSTRAINT segment_ordinal_unique UNIQUE (asset_id, method, idx);
ALTER TABLE chunks ADD CONSTRAINT chunk_ordinal_unique UNIQUE (asset_id, idx);
ALTER TABLE chunks ADD CONSTRAINT pages_valid CHECK (
  (page_from IS NULL AND page_to IS NULL) OR
  (page_from IS NOT NULL AND page_to IS NOT NULL AND page_from >= 1 AND page_to >= page_from)
);
ALTER TABLE evidence_links ADD CONSTRAINT confidence_valid CHECK (confidence BETWEEN 0 AND 1);
ALTER TABLE evidence_links ADD CONSTRAINT link_unique UNIQUE NULLS NOT DISTINCT (segment_id, chunk_id, image_id, relation);
ALTER TABLE eval_gold ADD CONSTRAINT one_gold_target CHECK (num_nonnulls(segment_id, chunk_id, image_id) = 1);
ALTER TABLE eval_gold ADD CONSTRAINT gold_span_valid CHECK (
  (gold_start_s IS NULL AND gold_end_s IS NULL) OR
  (segment_id IS NOT NULL AND gold_start_s IS NOT NULL AND gold_end_s IS NOT NULL
   AND gold_start_s >= 0 AND gold_end_s > gold_start_s)
);
