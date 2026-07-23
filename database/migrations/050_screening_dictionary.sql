-- 검사명 매핑과 수치 판정은 VDB가 아니라 관계형 규칙 DB가 담당합니다.
CREATE TABLE IF NOT EXISTS screening_item (
    item_code          VARCHAR(80) PRIMARY KEY,
    display_name_ko    VARCHAR(200) NOT NULL,
    display_name_en    VARCHAR(200),
    domain             VARCHAR(60) NOT NULL,
    measurement_type   VARCHAR(20) NOT NULL
                           CHECK (measurement_type IN ('NUMERIC', 'CODE', 'TEXT')),
    canonical_unit     VARCHAR(40),
    combination_group  VARCHAR(80),
    knowledge_key      VARCHAR(100),
    is_active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS screening_item_alias (
    alias_normalized   VARCHAR(200) PRIMARY KEY,
    item_code          VARCHAR(80) NOT NULL REFERENCES screening_item(item_code) ON DELETE CASCADE,
    alias_display      VARCHAR(200) NOT NULL,
    source_type        VARCHAR(30) NOT NULL DEFAULT 'INTERNAL'
                           CHECK (source_type IN ('NHIS', 'LOINC', 'DOCUMENT', 'INTERNAL')),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_screening_item_alias_item
    ON screening_item_alias (item_code);

CREATE TABLE IF NOT EXISTS screening_rule_set (
    id                  BIGSERIAL PRIMARY KEY,
    rule_set_code       VARCHAR(100) NOT NULL UNIQUE,
    source_document_id  UUID REFERENCES source_document(id) ON DELETE RESTRICT,
    version_label       VARCHAR(100) NOT NULL,
    effective_from      DATE NOT NULL,
    effective_to        DATE,
    is_active           BOOLEAN NOT NULL DEFAULT FALSE,
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE TABLE IF NOT EXISTS screening_rule (
    id                    BIGSERIAL PRIMARY KEY,
    rule_set_id           BIGINT NOT NULL REFERENCES screening_rule_set(id) ON DELETE CASCADE,
    item_code             VARCHAR(80) NOT NULL REFERENCES screening_item(item_code) ON DELETE RESTRICT,
    sex_scope             VARCHAR(10) NOT NULL DEFAULT 'ANY'
                              CHECK (sex_scope IN ('ANY', 'MALE', 'FEMALE')),
    result_status         VARCHAR(30) NOT NULL
                              CHECK (result_status IN ('NORMAL_A', 'NORMAL_B', 'DISEASE_SUSPECTED')),
    lower_value           NUMERIC,
    lower_inclusive       BOOLEAN NOT NULL DEFAULT TRUE,
    upper_value           NUMERIC,
    upper_inclusive       BOOLEAN NOT NULL DEFAULT TRUE,
    expected_text         VARCHAR(80),
    priority              SMALLINT NOT NULL DEFAULT 10,
    source_locator        VARCHAR(200),
    notes                 TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (lower_value IS NULL OR upper_value IS NULL OR lower_value <= upper_value),
    CHECK (
        expected_text IS NOT NULL
        OR lower_value IS NOT NULL
        OR upper_value IS NOT NULL
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_screening_rule_definition
    ON screening_rule (
        rule_set_id,
        item_code,
        sex_scope,
        result_status,
        COALESCE(lower_value, -999999999),
        COALESCE(upper_value, 999999999),
        COALESCE(expected_text, '')
    );

CREATE INDEX IF NOT EXISTS idx_screening_rule_lookup
    ON screening_rule (rule_set_id, item_code, sex_scope, priority DESC);

-- 검사일에 유효한 규칙을 선택합니다. 범위 밖 고값/저값이 원문에 정의되지 않은 경우
-- 임의로 추정하지 않고 결과를 반환하지 않습니다.
CREATE OR REPLACE FUNCTION classify_screening_value(
    p_item_code VARCHAR,
    p_numeric_value NUMERIC DEFAULT NULL,
    p_text_value TEXT DEFAULT NULL,
    p_sex VARCHAR DEFAULT 'ANY',
    p_observed_on DATE DEFAULT CURRENT_DATE
)
RETURNS TABLE (
    result_status VARCHAR,
    rule_set_code VARCHAR,
    source_document_id UUID,
    source_locator VARCHAR
)
LANGUAGE SQL
STABLE
AS $$
    SELECT
        r.result_status,
        rs.rule_set_code,
        rs.source_document_id,
        r.source_locator
    FROM screening_rule_set rs
    JOIN screening_rule r ON r.rule_set_id = rs.id
    WHERE rs.is_active = TRUE
      AND p_observed_on >= rs.effective_from
      AND (rs.effective_to IS NULL OR p_observed_on <= rs.effective_to)
      AND r.item_code = p_item_code
      AND r.sex_scope IN ('ANY', UPPER(p_sex))
      AND (
          (
              p_numeric_value IS NOT NULL
              AND r.expected_text IS NULL
              AND (
                  r.lower_value IS NULL
                  OR (r.lower_inclusive AND p_numeric_value >= r.lower_value)
                  OR (NOT r.lower_inclusive AND p_numeric_value > r.lower_value)
              )
              AND (
                  r.upper_value IS NULL
                  OR (r.upper_inclusive AND p_numeric_value <= r.upper_value)
                  OR (NOT r.upper_inclusive AND p_numeric_value < r.upper_value)
              )
          )
          OR (
              p_text_value IS NOT NULL
              AND r.expected_text IS NOT NULL
              AND regexp_replace(upper(trim(p_text_value)), '\\s+', '', 'g') =
                  regexp_replace(upper(trim(r.expected_text)), '\\s+', '', 'g')
          )
      )
    ORDER BY
        CASE WHEN r.sex_scope = UPPER(p_sex) THEN 0 ELSE 1 END,
        r.priority DESC
    LIMIT 1;
$$;

COMMENT ON FUNCTION classify_screening_value IS
    '검사일·성별·단위를 정규화한 뒤 현행 판정규칙으로 상태를 반환. 진단 함수가 아님';
