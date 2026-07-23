-- source_document를 검색 가능한 문단 단위로 나눈 VDB 핵심 테이블입니다.
CREATE TABLE IF NOT EXISTS knowledge_chunk (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_document_id  UUID NOT NULL REFERENCES source_document(id) ON DELETE RESTRICT,
    chunk_index         INTEGER NOT NULL CHECK (chunk_index >= 0),
    chunk_version       INTEGER NOT NULL DEFAULT 1 CHECK (chunk_version > 0),
    section_type        VARCHAR(60) NOT NULL,
    heading             TEXT,
    content             TEXT NOT NULL,
    token_count         INTEGER CHECK (token_count IS NULL OR token_count > 0),
    content_hash        CHAR(64) NOT NULL,
    embedding_model     VARCHAR(120),
    embedding           VECTOR(1536),
    metadata            JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    embedded_at         TIMESTAMPTZ,

    CONSTRAINT uq_knowledge_chunk_position
        UNIQUE (source_document_id, chunk_version, chunk_index),
    CONSTRAINT knowledge_chunk_embedding_state_check
        CHECK (
            (embedding IS NULL AND embedded_at IS NULL)
            OR (embedding IS NOT NULL AND embedding_model IS NOT NULL AND embedded_at IS NOT NULL)
        )
);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunk_document
    ON knowledge_chunk (source_document_id, chunk_version, chunk_index);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunk_section
    ON knowledge_chunk (section_type);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunk_metadata_gin
    ON knowledge_chunk USING GIN (metadata);

-- 데이터가 적을 때는 순차 검색으로도 충분합니다. 문서가 늘어나면 이 인덱스를 사용합니다.
CREATE INDEX IF NOT EXISTS idx_knowledge_chunk_embedding_hnsw
    ON knowledge_chunk USING HNSW (embedding vector_cosine_ops)
    WHERE embedding IS NOT NULL;

COMMENT ON TABLE knowledge_chunk IS 'VDB에서 의미 기반 검색을 수행하는 문서 청크';
COMMENT ON COLUMN knowledge_chunk.embedding IS '1536차원 임베딩. 모델을 바꾸면 차원과 마이그레이션 전략을 함께 변경';

