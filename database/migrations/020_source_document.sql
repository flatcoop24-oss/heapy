-- API 응답, 웹 문서, PDF, 내부 가이드 각각의 원문 단위를 관리합니다.
CREATE TABLE IF NOT EXISTS source_document (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id             BIGINT NOT NULL REFERENCES source_registry(id) ON DELETE RESTRICT,
    external_document_id  VARCHAR(300),
    title                 TEXT NOT NULL,
    document_type         VARCHAR(60) NOT NULL,
    source_url            TEXT,
    storage_path          TEXT,
    content_format        VARCHAR(30) NOT NULL
                              CHECK (content_format IN ('JSON', 'XML', 'HTML', 'PDF', 'HWP', 'HWPX', 'MARKDOWN', 'TEXT')),
    language_code         VARCHAR(10) NOT NULL DEFAULT 'ko',
    version_label         VARCHAR(100) NOT NULL DEFAULT '1',
    checksum_sha256       CHAR(64),
    raw_payload           JSONB,
    raw_content           TEXT,
    normalized_content    TEXT,
    ingestion_target      VARCHAR(30) NOT NULL
                              CHECK (ingestion_target IN ('VECTOR', 'RELATIONAL', 'BOTH', 'REFERENCE_ONLY')),
    processing_status     VARCHAR(30) NOT NULL DEFAULT 'COLLECTED'
                              CHECK (processing_status IN ('COLLECTED', 'NORMALIZED', 'CHUNKED', 'FAILED', 'EXCLUDED', 'OUTDATED')),
    published_at          TIMESTAMPTZ,
    fetched_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata              JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_source_document_version
    ON source_document (
        source_id,
        COALESCE(external_document_id, ''),
        version_label
    );

CREATE INDEX IF NOT EXISTS idx_source_document_source_status
    ON source_document (source_id, processing_status);

CREATE INDEX IF NOT EXISTS idx_source_document_metadata_gin
    ON source_document USING GIN (metadata);

COMMENT ON TABLE source_document IS '수집한 원문과 정규화 본문, 파일 위치, 버전 및 처리 상태';
COMMENT ON COLUMN source_document.storage_path IS 'storage/source_document 아래 원본 또는 정규화 파일의 상대 경로';
