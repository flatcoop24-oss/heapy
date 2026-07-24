-- Users 건강검진 기록의 정상판정 보호 계층입니다.
-- 숫자만으로 진단하지 않으며, 검증 상태·단위·성별·검사일 규칙 버전을
-- 모두 확인한 뒤 국가건강검진 결과 분류를 반환합니다.

ALTER TABLE screening_observation
    ADD COLUMN IF NOT EXISTS reported_interpretation_code VARCHAR(80),
    ADD COLUMN IF NOT EXISTS reported_interpretation_text TEXT;

ALTER TABLE screening_observation
    DROP CONSTRAINT IF EXISTS screening_observation_reported_code_format;

ALTER TABLE screening_observation
    ADD CONSTRAINT screening_observation_reported_code_format
        CHECK (
            reported_interpretation_code IS NULL
            OR reported_interpretation_code ~ '^[A-Z][A-Z0-9_]*$'
        );

ALTER TABLE screening_observation
    DROP CONSTRAINT IF EXISTS screening_observation_check,
    DROP CONSTRAINT IF EXISTS screening_observation_value_present_check;

ALTER TABLE screening_observation
    ADD CONSTRAINT screening_observation_value_present_check
        CHECK (
            value_numeric IS NOT NULL
            OR value_text IS NOT NULL
            OR reported_interpretation_code IS NOT NULL
        );

COMMENT ON COLUMN screening_observation.reported_interpretation_code IS
    '검진기관 결과지에 표시된 판정을 정규화한 코드. 계산 판정과 별도로 보존';
COMMENT ON COLUMN screening_observation.reported_interpretation_text IS
    '검진기관 결과지의 판정 원문. OCR/구조화 과정에서 덮어쓰지 않음';


CREATE OR REPLACE FUNCTION canonical_screening_unit(p_unit TEXT)
RETURNS TEXT
LANGUAGE SQL
IMMUTABLE
AS $$
    SELECT CASE
        WHEN p_unit IS NULL THEN NULL
        WHEN lower(regexp_replace(trim(p_unit), '\s+', '', 'g'))
            IN ('u/l', 'iu/l') THEN 'u/l'
        WHEN lower(regexp_replace(trim(p_unit), '\s+', '', 'g'))
            IN ('g/dl') THEN 'g/dl'
        WHEN lower(regexp_replace(trim(p_unit), '\s+', '', 'g'))
            IN ('mg/dl', '㎎/dl', 'mg/㎗') THEN 'mg/dl'
        WHEN replace(
            lower(regexp_replace(trim(p_unit), '\s+', '', 'g')),
            '㎡',
            'm2'
        ) = 'ml/min/1.73m2' THEN 'ml/min/1.73m2'
        ELSE lower(regexp_replace(trim(p_unit), '\s+', '', 'g'))
    END;
$$;

COMMENT ON FUNCTION canonical_screening_unit IS
    '판정 전 단위 동일성 확인용 최소 정규화. 단위 환산은 수행하지 않음';


CREATE OR REPLACE FUNCTION canonical_screening_code(
    p_item_code VARCHAR,
    p_value TEXT
)
RETURNS TEXT
LANGUAGE SQL
IMMUTABLE
AS $$
    SELECT CASE
        WHEN p_value IS NULL THEN NULL
        WHEN p_item_code = 'URINE_PROTEIN' THEN
            CASE lower(regexp_replace(trim(p_value), '\s+', '', 'g'))
                WHEN 'negative' THEN 'NEGATIVE'
                WHEN 'neg' THEN 'NEGATIVE'
                WHEN '음성' THEN 'NEGATIVE'
                WHEN '-' THEN 'NEGATIVE'
                WHEN 'trace' THEN 'TRACE'
                WHEN '약양성' THEN 'TRACE'
                WHEN '±' THEN 'TRACE'
                WHEN '+-' THEN 'TRACE'
                WHEN 'positive_1' THEN 'POSITIVE_1'
                WHEN 'positive1' THEN 'POSITIVE_1'
                WHEN '1+' THEN 'POSITIVE_1'
                WHEN '+1' THEN 'POSITIVE_1'
                WHEN '+' THEN 'POSITIVE_1'
                WHEN '양성' THEN 'POSITIVE_1'
                WHEN 'positive_2' THEN 'POSITIVE_2'
                WHEN 'positive2' THEN 'POSITIVE_2'
                WHEN '2+' THEN 'POSITIVE_2'
                WHEN '+2' THEN 'POSITIVE_2'
                WHEN 'positive_3' THEN 'POSITIVE_3'
                WHEN 'positive3' THEN 'POSITIVE_3'
                WHEN '3+' THEN 'POSITIVE_3'
                WHEN '+3' THEN 'POSITIVE_3'
                WHEN 'positive_4' THEN 'POSITIVE_4'
                WHEN 'positive4' THEN 'POSITIVE_4'
                WHEN '4+' THEN 'POSITIVE_4'
                WHEN '+4' THEN 'POSITIVE_4'
                ELSE upper(trim(p_value))
            END
        ELSE upper(trim(p_value))
    END;
$$;

COMMENT ON FUNCTION canonical_screening_code IS
    '요단백 결과지 표현을 판정 규칙 코드로 정규화';


CREATE OR REPLACE FUNCTION classify_user_screening_observation(
    p_observation_id UUID
)
RETURNS TABLE (
    observation_id UUID,
    item_code VARCHAR,
    classification_status VARCHAR,
    normality VARCHAR,
    is_normal_a BOOLEAN,
    decision_state VARCHAR,
    requires_review BOOLEAN,
    reason_code VARCHAR,
    classification_basis VARCHAR,
    normalized_value TEXT,
    reported_interpretation_code VARCHAR,
    source_computed_mismatch BOOLEAN,
    rule_set_code VARCHAR,
    rule_source_document_id UUID,
    source_locator VARCHAR
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_observation screening_observation%ROWTYPE;
    v_report screening_report%ROWTYPE;
    v_item screening_item%ROWTYPE;
    v_profile lab_item_profile%ROWTYPE;
    v_classification RECORD;
    v_input_text TEXT;
    v_requires_sex BOOLEAN := FALSE;
    v_reported_code VARCHAR;
BEGIN
    observation_id := p_observation_id;
    classification_status := 'UNCLASSIFIED';
    normality := 'UNCLASSIFIED';
    is_normal_a := NULL;
    decision_state := 'REVIEW_REQUIRED';
    requires_review := TRUE;
    classification_basis := 'NONE';
    normalized_value := NULL;
    source_computed_mismatch := FALSE;

    SELECT *
    INTO v_observation
    FROM screening_observation
    WHERE id = p_observation_id;

    IF NOT FOUND THEN
        reason_code := 'OBSERVATION_NOT_FOUND';
        RETURN NEXT;
        RETURN;
    END IF;

    item_code := v_observation.item_code;
    v_reported_code := v_observation.reported_interpretation_code;
    reported_interpretation_code := v_reported_code;

    SELECT * INTO v_report
    FROM screening_report
    WHERE id = v_observation.report_id;

    SELECT * INTO v_item
    FROM screening_item
    WHERE screening_item.item_code = v_observation.item_code;

    SELECT * INTO v_profile
    FROM lab_item_profile
    WHERE lab_item_profile.item_code = v_observation.item_code;

    IF v_observation.item_code IS NULL
       OR v_item.item_code IS NULL
       OR v_profile.item_code IS NULL THEN
        reason_code := 'ITEM_UNMAPPED';
        RETURN NEXT;
        RETURN;
    END IF;

    IF v_report.verification_status NOT IN ('AUTO_VALIDATED', 'USER_CONFIRMED')
       OR v_observation.verification_status
            NOT IN ('AUTO_VALIDATED', 'USER_CONFIRMED') THEN
        reason_code := 'UNVERIFIED_RESULT';
        RETURN NEXT;
        RETURN;
    END IF;

    IF v_observation.verification_status <> 'USER_CONFIRMED'
       AND v_observation.extraction_confidence IS NOT NULL
       AND v_observation.extraction_confidence < 0.95 THEN
        reason_code := 'LOW_EXTRACTION_CONFIDENCE';
        RETURN NEXT;
        RETURN;
    END IF;

    IF v_profile.interpretation_mode = 'SOURCE_REPORTED_COMPOSITE' THEN
        classification_basis := 'SOURCE_REPORTED';
        IF v_reported_code = 'HEPATITIS_B_CARRIER_SUSPECTED' THEN
            classification_status := 'DISEASE_SUSPECTED';
            normality := 'SUSPECTED';
            is_normal_a := FALSE;
            decision_state := 'CLASSIFIED';
            requires_review := FALSE;
            reason_code := 'SOURCE_COMPOSITE_SUSPECTED';
        ELSIF v_reported_code IN (
            'HEPATITIS_B_ANTIBODY_PRESENT',
            'HEPATITIS_B_ANTIBODY_ABSENT'
        ) THEN
            classification_status := 'SOURCE_REPORTED';
            normality := 'SOURCE_REPORTED';
            decision_state := 'SOURCE_RECORDED';
            requires_review := FALSE;
            reason_code := 'SOURCE_COMPOSITE_RECORDED';
        ELSE
            reason_code := CASE
                WHEN v_reported_code IS NULL THEN 'SOURCE_RESULT_REQUIRED'
                ELSE 'SOURCE_COMPOSITE_PENDING'
            END;
        END IF;
        RETURN NEXT;
        RETURN;
    END IF;

    IF v_profile.interpretation_mode = 'SOURCE_REPORTED' THEN
        classification_basis := 'SOURCE_REPORTED';
        IF v_observation.item_code = 'HEPATITIS_C_ANTIBODY'
           AND v_reported_code = 'HEPATITIS_C_ANTIBODY_ABSENT' THEN
            classification_status := 'NORMAL_A';
            normality := 'NORMAL';
            is_normal_a := TRUE;
            decision_state := 'CLASSIFIED';
            requires_review := FALSE;
            reason_code := 'SOURCE_RESULT_CLASSIFIED';
        ELSIF v_observation.item_code = 'HEPATITIS_C_ANTIBODY'
           AND v_reported_code = 'HEPATITIS_C_ANTIBODY_PRESENT' THEN
            classification_status := 'DISEASE_SUSPECTED';
            normality := 'SUSPECTED';
            is_normal_a := FALSE;
            decision_state := 'CLASSIFIED';
            requires_review := FALSE;
            reason_code := 'SOURCE_RESULT_CLASSIFIED';
        ELSE
            reason_code := CASE
                WHEN v_reported_code IS NULL THEN 'SOURCE_RESULT_REQUIRED'
                ELSE 'SOURCE_RESULT_INDETERMINATE'
            END;
        END IF;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM screening_rule_set rs
        JOIN screening_rule sr ON sr.rule_set_id = rs.id
        WHERE sr.item_code = v_observation.item_code
          AND sr.sex_scope IN ('MALE', 'FEMALE')
          AND rs.is_active = TRUE
          AND v_report.screened_on >= rs.effective_from
          AND (
              rs.effective_to IS NULL
              OR v_report.screened_on <= rs.effective_to
          )
    )
    INTO v_requires_sex;

    IF v_requires_sex
       AND v_report.sex_for_clinical_use NOT IN ('MALE', 'FEMALE') THEN
        reason_code := 'SEX_FOR_CLINICAL_USE_REQUIRED';
        RETURN NEXT;
        RETURN;
    END IF;

    IF v_item.measurement_type = 'NUMERIC' THEN
        IF v_observation.value_numeric IS NULL THEN
            reason_code := 'NUMERIC_VALUE_REQUIRED';
            RETURN NEXT;
            RETURN;
        END IF;
        IF canonical_screening_unit(
            COALESCE(v_observation.normalized_unit, v_observation.raw_unit)
        ) IS NULL THEN
            reason_code := 'UNIT_REQUIRED';
            RETURN NEXT;
            RETURN;
        END IF;
        IF canonical_screening_unit(
            COALESCE(v_observation.normalized_unit, v_observation.raw_unit)
        ) <> canonical_screening_unit(v_item.canonical_unit) THEN
            reason_code := 'UNIT_MISMATCH';
            RETURN NEXT;
            RETURN;
        END IF;
        normalized_value := v_observation.value_numeric::TEXT;
    ELSE
        v_input_text := canonical_screening_code(
            v_observation.item_code,
            v_observation.value_text
        );
        IF v_input_text IS NULL THEN
            reason_code := 'CODE_VALUE_UNRECOGNIZED';
            RETURN NEXT;
            RETURN;
        END IF;
        normalized_value := v_input_text;
    END IF;

    SELECT *
    INTO v_classification
    FROM classify_screening_value(
        v_observation.item_code,
        v_observation.value_numeric,
        v_input_text,
        v_report.sex_for_clinical_use,
        v_report.screened_on
    );

    IF NOT FOUND THEN
        reason_code := 'OUTSIDE_DEFINED_OFFICIAL_RANGE';
        RETURN NEXT;
        RETURN;
    END IF;

    IF v_classification.result_status IS NULL THEN
        reason_code := 'OUTSIDE_DEFINED_OFFICIAL_RANGE';
        RETURN NEXT;
        RETURN;
    END IF;

    rule_set_code := v_classification.rule_set_code;
    rule_source_document_id := v_classification.source_document_id;
    source_locator := v_classification.source_locator;
    classification_basis := 'OFFICIAL_RULE';

    IF v_reported_code IN (
        'NORMAL_A',
        'NORMAL_B',
        'DISEASE_SUSPECTED'
    ) AND v_reported_code <> v_classification.result_status THEN
        reason_code := 'SOURCE_COMPUTED_MISMATCH';
        source_computed_mismatch := TRUE;
        RETURN NEXT;
        RETURN;
    END IF;

    classification_status := v_classification.result_status;
    normality := CASE v_classification.result_status
        WHEN 'NORMAL_A' THEN 'NORMAL'
        WHEN 'NORMAL_B' THEN 'BORDERLINE'
        WHEN 'DISEASE_SUSPECTED' THEN 'SUSPECTED'
        ELSE 'UNCLASSIFIED'
    END;
    is_normal_a := v_classification.result_status = 'NORMAL_A';
    decision_state := 'CLASSIFIED';
    requires_review := FALSE;
    reason_code := 'OFFICIAL_RULE_MATCH';
    RETURN NEXT;
END;
$$;

COMMENT ON FUNCTION classify_user_screening_observation IS
    '검증된 Users 건강검진 관찰값을 공식 검진 분류로 변환. 진단 함수가 아님';


CREATE OR REPLACE VIEW user_screening_record_classification AS
SELECT
    r.user_id,
    r.screened_on,
    r.provider_name,
    r.source_method,
    r.verification_status AS report_verification_status,
    o.verification_status AS observation_verification_status,
    o.value_numeric,
    o.value_text,
    COALESCE(o.normalized_unit, o.raw_unit) AS recorded_unit,
    c.*
FROM screening_report r
JOIN screening_observation o ON o.report_id = r.id
CROSS JOIN LATERAL classify_user_screening_observation(o.id) c;

COMMENT ON VIEW user_screening_record_classification IS
    'Users 검진 기록별 정상A·정상B·질환의심·판정불가와 품질 사유를 함께 제공';
