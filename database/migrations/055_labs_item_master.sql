-- Labs Item Master는 항목 정체성과 판정 규칙을 분리합니다.
-- normal_range_a 같은 문자열 칼럼은 표시용으로만 생성하고 판정에는 사용하지 않습니다.
ALTER TABLE screening_item
    DROP CONSTRAINT IF EXISTS screening_item_measurement_type_check;

ALTER TABLE screening_item
    ADD CONSTRAINT screening_item_measurement_type_check
        CHECK (
            measurement_type IN (
                'NUMERIC',
                'CODE',
                'TEXT',
                'NUMERIC_OR_CODE'
            )
        );

CREATE TABLE IF NOT EXISTS lab_item_profile (
    item_code               VARCHAR(80) PRIMARY KEY
                                REFERENCES screening_item(item_code)
                                ON DELETE CASCADE,
    display_order           SMALLINT NOT NULL UNIQUE
                                CHECK (display_order > 0),
    specimen_type           VARCHAR(30) NOT NULL
                                CHECK (
                                    specimen_type IN (
                                        'WHOLE_BLOOD',
                                        'SERUM',
                                        'SERUM_OR_PLASMA',
                                        'URINE',
                                        'DERIVED'
                                    )
                                ),
    result_representation   VARCHAR(30) NOT NULL
                                CHECK (
                                    result_representation IN (
                                        'NUMERIC',
                                        'CODE',
                                        'NUMERIC_OR_CODE'
                                    )
                                ),
    is_derived              BOOLEAN NOT NULL DEFAULT FALSE,
    derivation_mode         VARCHAR(20) NOT NULL DEFAULT 'NONE'
                                CHECK (
                                    derivation_mode IN (
                                        'NONE',
                                        'CONDITIONAL',
                                        'ALWAYS'
                                    )
                                ),
    derivation_requires_sex BOOLEAN NOT NULL DEFAULT FALSE,
    interpretation_mode     VARCHAR(40) NOT NULL
                                CHECK (
                                    interpretation_mode IN (
                                        'RULE_ENGINE',
                                        'SOURCE_REPORTED',
                                        'SOURCE_REPORTED_COMPOSITE'
                                    )
                                ),
    allowed_values          JSONB NOT NULL DEFAULT '[]'::JSONB,
    eligibility             JSONB NOT NULL DEFAULT '{}'::JSONB,
    categories              JSONB NOT NULL DEFAULT '[]'::JSONB,
    source_document_id      UUID NOT NULL
                                REFERENCES source_document(id)
                                ON DELETE RESTRICT,
    source_locator          VARCHAR(300) NOT NULL,
    notes                   TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (jsonb_typeof(allowed_values) = 'array'),
    CHECK (jsonb_typeof(eligibility) = 'object'),
    CHECK (jsonb_typeof(categories) = 'array'),
    CHECK (is_derived = (derivation_mode <> 'NONE')),
    CHECK (NOT derivation_requires_sex OR is_derived),
    CHECK (
        interpretation_mode <> 'RULE_ENGINE'
        OR result_representation IN ('NUMERIC', 'CODE')
    )
);

CREATE INDEX IF NOT EXISTS idx_lab_item_profile_categories
    ON lab_item_profile USING GIN (categories);

-- 현재 활성 규칙을 JSON 배열로 묶은 읽기 전용 마스터입니다.
-- 판정 실행은 classify_screening_value()가 담당합니다.
CREATE OR REPLACE VIEW labs_item_master AS
SELECT
    i.item_code,
    i.display_name_en,
    i.display_name_ko,
    i.domain,
    i.measurement_type,
    i.canonical_unit,
    p.display_order,
    p.specimen_type,
    p.result_representation,
    COALESCE(active_rules.classification_sex_specific, FALSE)
        AS classification_sex_specific,
    jsonb_path_exists(p.eligibility, '$.**.sex')
        AS eligibility_sex_specific,
    p.derivation_requires_sex,
    (
        COALESCE(active_rules.classification_sex_specific, FALSE)
        OR jsonb_path_exists(p.eligibility, '$.**.sex')
        OR p.derivation_requires_sex
    ) AS requires_sex_for_clinical_use,
    p.is_derived,
    p.derivation_mode,
    p.interpretation_mode,
    p.allowed_values,
    p.eligibility,
    p.categories,
    COALESCE(active_rules.rules, '[]'::JSONB) AS classification_rules,
    p.source_document_id,
    p.source_locator,
    p.notes,
    i.is_active
FROM screening_item i
JOIN lab_item_profile p ON p.item_code = i.item_code
LEFT JOIN LATERAL (
    SELECT jsonb_agg(
        jsonb_build_object(
            'rule_set_code', rs.rule_set_code,
            'effective_from', rs.effective_from,
            'effective_to', rs.effective_to,
            'sex_scope', r.sex_scope,
            'result_status', r.result_status,
            'lower_value', r.lower_value,
            'lower_inclusive', r.lower_inclusive,
            'upper_value', r.upper_value,
            'upper_inclusive', r.upper_inclusive,
            'expected_text', r.expected_text,
            'source_locator', r.source_locator,
            'notes', r.notes
        )
        ORDER BY
            rs.effective_from DESC,
            r.sex_scope,
            r.priority,
            r.lower_value NULLS FIRST,
            r.upper_value NULLS LAST
    ) AS rules,
    COALESCE(
        bool_or(r.sex_scope IN ('MALE', 'FEMALE')),
        FALSE
    ) AS classification_sex_specific
    FROM screening_rule_set rs
    JOIN screening_rule r ON r.rule_set_id = rs.id
    WHERE r.item_code = i.item_code
      AND rs.is_active = TRUE
      AND CURRENT_DATE >= rs.effective_from
      AND (rs.effective_to IS NULL OR CURRENT_DATE <= rs.effective_to)
) active_rules ON TRUE;

COMMENT ON TABLE lab_item_profile IS
    '국가건강검진 Labs 15종의 검체·표현형·대상조건·출처 메타데이터';
COMMENT ON VIEW labs_item_master IS
    'screening_item, lab_item_profile, 현행 screening_rule을 합친 Labs Item Master 읽기 모델';
COMMENT ON COLUMN lab_item_profile.interpretation_mode IS
    'RULE_ENGINE=정규화 규칙 판정, SOURCE_REPORTED*=검진기관 원문 판정 우선';
COMMENT ON COLUMN lab_item_profile.derivation_requires_sex IS
    '계산식 입력으로 sex_for_clinical_use가 필요한지 여부. 판정·대상조건 성별 의존성은 뷰에서 자동 산출';
