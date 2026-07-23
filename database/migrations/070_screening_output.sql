-- 사용자 검진 원자료는 지식 VDB와 분리해 저장합니다.
-- 이 테이블의 개인 데이터는 knowledge_chunk로 임베딩하지 않습니다.
CREATE TABLE IF NOT EXISTS screening_report (
    id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                   UUID NOT NULL,
    screened_on               DATE NOT NULL,
    provider_name             VARCHAR(200),
    source_method             VARCHAR(30) NOT NULL
                                  CHECK (source_method IN (
                                      'FHIR_API', 'PROVIDER_API', 'STRUCTURED_FILE',
                                      'PDF_TEXT', 'OCR', 'MANUAL'
                                  )),
    source_checksum_sha256    CHAR(64),
    parser_version            VARCHAR(100),
    subject_sex               VARCHAR(10) NOT NULL DEFAULT 'UNKNOWN'
                                  CHECK (subject_sex IN ('MALE', 'FEMALE', 'UNKNOWN')),
    verification_status       VARCHAR(30) NOT NULL DEFAULT 'UNVERIFIED'
                                  CHECK (verification_status IN (
                                      'UNVERIFIED', 'AUTO_VALIDATED',
                                      'USER_CONFIRMED', 'REVIEW_REQUIRED'
                                  )),
    verified_by_user_at       TIMESTAMPTZ,
    metadata                  JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_screening_report_user_date
    ON screening_report (user_id, screened_on DESC);

CREATE TABLE IF NOT EXISTS screening_observation (
    id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id                 UUID NOT NULL REFERENCES screening_report(id) ON DELETE CASCADE,
    item_code                 VARCHAR(80) REFERENCES screening_item(item_code) ON DELETE RESTRICT,
    raw_item_name             VARCHAR(300) NOT NULL,
    value_numeric             NUMERIC,
    value_text                TEXT,
    raw_unit                  VARCHAR(80),
    normalized_unit           VARCHAR(40),
    reference_low             NUMERIC,
    reference_high            NUMERIC,
    reference_text            TEXT,
    extraction_confidence     NUMERIC(5,4)
                                  CHECK (
                                      extraction_confidence IS NULL
                                      OR extraction_confidence BETWEEN 0 AND 1
                                  ),
    verification_status       VARCHAR(30) NOT NULL DEFAULT 'UNVERIFIED'
                                  CHECK (verification_status IN (
                                      'UNVERIFIED', 'AUTO_VALIDATED',
                                      'USER_CONFIRMED', 'REVIEW_REQUIRED'
                                  )),
    observed_at               TIMESTAMPTZ,
    raw_payload               JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (value_numeric IS NOT NULL OR value_text IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_screening_observation_report
    ON screening_observation (report_id, item_code);

CREATE INDEX IF NOT EXISTS idx_screening_observation_item
    ON screening_observation (item_code, observed_at DESC);

-- 정규화된 항목 키는 벡터 유사도 검색보다 직접 조회가 정확합니다.
CREATE OR REPLACE FUNCTION get_knowledge_by_key(
    p_canonical_key VARCHAR,
    p_route VARCHAR DEFAULT 'SIMPLE_LOOKUP'
)
RETURNS TABLE (
    chunk_id UUID,
    heading TEXT,
    content TEXT,
    safety_level VARCHAR,
    evidence JSONB,
    citation_label TEXT
)
LANGUAGE SQL
STABLE
AS $$
    SELECT
        kc.id,
        kc.heading,
        kc.content,
        kc.safety_level,
        COALESCE(kc.metadata -> 'evidence', '[]'::JSONB),
        sd.citation_label
    FROM knowledge_chunk kc
    JOIN source_document sd ON sd.id = kc.source_document_id
    JOIN source_registry sr ON sr.id = sd.source_id
    WHERE kc.canonical_key = p_canonical_key
      AND UPPER(p_route) = ANY(kc.route_scope)
      AND kc.is_retrievable = TRUE
      AND sd.is_retrievable = TRUE
      AND sr.is_active = TRUE
      AND sr.license_status = 'APPROVED'
      AND (kc.valid_from IS NULL OR CURRENT_DATE >= kc.valid_from)
      AND (kc.valid_to IS NULL OR CURRENT_DATE <= kc.valid_to)
      AND (sd.effective_from IS NULL OR CURRENT_DATE >= sd.effective_from)
      AND (sd.effective_to IS NULL OR CURRENT_DATE <= sd.effective_to)
      AND (
          (
              UPPER(p_route) IN ('COMPREHENSIVE_ANALYSIS', 'PROACTIVE_CARE')
              AND kc.review_status = 'CLINICALLY_APPROVED'
              AND sd.clinical_review_status = 'APPROVED'
          )
          OR (
              UPPER(p_route) NOT IN ('COMPREHENSIVE_ANALYSIS', 'PROACTIVE_CARE')
              AND kc.review_status IN ('SOURCE_VERIFIED', 'CLINICALLY_APPROVED')
          )
      )
    ORDER BY kc.chunk_version DESC
    LIMIT 1;
$$;

-- 프론트엔드/LLM에 전달할 MVP 출력입니다.
-- 확정 진단·원인 추론·치료 제안은 포함하지 않습니다.
CREATE OR REPLACE FUNCTION build_screening_report_output(p_report_id UUID)
RETURNS JSONB
LANGUAGE SQL
STABLE
AS $$
    WITH report AS (
        SELECT * FROM screening_report WHERE id = p_report_id
    ),
    interpreted AS (
        SELECT
            o.id,
            o.raw_item_name,
            o.item_code,
            i.display_name_ko,
            i.domain,
            i.combination_group,
            i.knowledge_key,
            o.value_numeric,
            o.value_text,
            COALESCE(o.normalized_unit, o.raw_unit, i.canonical_unit) AS unit,
            o.reference_low,
            o.reference_high,
            o.reference_text,
            o.extraction_confidence,
            o.verification_status,
            c.result_status,
            c.rule_set_code,
            c.source_document_id AS rule_source_document_id,
            c.source_locator,
            k.heading AS knowledge_heading,
            k.content AS explanation,
            k.safety_level,
            k.evidence,
            k.citation_label,
            CASE
                WHEN o.item_code IS NULL THEN TRUE
                WHEN c.result_status IS NULL THEN TRUE
                WHEN o.verification_status IN ('UNVERIFIED', 'REVIEW_REQUIRED') THEN TRUE
                WHEN o.extraction_confidence IS NOT NULL AND o.extraction_confidence < 0.95 THEN TRUE
                ELSE FALSE
            END AS requires_confirmation,
            CASE COALESCE(c.result_status, 'UNCLASSIFIED')
                WHEN 'DISEASE_SUSPECTED' THEN 3
                WHEN 'NORMAL_B' THEN 2
                WHEN 'NORMAL_A' THEN 1
                ELSE 0
            END AS severity_rank
        FROM report r
        JOIN screening_observation o ON o.report_id = r.id
        LEFT JOIN screening_item i ON i.item_code = o.item_code
        LEFT JOIN LATERAL classify_screening_value(
            o.item_code,
            o.value_numeric,
            o.value_text,
            r.subject_sex,
            r.screened_on
        ) c ON TRUE
        LEFT JOIN LATERAL get_knowledge_by_key(i.knowledge_key, 'SIMPLE_LOOKUP') k ON TRUE
    ),
    summary AS (
        SELECT
            COUNT(*) AS item_count,
            COUNT(*) FILTER (WHERE requires_confirmation) AS confirmation_count,
            COUNT(*) FILTER (WHERE result_status = 'DISEASE_SUSPECTED') AS suspected_count,
            COUNT(*) FILTER (WHERE result_status = 'NORMAL_B') AS borderline_count,
            MAX(severity_rank) AS max_severity
        FROM interpreted
    ),
    items AS (
        SELECT COALESCE(
            jsonb_agg(
                jsonb_build_object(
                    'observation_id', id,
                    'item_code', item_code,
                    'raw_item_name', raw_item_name,
                    'display_name', display_name_ko,
                    'domain', domain,
                    'combination_group', combination_group,
                    'value', CASE
                        WHEN value_numeric IS NOT NULL THEN to_jsonb(value_numeric)
                        ELSE to_jsonb(value_text)
                    END,
                    'unit', unit,
                    'source_reference_range', jsonb_build_object(
                        'low', reference_low,
                        'high', reference_high,
                        'text', reference_text
                    ),
                    'result_status', COALESCE(result_status, 'UNCLASSIFIED'),
                    'rule', jsonb_build_object(
                        'rule_set_code', rule_set_code,
                        'source_document_id', rule_source_document_id,
                        'source_locator', source_locator
                    ),
                    'knowledge', jsonb_build_object(
                        'canonical_key', knowledge_key,
                        'heading', knowledge_heading,
                        'explanation', explanation,
                        'safety_level', safety_level,
                        'evidence', COALESCE(evidence, '[]'::JSONB),
                        'citation_label', citation_label
                    ),
                    'quality', jsonb_build_object(
                        'verification_status', verification_status,
                        'extraction_confidence', extraction_confidence,
                        'requires_confirmation', requires_confirmation
                    )
                ) ORDER BY severity_rank DESC, display_name_ko NULLS LAST, raw_item_name
            ),
            '[]'::JSONB
        ) AS value
        FROM interpreted
    )
    SELECT jsonb_build_object(
        'report', jsonb_build_object(
            'report_id', r.id,
            'user_id', r.user_id,
            'screened_on', r.screened_on,
            'provider_name', r.provider_name,
            'source_method', r.source_method,
            'verification_status', r.verification_status,
            'parser_version', r.parser_version
        ),
        'summary', jsonb_build_object(
            'overall_status', CASE s.max_severity
                WHEN 3 THEN 'DISEASE_SUSPECTED'
                WHEN 2 THEN 'NORMAL_B'
                WHEN 1 THEN 'NORMAL_A'
                ELSE 'UNCLASSIFIED'
            END,
            'item_count', s.item_count,
            'suspected_count', s.suspected_count,
            'borderline_count', s.borderline_count,
            'confirmation_count', s.confirmation_count
        ),
        'items', items.value,
        'output_policy', jsonb_build_object(
            'simple_lookup', TRUE,
            'personal_hook', s.confirmation_count = 0,
            'comprehensive_analysis', FALSE,
            'proactive_care', FALSE,
            'reason', '종합분석과 선제케어는 임상검수 완료 규칙·청크가 필요합니다.'
        ),
        'disclaimer', '검진 판정과 교육용 설명이며 의료 진단이나 처방이 아닙니다.'
    )
    FROM report r
    CROSS JOIN summary s
    CROSS JOIN items;
$$;

COMMENT ON FUNCTION build_screening_report_output IS
    '검진 원값, 판정, 쉬운 설명, 근거, 데이터 품질을 한 JSON으로 반환하는 MVP 출력 함수';

-- 동일 사용자·동일 항목의 검증된 값만 시계열로 반환합니다.
CREATE OR REPLACE FUNCTION get_screening_trend(
    p_user_id UUID,
    p_item_code VARCHAR,
    p_limit INTEGER DEFAULT 10
)
RETURNS TABLE (
    screened_on DATE,
    value_numeric NUMERIC,
    value_text TEXT,
    unit VARCHAR,
    result_status VARCHAR,
    verification_status VARCHAR,
    report_id UUID
)
LANGUAGE SQL
STABLE
AS $$
    SELECT
        r.screened_on,
        o.value_numeric,
        o.value_text,
        COALESCE(o.normalized_unit, o.raw_unit, i.canonical_unit),
        c.result_status,
        o.verification_status,
        r.id
    FROM screening_report r
    JOIN screening_observation o ON o.report_id = r.id
    JOIN screening_item i ON i.item_code = o.item_code
    LEFT JOIN LATERAL classify_screening_value(
        o.item_code,
        o.value_numeric,
        o.value_text,
        r.subject_sex,
        r.screened_on
    ) c ON TRUE
    WHERE r.user_id = p_user_id
      AND o.item_code = p_item_code
      AND r.verification_status IN ('AUTO_VALIDATED', 'USER_CONFIRMED')
      AND o.verification_status IN ('AUTO_VALIDATED', 'USER_CONFIRMED')
    ORDER BY r.screened_on DESC, o.observed_at DESC NULLS LAST
    LIMIT GREATEST(1, LEAST(p_limit, 100));
$$;
