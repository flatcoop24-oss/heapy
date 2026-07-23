-- 어떤 기관의 자료를 어떤 조건으로 수집할 수 있는지 관리합니다.
CREATE TABLE IF NOT EXISTS source_registry (
    id                      BIGSERIAL PRIMARY KEY,
    source_code             VARCHAR(60) NOT NULL UNIQUE,
    source_name             VARCHAR(200) NOT NULL,
    provider_name           VARCHAR(200) NOT NULL,
    source_kind             VARCHAR(30) NOT NULL
                                CHECK (source_kind IN ('API', 'WEB', 'PDF', 'DOCUMENT', 'INTERNAL')),
    base_url                TEXT,
    ingestion_target        VARCHAR(30) NOT NULL
                                CHECK (ingestion_target IN ('VECTOR', 'RELATIONAL', 'BOTH', 'REFERENCE_ONLY')),
    license_status          VARCHAR(30) NOT NULL DEFAULT 'PENDING'
                                CHECK (license_status IN ('APPROVED', 'PENDING', 'RESTRICTED', 'REJECTED')),
    license_name            VARCHAR(200),
    license_url             TEXT,
    commercial_use_allowed  BOOLEAN,
    modification_allowed    BOOLEAN,
    attribution_required    BOOLEAN NOT NULL DEFAULT TRUE,
    refresh_cycle           VARCHAR(50),
    is_active               BOOLEAN NOT NULL DEFAULT FALSE,
    notes                   TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT source_registry_active_license_check
        CHECK (NOT is_active OR license_status = 'APPROVED')
);

COMMENT ON TABLE source_registry IS '출처, 라이선스, 수집 목적과 활성화 여부를 관리하는 출처 원장';
COMMENT ON COLUMN source_registry.ingestion_target IS 'VECTOR=VDB, RELATIONAL=규칙/코드 DB, BOTH=양쪽, REFERENCE_ONLY=참조만';
