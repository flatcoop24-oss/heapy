-- 의료 VDB에 필요한 출처 신뢰도, 검수 상태, 유효기간과 검색 범위를 추가합니다.
ALTER TABLE source_registry
    ADD COLUMN IF NOT EXISTS trust_tier SMALLINT NOT NULL DEFAULT 4
        CHECK (trust_tier BETWEEN 1 AND 4),
    ADD COLUMN IF NOT EXISTS license_reviewed_at DATE;

COMMENT ON COLUMN source_registry.trust_tier IS
    '1=법령·정부 원문, 2=전문학회 지침, 3=검수된 자체 문서, 4=보조 자료';

ALTER TABLE source_document
    ADD COLUMN IF NOT EXISTS effective_from DATE,
    ADD COLUMN IF NOT EXISTS effective_to DATE,
    ADD COLUMN IF NOT EXISTS review_status VARCHAR(30) NOT NULL DEFAULT 'DRAFT'
        CHECK (review_status IN ('DRAFT', 'SOURCE_VERIFIED', 'CLINICALLY_APPROVED', 'REJECTED')),
    ADD COLUMN IF NOT EXISTS clinical_review_status VARCHAR(30) NOT NULL DEFAULT 'NOT_REQUIRED'
        CHECK (clinical_review_status IN ('NOT_REQUIRED', 'PENDING', 'APPROVED', 'REJECTED')),
    ADD COLUMN IF NOT EXISTS reviewed_by VARCHAR(200),
    ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS citation_label TEXT,
    ADD COLUMN IF NOT EXISTS is_retrievable BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS supersedes_document_id UUID
        REFERENCES source_document(id) ON DELETE SET NULL;

ALTER TABLE source_document
    DROP CONSTRAINT IF EXISTS source_document_effective_dates_check;

ALTER TABLE source_document
    ADD CONSTRAINT source_document_effective_dates_check
        CHECK (effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from);

CREATE INDEX IF NOT EXISTS idx_source_document_retrieval_gate
    ON source_document (is_retrievable, review_status, effective_from, effective_to);

ALTER TABLE knowledge_chunk
    ADD COLUMN IF NOT EXISTS canonical_key VARCHAR(100),
    ADD COLUMN IF NOT EXISTS domain VARCHAR(60) NOT NULL DEFAULT 'GENERAL',
    ADD COLUMN IF NOT EXISTS route_scope TEXT[] NOT NULL DEFAULT ARRAY['SIMPLE_LOOKUP']::TEXT[],
    ADD COLUMN IF NOT EXISTS safety_level VARCHAR(20) NOT NULL DEFAULT 'LOW'
        CHECK (safety_level IN ('LOW', 'MODERATE', 'HIGH')),
    ADD COLUMN IF NOT EXISTS review_status VARCHAR(30) NOT NULL DEFAULT 'DRAFT'
        CHECK (review_status IN ('DRAFT', 'SOURCE_VERIFIED', 'CLINICALLY_APPROVED', 'REJECTED')),
    ADD COLUMN IF NOT EXISTS is_retrievable BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS valid_from DATE,
    ADD COLUMN IF NOT EXISTS valid_to DATE,
    ADD COLUMN IF NOT EXISTS keywords TEXT[] NOT NULL DEFAULT '{}'::TEXT[],
    ADD COLUMN IF NOT EXISTS search_text TEXT NOT NULL DEFAULT '';

ALTER TABLE knowledge_chunk
    DROP CONSTRAINT IF EXISTS knowledge_chunk_valid_dates_check;

ALTER TABLE knowledge_chunk
    ADD CONSTRAINT knowledge_chunk_valid_dates_check
        CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from);

CREATE UNIQUE INDEX IF NOT EXISTS uq_knowledge_chunk_canonical_version
    ON knowledge_chunk (source_document_id, chunk_version, canonical_key)
    WHERE canonical_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_knowledge_chunk_retrieval_gate
    ON knowledge_chunk (is_retrievable, review_status, domain, valid_from, valid_to);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunk_routes_gin
    ON knowledge_chunk USING GIN (route_scope);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunk_keywords_gin
    ON knowledge_chunk USING GIN (keywords);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunk_search_fts
    ON knowledge_chunk USING GIN (to_tsvector('simple', search_text));

COMMENT ON COLUMN knowledge_chunk.route_scope IS
    '이 청크를 사용할 수 있는 답변 경로. 예: SIMPLE_LOOKUP, DRUG_LOOKUP, COMPREHENSIVE_ANALYSIS';
COMMENT ON COLUMN knowledge_chunk.review_status IS
    '종합분석·선제케어에서는 CLINICALLY_APPROVED만 검색하도록 retrieval 함수가 제한한다';

