BEGIN;

-- 현행 규칙 원문을 source_document로 먼저 고정합니다.
INSERT INTO source_document (
    id,
    source_id,
    external_document_id,
    title,
    document_type,
    source_url,
    storage_path,
    content_format,
    language_code,
    version_label,
    checksum_sha256,
    ingestion_target,
    processing_status,
    published_at,
    effective_from,
    review_status,
    clinical_review_status,
    citation_label,
    is_retrievable,
    metadata
) VALUES (
    'd7b8b2e7-f8cc-5f71-8e0e-59adddd35678'::UUID,
    (SELECT id FROM source_registry WHERE source_code = 'MOHW_SCREENING_RULE'),
    'MOHW-2026-6-APPENDIX-4',
    '건강검진 실시기준 [별표 4의 별첨] 검사항목별 판정기준',
    'SCREENING_RULE',
    'https://law.go.kr/LSW/flDownload.do?bylClsCd=200207&flNm=%5B%EB%B3%84%EC%B2%A8+1%5D+%EA%B2%80%EC%82%AC%ED%95%AD%EB%AA%A9%EB%B3%84+%ED%8C%90%EC%A0%95%EA%B8%B0%EC%A4%80&flSeq=160922929',
    'mohw_screening/raw/2026-01-07__MOHW-2026-6__v2026-6.pdf',
    'PDF',
    'ko',
    '보건복지부고시 제2026-6호',
    '5f804efa7257c067eabe8084cff6b9fb3d140f8f33e10234fc5423351f6ed11a',
    'RELATIONAL',
    'NORMALIZED',
    '2026-01-07T00:00:00+09:00'::TIMESTAMPTZ,
    DATE '2026-01-07',
    'SOURCE_VERIFIED',
    'NOT_REQUIRED',
    '보건복지부 건강검진 실시기준 제2026-6호 [별표 4의 별첨]',
    FALSE,
    '{"pages":3,"rule_scope":"national_health_screening","extracted_by":"pypdf_and_visual_review"}'::JSONB
)
ON CONFLICT (id) DO UPDATE SET
    source_url = EXCLUDED.source_url,
    storage_path = EXCLUDED.storage_path,
    checksum_sha256 = EXCLUDED.checksum_sha256,
    version_label = EXCLUDED.version_label,
    effective_from = EXCLUDED.effective_from,
    review_status = EXCLUDED.review_status,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

INSERT INTO screening_item (
    item_code, display_name_ko, display_name_en, domain,
    measurement_type, canonical_unit, combination_group, knowledge_key
) VALUES
    ('SYSTOLIC_BP', '수축기 혈압', 'Systolic blood pressure', 'CARDIOVASCULAR', 'NUMERIC', 'mmHg', 'BLOOD_PRESSURE', 'BLOOD_PRESSURE'),
    ('DIASTOLIC_BP', '이완기 혈압', 'Diastolic blood pressure', 'CARDIOVASCULAR', 'NUMERIC', 'mmHg', 'BLOOD_PRESSURE', 'BLOOD_PRESSURE'),
    ('BMI', '체질량지수', 'Body mass index', 'BODY_COMPOSITION', 'NUMERIC', 'kg/m2', 'OBESITY', 'BMI'),
    ('WAIST_CIRCUMFERENCE', '허리둘레', 'Waist circumference', 'BODY_COMPOSITION', 'NUMERIC', 'cm', 'OBESITY', 'WAIST_CIRCUMFERENCE'),
    ('HEMOGLOBIN', '혈색소', 'Hemoglobin', 'HEMATOLOGY', 'NUMERIC', 'g/dL', 'ANEMIA', 'HEMOGLOBIN'),
    ('FASTING_GLUCOSE', '공복혈당', 'Fasting plasma glucose', 'GLUCOSE_METABOLISM', 'NUMERIC', 'mg/dL', 'DIABETES', 'FASTING_GLUCOSE'),
    ('TOTAL_CHOLESTEROL', '총콜레스테롤', 'Total cholesterol', 'LIPID', 'NUMERIC', 'mg/dL', 'DYSLIPIDEMIA', 'TOTAL_CHOLESTEROL'),
    ('HDL_CHOLESTEROL', '고밀도(HDL) 콜레스테롤', 'HDL cholesterol', 'LIPID', 'NUMERIC', 'mg/dL', 'DYSLIPIDEMIA', 'HDL_CHOLESTEROL'),
    ('TRIGLYCERIDES', '중성지방', 'Triglycerides', 'LIPID', 'NUMERIC', 'mg/dL', 'DYSLIPIDEMIA', 'TRIGLYCERIDES'),
    ('LDL_CHOLESTEROL', '저밀도(LDL) 콜레스테롤', 'LDL cholesterol', 'LIPID', 'NUMERIC', 'mg/dL', 'DYSLIPIDEMIA', 'LDL_CHOLESTEROL'),
    ('AST', '에이에스티(AST/SGOT)', 'Aspartate aminotransferase', 'LIVER', 'NUMERIC', 'U/L', 'LIVER_FUNCTION', 'AST'),
    ('ALT', '에이엘티(ALT/SGPT)', 'Alanine aminotransferase', 'LIVER', 'NUMERIC', 'U/L', 'LIVER_FUNCTION', 'ALT'),
    ('GAMMA_GTP', '감마지티피(γ-GTP)', 'Gamma-glutamyl transferase', 'LIVER', 'NUMERIC', 'U/L', 'LIVER_FUNCTION', 'GAMMA_GTP'),
    ('URINE_PROTEIN', '요단백', 'Urine protein', 'KIDNEY', 'CODE', NULL, 'KIDNEY_FUNCTION', 'URINE_PROTEIN'),
    ('SERUM_CREATININE', '혈청크레아티닌', 'Serum creatinine', 'KIDNEY', 'NUMERIC', 'mg/dL', 'KIDNEY_FUNCTION', 'SERUM_CREATININE'),
    ('EGFR', '신사구체여과율(eGFR)', 'Estimated glomerular filtration rate', 'KIDNEY', 'NUMERIC', 'mL/min/1.73m2', 'KIDNEY_FUNCTION', 'EGFR')
ON CONFLICT (item_code) DO UPDATE SET
    display_name_ko = EXCLUDED.display_name_ko,
    display_name_en = EXCLUDED.display_name_en,
    domain = EXCLUDED.domain,
    measurement_type = EXCLUDED.measurement_type,
    canonical_unit = EXCLUDED.canonical_unit,
    combination_group = EXCLUDED.combination_group,
    knowledge_key = EXCLUDED.knowledge_key,
    is_active = TRUE,
    updated_at = NOW();

INSERT INTO screening_item_alias (alias_normalized, item_code, alias_display, source_type) VALUES
    ('수축기혈압', 'SYSTOLIC_BP', '수축기 혈압', 'DOCUMENT'),
    ('최고혈압', 'SYSTOLIC_BP', '최고혈압', 'INTERNAL'),
    ('sbp', 'SYSTOLIC_BP', 'SBP', 'INTERNAL'),
    ('이완기혈압', 'DIASTOLIC_BP', '이완기 혈압', 'DOCUMENT'),
    ('최저혈압', 'DIASTOLIC_BP', '최저혈압', 'INTERNAL'),
    ('dbp', 'DIASTOLIC_BP', 'DBP', 'INTERNAL'),
    ('bmi', 'BMI', 'BMI', 'DOCUMENT'),
    ('체질량지수', 'BMI', '체질량지수', 'DOCUMENT'),
    ('허리둘레', 'WAIST_CIRCUMFERENCE', '허리둘레', 'DOCUMENT'),
    ('복부둘레', 'WAIST_CIRCUMFERENCE', '복부둘레', 'INTERNAL'),
    ('혈색소', 'HEMOGLOBIN', '혈색소', 'DOCUMENT'),
    ('헤모글로빈', 'HEMOGLOBIN', '헤모글로빈', 'INTERNAL'),
    ('hemoglobin', 'HEMOGLOBIN', 'Hemoglobin', 'INTERNAL'),
    ('hb', 'HEMOGLOBIN', 'Hb', 'INTERNAL'),
    ('공복혈당', 'FASTING_GLUCOSE', '공복혈당', 'DOCUMENT'),
    ('공복혈장포도당', 'FASTING_GLUCOSE', '공복혈장포도당', 'INTERNAL'),
    ('fpg', 'FASTING_GLUCOSE', 'FPG', 'INTERNAL'),
    ('총콜레스테롤', 'TOTAL_CHOLESTEROL', '총콜레스테롤', 'DOCUMENT'),
    ('totalcholesterol', 'TOTAL_CHOLESTEROL', 'Total cholesterol', 'INTERNAL'),
    ('hdl', 'HDL_CHOLESTEROL', 'HDL', 'INTERNAL'),
    ('hdl콜레스테롤', 'HDL_CHOLESTEROL', 'HDL 콜레스테롤', 'DOCUMENT'),
    ('고밀도콜레스테롤', 'HDL_CHOLESTEROL', '고밀도 콜레스테롤', 'INTERNAL'),
    ('중성지방', 'TRIGLYCERIDES', '중성지방', 'DOCUMENT'),
    ('트리글리세라이드', 'TRIGLYCERIDES', '트리글리세라이드', 'INTERNAL'),
    ('tg', 'TRIGLYCERIDES', 'TG', 'INTERNAL'),
    ('ldl', 'LDL_CHOLESTEROL', 'LDL', 'INTERNAL'),
    ('ldl콜레스테롤', 'LDL_CHOLESTEROL', 'LDL 콜레스테롤', 'DOCUMENT'),
    ('저밀도콜레스테롤', 'LDL_CHOLESTEROL', '저밀도 콜레스테롤', 'INTERNAL'),
    ('ast', 'AST', 'AST', 'DOCUMENT'),
    ('sgot', 'AST', 'SGOT', 'INTERNAL'),
    ('에이에스티', 'AST', '에이에스티', 'DOCUMENT'),
    ('alt', 'ALT', 'ALT', 'DOCUMENT'),
    ('sgpt', 'ALT', 'SGPT', 'INTERNAL'),
    ('에이엘티', 'ALT', '에이엘티', 'DOCUMENT'),
    ('감마지티피', 'GAMMA_GTP', '감마지티피', 'DOCUMENT'),
    ('감마gtp', 'GAMMA_GTP', '감마GTP', 'INTERNAL'),
    ('γ-gtp', 'GAMMA_GTP', 'γ-GTP', 'DOCUMENT'),
    ('ggt', 'GAMMA_GTP', 'GGT', 'INTERNAL'),
    ('요단백', 'URINE_PROTEIN', '요단백', 'DOCUMENT'),
    ('단백뇨', 'URINE_PROTEIN', '단백뇨', 'INTERNAL'),
    ('혈청크레아티닌', 'SERUM_CREATININE', '혈청크레아티닌', 'DOCUMENT'),
    ('크레아티닌', 'SERUM_CREATININE', '크레아티닌', 'INTERNAL'),
    ('creatinine', 'SERUM_CREATININE', 'Creatinine', 'INTERNAL'),
    ('egfr', 'EGFR', 'eGFR', 'DOCUMENT'),
    ('신사구체여과율', 'EGFR', '신사구체여과율', 'DOCUMENT'),
    ('추정사구체여과율', 'EGFR', '추정사구체여과율', 'INTERNAL')
ON CONFLICT (alias_normalized) DO UPDATE SET
    item_code = EXCLUDED.item_code,
    alias_display = EXCLUDED.alias_display,
    source_type = EXCLUDED.source_type;

INSERT INTO screening_rule_set (
    rule_set_code, source_document_id, version_label, effective_from, is_active, notes
) VALUES (
    'MOHW_SCREENING_2026_6',
    'd7b8b2e7-f8cc-5f71-8e0e-59adddd35678'::UUID,
    '보건복지부고시 제2026-6호',
    DATE '2026-01-07',
    TRUE,
    '국가건강검진 판정용. 진단기준이나 검사실 참고범위로 재사용하지 않음'
)
ON CONFLICT (rule_set_code) DO UPDATE SET
    source_document_id = EXCLUDED.source_document_id,
    version_label = EXCLUDED.version_label,
    effective_from = EXCLUDED.effective_from,
    is_active = EXCLUDED.is_active,
    notes = EXCLUDED.notes,
    updated_at = NOW();

WITH rs AS (
    SELECT id FROM screening_rule_set WHERE rule_set_code = 'MOHW_SCREENING_2026_6'
)
INSERT INTO screening_rule (
    rule_set_id, item_code, sex_scope, result_status,
    lower_value, lower_inclusive, upper_value, upper_inclusive,
    expected_text, priority, source_locator, notes
)
SELECT rs.id, v.item_code, v.sex_scope, v.result_status,
       v.lower_value, v.lower_inclusive, v.upper_value, v.upper_inclusive,
       v.expected_text, v.priority, v.source_locator, v.notes
FROM rs
CROSS JOIN (VALUES
    ('SYSTOLIC_BP', 'ANY', 'NORMAL_A', NULL, TRUE, 120, FALSE, NULL, 10, '1쪽 고혈압', '이완기 혈압과 결합하여 최종 판정'),
    ('SYSTOLIC_BP', 'ANY', 'NORMAL_B', 120, TRUE, 140, FALSE, NULL, 20, '1쪽 고혈압', NULL),
    ('SYSTOLIC_BP', 'ANY', 'DISEASE_SUSPECTED', 140, TRUE, NULL, TRUE, NULL, 30, '1쪽 고혈압', NULL),
    ('DIASTOLIC_BP', 'ANY', 'NORMAL_A', NULL, TRUE, 80, FALSE, NULL, 10, '1쪽 고혈압', '수축기 혈압과 결합하여 최종 판정'),
    ('DIASTOLIC_BP', 'ANY', 'NORMAL_B', 80, TRUE, 90, FALSE, NULL, 20, '1쪽 고혈압', NULL),
    ('DIASTOLIC_BP', 'ANY', 'DISEASE_SUSPECTED', 90, TRUE, NULL, TRUE, NULL, 30, '1쪽 고혈압', NULL),
    ('BMI', 'ANY', 'NORMAL_A', 18.5, TRUE, 25, FALSE, NULL, 10, '1쪽 비만', NULL),
    ('BMI', 'ANY', 'NORMAL_B', NULL, TRUE, 18.5, FALSE, NULL, 20, '1쪽 비만', '저체중 범위'),
    ('BMI', 'ANY', 'NORMAL_B', 25, TRUE, 30, FALSE, NULL, 20, '1쪽 비만', '과체중 범위'),
    ('BMI', 'ANY', 'DISEASE_SUSPECTED', 30, TRUE, NULL, TRUE, NULL, 30, '1쪽 비만', NULL),
    ('WAIST_CIRCUMFERENCE', 'MALE', 'NORMAL_A', NULL, TRUE, 90, FALSE, NULL, 10, '1쪽 허리둘레', NULL),
    ('WAIST_CIRCUMFERENCE', 'MALE', 'DISEASE_SUSPECTED', 90, TRUE, NULL, TRUE, NULL, 30, '1쪽 허리둘레', NULL),
    ('WAIST_CIRCUMFERENCE', 'FEMALE', 'NORMAL_A', NULL, TRUE, 85, FALSE, NULL, 10, '1쪽 허리둘레', NULL),
    ('WAIST_CIRCUMFERENCE', 'FEMALE', 'DISEASE_SUSPECTED', 85, TRUE, NULL, TRUE, NULL, 30, '1쪽 허리둘레', NULL),
    ('HEMOGLOBIN', 'MALE', 'NORMAL_A', 13.0, TRUE, 16.5, TRUE, NULL, 10, '1쪽 빈혈', NULL),
    ('HEMOGLOBIN', 'MALE', 'NORMAL_B', 12.0, TRUE, 13.0, FALSE, NULL, 20, '1쪽 빈혈', NULL),
    ('HEMOGLOBIN', 'MALE', 'DISEASE_SUSPECTED', NULL, TRUE, 12.0, FALSE, NULL, 30, '1쪽 빈혈', NULL),
    ('HEMOGLOBIN', 'FEMALE', 'NORMAL_A', 12.0, TRUE, 15.5, TRUE, NULL, 10, '1쪽 빈혈', NULL),
    ('HEMOGLOBIN', 'FEMALE', 'NORMAL_B', 10.0, TRUE, 12.0, FALSE, NULL, 20, '1쪽 빈혈', NULL),
    ('HEMOGLOBIN', 'FEMALE', 'DISEASE_SUSPECTED', NULL, TRUE, 10.0, FALSE, NULL, 30, '1쪽 빈혈', NULL),
    ('FASTING_GLUCOSE', 'ANY', 'NORMAL_A', NULL, TRUE, 100, FALSE, NULL, 10, '1쪽 당뇨병', NULL),
    ('FASTING_GLUCOSE', 'ANY', 'NORMAL_B', 100, TRUE, 126, FALSE, NULL, 20, '1쪽 당뇨병', NULL),
    ('FASTING_GLUCOSE', 'ANY', 'DISEASE_SUSPECTED', 126, TRUE, NULL, TRUE, NULL, 30, '1쪽 당뇨병', NULL),
    ('TOTAL_CHOLESTEROL', 'ANY', 'NORMAL_A', NULL, TRUE, 200, FALSE, NULL, 10, '1쪽 이상지질혈증', NULL),
    ('TOTAL_CHOLESTEROL', 'ANY', 'NORMAL_B', 200, TRUE, 240, FALSE, NULL, 20, '1쪽 이상지질혈증', NULL),
    ('TOTAL_CHOLESTEROL', 'ANY', 'DISEASE_SUSPECTED', 240, TRUE, NULL, TRUE, NULL, 30, '1쪽 이상지질혈증', NULL),
    ('HDL_CHOLESTEROL', 'ANY', 'NORMAL_A', 60, TRUE, NULL, TRUE, NULL, 10, '1쪽 HDL', NULL),
    ('HDL_CHOLESTEROL', 'ANY', 'NORMAL_B', 40, TRUE, 60, FALSE, NULL, 20, '1쪽 HDL', NULL),
    ('HDL_CHOLESTEROL', 'ANY', 'DISEASE_SUSPECTED', NULL, TRUE, 40, FALSE, NULL, 30, '1쪽 HDL', NULL),
    ('TRIGLYCERIDES', 'ANY', 'NORMAL_A', NULL, TRUE, 150, FALSE, NULL, 10, '1쪽 중성지방', NULL),
    ('TRIGLYCERIDES', 'ANY', 'NORMAL_B', 150, TRUE, 200, FALSE, NULL, 20, '1쪽 중성지방', NULL),
    ('TRIGLYCERIDES', 'ANY', 'DISEASE_SUSPECTED', 200, TRUE, NULL, TRUE, NULL, 30, '1쪽 중성지방', NULL),
    ('LDL_CHOLESTEROL', 'ANY', 'NORMAL_A', NULL, TRUE, 130, FALSE, NULL, 10, '1쪽 LDL', '개인 위험도별 치료 목표와 구분'),
    ('LDL_CHOLESTEROL', 'ANY', 'NORMAL_B', 130, TRUE, 160, FALSE, NULL, 20, '1쪽 LDL', NULL),
    ('LDL_CHOLESTEROL', 'ANY', 'DISEASE_SUSPECTED', 160, TRUE, NULL, TRUE, NULL, 30, '1쪽 LDL', NULL),
    ('AST', 'ANY', 'NORMAL_A', NULL, TRUE, 40, TRUE, NULL, 10, '1쪽 AST', NULL),
    ('AST', 'ANY', 'NORMAL_B', 40, FALSE, 50, TRUE, NULL, 20, '1쪽 AST', NULL),
    ('AST', 'ANY', 'DISEASE_SUSPECTED', 50, FALSE, NULL, TRUE, NULL, 30, '1쪽 AST', NULL),
    ('ALT', 'ANY', 'NORMAL_A', NULL, TRUE, 35, TRUE, NULL, 10, '1쪽 ALT', NULL),
    ('ALT', 'ANY', 'NORMAL_B', 35, FALSE, 45, TRUE, NULL, 20, '1쪽 ALT', NULL),
    ('ALT', 'ANY', 'DISEASE_SUSPECTED', 45, FALSE, NULL, TRUE, NULL, 30, '1쪽 ALT', NULL),
    ('GAMMA_GTP', 'MALE', 'NORMAL_A', 11, TRUE, 63, TRUE, NULL, 10, '1쪽 감마지티피', NULL),
    ('GAMMA_GTP', 'MALE', 'NORMAL_B', 63, FALSE, 77, TRUE, NULL, 20, '1쪽 감마지티피', NULL),
    ('GAMMA_GTP', 'MALE', 'DISEASE_SUSPECTED', 77, FALSE, NULL, TRUE, NULL, 30, '1쪽 감마지티피', NULL),
    ('GAMMA_GTP', 'FEMALE', 'NORMAL_A', 8, TRUE, 35, TRUE, NULL, 10, '1쪽 감마지티피', NULL),
    ('GAMMA_GTP', 'FEMALE', 'NORMAL_B', 35, FALSE, 45, TRUE, NULL, 20, '1쪽 감마지티피', NULL),
    ('GAMMA_GTP', 'FEMALE', 'DISEASE_SUSPECTED', 45, FALSE, NULL, TRUE, NULL, 30, '1쪽 감마지티피', NULL),
    ('URINE_PROTEIN', 'ANY', 'NORMAL_A', NULL, TRUE, NULL, TRUE, '-', 10, '1쪽 요단백', '음성'),
    ('URINE_PROTEIN', 'ANY', 'NORMAL_B', NULL, TRUE, NULL, TRUE, '±', 20, '1쪽 요단백', '약양성'),
    ('URINE_PROTEIN', 'ANY', 'DISEASE_SUSPECTED', NULL, TRUE, NULL, TRUE, '+1', 30, '1쪽 요단백', '양성 1+'),
    ('URINE_PROTEIN', 'ANY', 'DISEASE_SUSPECTED', NULL, TRUE, NULL, TRUE, '+2', 30, '1쪽 요단백', '양성 2+'),
    ('URINE_PROTEIN', 'ANY', 'DISEASE_SUSPECTED', NULL, TRUE, NULL, TRUE, '+3', 30, '1쪽 요단백', '양성 3+'),
    ('URINE_PROTEIN', 'ANY', 'DISEASE_SUSPECTED', NULL, TRUE, NULL, TRUE, '+4', 30, '1쪽 요단백', '양성 4+'),
    ('SERUM_CREATININE', 'ANY', 'NORMAL_A', NULL, TRUE, 1.5, TRUE, NULL, 10, '1쪽 혈청크레아티닌', NULL),
    ('SERUM_CREATININE', 'ANY', 'DISEASE_SUSPECTED', 1.5, FALSE, NULL, TRUE, NULL, 30, '1쪽 혈청크레아티닌', NULL),
    ('EGFR', 'ANY', 'NORMAL_A', 60, TRUE, NULL, TRUE, NULL, 10, '1쪽 e-GFR', NULL),
    ('EGFR', 'ANY', 'DISEASE_SUSPECTED', NULL, TRUE, 60, FALSE, NULL, 30, '1쪽 e-GFR', NULL)
) AS v(
    item_code, sex_scope, result_status,
    lower_value, lower_inclusive, upper_value, upper_inclusive,
    expected_text, priority, source_locator, notes
)
ON CONFLICT DO NOTHING;

COMMIT;
