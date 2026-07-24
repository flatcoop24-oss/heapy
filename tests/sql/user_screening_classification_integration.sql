\set ON_ERROR_STOP on

BEGIN;

INSERT INTO screening_report (
    id,
    user_id,
    screened_on,
    provider_name,
    source_method,
    sex_for_clinical_use,
    verification_status,
    parser_version
) VALUES
    (
        '10000000-0000-0000-0000-000000000001',
        '20000000-0000-0000-0000-000000000001',
        DATE '2026-07-24',
        '합성검진기관',
        'MANUAL',
        'MALE',
        'USER_CONFIRMED',
        'integration-test-v1'
    ),
    (
        '10000000-0000-0000-0000-000000000002',
        '20000000-0000-0000-0000-000000000002',
        DATE '2026-07-24',
        '합성검진기관',
        'MANUAL',
        'UNKNOWN',
        'USER_CONFIRMED',
        'integration-test-v1'
    ),
    (
        '10000000-0000-0000-0000-000000000003',
        '20000000-0000-0000-0000-000000000003',
        DATE '2026-07-24',
        '합성검진기관',
        'OCR',
        'MALE',
        'AUTO_VALIDATED',
        'integration-test-v1'
    );

INSERT INTO screening_observation (
    id,
    report_id,
    item_code,
    raw_item_name,
    value_numeric,
    value_text,
    normalized_unit,
    extraction_confidence,
    verification_status,
    reported_interpretation_code
) VALUES
    (
        '30000000-0000-0000-0000-000000000001',
        '10000000-0000-0000-0000-000000000001',
        'HEMOGLOBIN', '혈색소', 13.0, NULL, 'g/dL', NULL,
        'USER_CONFIRMED', NULL
    ),
    (
        '30000000-0000-0000-0000-000000000002',
        '10000000-0000-0000-0000-000000000001',
        'FASTING_GLUCOSE', '공복혈당', 99, NULL, 'mg/dL', NULL,
        'USER_CONFIRMED', NULL
    ),
    (
        '30000000-0000-0000-0000-000000000003',
        '10000000-0000-0000-0000-000000000001',
        'TOTAL_CHOLESTEROL', '총콜레스테롤', 199, NULL, 'mg/dL', NULL,
        'USER_CONFIRMED', NULL
    ),
    (
        '30000000-0000-0000-0000-000000000004',
        '10000000-0000-0000-0000-000000000001',
        'HDL_CHOLESTEROL', 'HDL 콜레스테롤', 60, NULL, 'mg/dL', NULL,
        'USER_CONFIRMED', NULL
    ),
    (
        '30000000-0000-0000-0000-000000000005',
        '10000000-0000-0000-0000-000000000001',
        'TRIGLYCERIDES', '중성지방', 149, NULL, 'mg/dL', NULL,
        'USER_CONFIRMED', NULL
    ),
    (
        '30000000-0000-0000-0000-000000000006',
        '10000000-0000-0000-0000-000000000001',
        'LDL_CHOLESTEROL', 'LDL 콜레스테롤', 129, NULL, 'mg/dL', NULL,
        'USER_CONFIRMED', NULL
    ),
    (
        '30000000-0000-0000-0000-000000000007',
        '10000000-0000-0000-0000-000000000001',
        'AST', 'AST', 40, NULL, 'IU/L', NULL,
        'USER_CONFIRMED', NULL
    ),
    (
        '30000000-0000-0000-0000-000000000008',
        '10000000-0000-0000-0000-000000000001',
        'ALT', 'ALT', 35, NULL, 'IU/L', NULL,
        'USER_CONFIRMED', NULL
    ),
    (
        '30000000-0000-0000-0000-000000000009',
        '10000000-0000-0000-0000-000000000001',
        'GAMMA_GTP', '감마지티피', 63, NULL, 'U/L', NULL,
        'USER_CONFIRMED', NULL
    ),
    (
        '30000000-0000-0000-0000-000000000010',
        '10000000-0000-0000-0000-000000000001',
        'SERUM_CREATININE', '혈청크레아티닌', 1.5, NULL, 'mg/dL', NULL,
        'USER_CONFIRMED', NULL
    ),
    (
        '30000000-0000-0000-0000-000000000011',
        '10000000-0000-0000-0000-000000000001',
        'EGFR', 'eGFR', 60, NULL, 'mL/min/1.73m2', NULL,
        'USER_CONFIRMED', NULL
    ),
    (
        '30000000-0000-0000-0000-000000000012',
        '10000000-0000-0000-0000-000000000001',
        'URINE_PROTEIN', '요단백', NULL, '음성', NULL, NULL,
        'USER_CONFIRMED', NULL
    ),
    (
        '30000000-0000-0000-0000-000000000013',
        '10000000-0000-0000-0000-000000000001',
        'HEPATITIS_B_SURFACE_ANTIGEN', 'B형간염 표면항원',
        NULL, NULL, NULL, NULL,
        'USER_CONFIRMED', 'HEPATITIS_B_ANTIBODY_PRESENT'
    ),
    (
        '30000000-0000-0000-0000-000000000014',
        '10000000-0000-0000-0000-000000000001',
        'HEPATITIS_B_SURFACE_ANTIBODY', 'B형간염 표면항체',
        NULL, NULL, NULL, NULL,
        'USER_CONFIRMED', 'HEPATITIS_B_ANTIBODY_PRESENT'
    ),
    (
        '30000000-0000-0000-0000-000000000015',
        '10000000-0000-0000-0000-000000000001',
        'HEPATITIS_C_ANTIBODY', 'C형간염 항체',
        NULL, NULL, NULL, NULL,
        'USER_CONFIRMED', 'HEPATITIS_C_ANTIBODY_ABSENT'
    ),
    (
        '40000000-0000-0000-0000-000000000001',
        '10000000-0000-0000-0000-000000000001',
        'FASTING_GLUCOSE', '공복혈당 경계', 100, NULL, 'mg/dL', NULL,
        'USER_CONFIRMED', NULL
    ),
    (
        '40000000-0000-0000-0000-000000000002',
        '10000000-0000-0000-0000-000000000001',
        'FASTING_GLUCOSE', '공복혈당 질환의심', 126, NULL, 'mg/dL', NULL,
        'USER_CONFIRMED', NULL
    ),
    (
        '40000000-0000-0000-0000-000000000003',
        '10000000-0000-0000-0000-000000000001',
        'FASTING_GLUCOSE', '공복혈당 단위오류', 5.5, NULL, 'mmol/L', NULL,
        'USER_CONFIRMED', NULL
    ),
    (
        '40000000-0000-0000-0000-000000000004',
        '10000000-0000-0000-0000-000000000001',
        'FASTING_GLUCOSE', '공복혈당 판정불일치', 99, NULL, 'mg/dL', NULL,
        'USER_CONFIRMED', 'NORMAL_B'
    ),
    (
        '40000000-0000-0000-0000-000000000005',
        '10000000-0000-0000-0000-000000000001',
        'HEMOGLOBIN', '혈색소 미정의 상한', 17.0, NULL, 'g/dL', NULL,
        'USER_CONFIRMED', NULL
    ),
    (
        '40000000-0000-0000-0000-000000000006',
        '10000000-0000-0000-0000-000000000002',
        'HEMOGLOBIN', '혈색소 성별 누락', 13.0, NULL, 'g/dL', NULL,
        'USER_CONFIRMED', NULL
    ),
    (
        '40000000-0000-0000-0000-000000000007',
        '10000000-0000-0000-0000-000000000003',
        'FASTING_GLUCOSE', '공복혈당 OCR 저신뢰도', 99, NULL, 'mg/dL', 0.9400,
        'AUTO_VALIDATED', NULL
    );

DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*)
    INTO v_count
    FROM user_screening_record_classification
    WHERE user_id = '20000000-0000-0000-0000-000000000001'
      AND observation_id::TEXT LIKE '30000000-%';

    IF v_count <> 15 THEN
        RAISE EXCEPTION 'expected 15 all-item rows, got %', v_count;
    END IF;

    SELECT COUNT(*)
    INTO v_count
    FROM user_screening_record_classification
    WHERE user_id = '20000000-0000-0000-0000-000000000001'
      AND observation_id::TEXT LIKE '30000000-%'
      AND classification_status = 'NORMAL_A';

    IF v_count <> 13 THEN
        RAISE EXCEPTION 'expected 13 NORMAL_A rows, got %', v_count;
    END IF;

    SELECT COUNT(*)
    INTO v_count
    FROM user_screening_record_classification
    WHERE user_id = '20000000-0000-0000-0000-000000000001'
      AND observation_id::TEXT LIKE '30000000-%'
      AND classification_status = 'SOURCE_REPORTED';

    IF v_count <> 2 THEN
        RAISE EXCEPTION 'expected 2 SOURCE_REPORTED rows, got %', v_count;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM user_screening_record_classification
        WHERE observation_id = '40000000-0000-0000-0000-000000000001'
          AND classification_status = 'NORMAL_B'
    ) THEN
        RAISE EXCEPTION 'glucose 100 boundary classification failed';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM user_screening_record_classification
        WHERE observation_id = '40000000-0000-0000-0000-000000000002'
          AND classification_status = 'DISEASE_SUSPECTED'
    ) THEN
        RAISE EXCEPTION 'glucose 126 suspected classification failed';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM user_screening_record_classification
        WHERE observation_id = '40000000-0000-0000-0000-000000000003'
          AND reason_code = 'UNIT_MISMATCH'
          AND requires_review = TRUE
    ) THEN
        RAISE EXCEPTION 'unit mismatch guard failed';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM user_screening_record_classification
        WHERE observation_id = '40000000-0000-0000-0000-000000000004'
          AND reason_code = 'SOURCE_COMPUTED_MISMATCH'
          AND requires_review = TRUE
    ) THEN
        RAISE EXCEPTION 'source/computed mismatch guard failed';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM user_screening_record_classification
        WHERE observation_id = '40000000-0000-0000-0000-000000000005'
          AND reason_code = 'OUTSIDE_DEFINED_OFFICIAL_RANGE'
          AND requires_review = TRUE
    ) THEN
        RAISE EXCEPTION 'undefined official range guard failed';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM user_screening_record_classification
        WHERE observation_id = '40000000-0000-0000-0000-000000000006'
          AND reason_code = 'SEX_FOR_CLINICAL_USE_REQUIRED'
          AND requires_review = TRUE
    ) THEN
        RAISE EXCEPTION 'sex requirement guard failed';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM user_screening_record_classification
        WHERE observation_id = '40000000-0000-0000-0000-000000000007'
          AND reason_code = 'LOW_EXTRACTION_CONFIDENCE'
          AND requires_review = TRUE
    ) THEN
        RAISE EXCEPTION 'OCR confidence guard failed';
    END IF;

    RAISE NOTICE 'user screening classification integration assertions passed';
END;
$$;

SELECT
    item_code,
    classification_status,
    decision_state,
    reason_code
FROM user_screening_record_classification
WHERE user_id = '20000000-0000-0000-0000-000000000001'
  AND observation_id::TEXT LIKE '30000000-%'
ORDER BY item_code;

ROLLBACK;
