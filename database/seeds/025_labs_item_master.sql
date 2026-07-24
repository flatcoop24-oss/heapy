BEGIN;

-- 항목 대상조건과 간염 원문 판정을 추적하기 위한 공식 문서를 등록합니다.
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
) VALUES
    (
        'c6a02f16-3222-424c-8fdd-6de8bba4e0d9'::UUID,
        (SELECT id FROM source_registry WHERE source_code = 'MOHW_SCREENING_RULE'),
        'MOHW-2026-6-APPENDIX-1',
        '건강검진 실시기준 [별표 1] 일반건강검진 검사항목, 대상자 및 검사방법',
        'SCREENING_ITEM_STANDARD',
        'https://law.go.kr/LSW/flDownload.do?flSeq=160922447',
        'mohw_screening/raw/2026-01-07__MOHW-2026-6__appendix-1-items.pdf',
        'PDF',
        'ko',
        '보건복지부고시 제2026-6호',
        '0c61bb0f3d5b63d83c3fa36b56100e90a8925fd4c5afc2baf836d848c83515d9',
        'RELATIONAL',
        'NORMALIZED',
        '2026-01-07T00:00:00+09:00'::TIMESTAMPTZ,
        DATE '2026-01-07',
        'SOURCE_VERIFIED',
        'NOT_REQUIRED',
        '보건복지부 건강검진 실시기준 제2026-6호 [별표 1]',
        FALSE,
        '{"pages":7,"role":"lab_item_scope_and_eligibility"}'::JSONB
    ),
    (
        'd8a4d049-4d86-4d6c-8e1e-7b263693b34e'::UUID,
        (SELECT id FROM source_registry WHERE source_code = 'MOHW_SCREENING_RULE'),
        'MOHW-2026-6-FORM-6',
        '건강검진 실시기준 [별지 제6호] 일반건강검진 결과통보서',
        'SCREENING_RESULT_FORM',
        'https://law.go.kr/LSW/flDownload.do?flSeq=160922671',
        'mohw_screening/raw/2026-01-07__MOHW-2026-6__appendix-6-result-notice.pdf',
        'PDF',
        'ko',
        '보건복지부고시 제2026-6호',
        '3ab6006ad6a25b5d294dc65f323b669e285b7987d3061755b06fec079d4cab6b',
        'RELATIONAL',
        'NORMALIZED',
        '2026-01-07T00:00:00+09:00'::TIMESTAMPTZ,
        DATE '2026-01-07',
        'SOURCE_VERIFIED',
        'NOT_REQUIRED',
        '보건복지부 건강검진 실시기준 제2026-6호 [별지 제6호]',
        FALSE,
        '{"pages":4,"role":"source_reported_lab_results"}'::JSONB
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
    item_code,
    display_name_ko,
    display_name_en,
    domain,
    measurement_type,
    canonical_unit,
    combination_group,
    knowledge_key
) VALUES
    ('HEMOGLOBIN', '혈색소', 'Hemoglobin', 'HEMATOLOGY', 'NUMERIC', 'g/dL', 'ANEMIA', 'HEMOGLOBIN'),
    ('FASTING_GLUCOSE', '공복혈당', 'Fasting plasma glucose', 'GLUCOSE_METABOLISM', 'NUMERIC', 'mg/dL', 'DIABETES', 'FASTING_GLUCOSE'),
    ('TOTAL_CHOLESTEROL', '총콜레스테롤', 'Total cholesterol', 'LIPID', 'NUMERIC', 'mg/dL', 'DYSLIPIDEMIA', 'TOTAL_CHOLESTEROL'),
    ('HDL_CHOLESTEROL', '고밀도(HDL) 콜레스테롤', 'HDL cholesterol', 'LIPID', 'NUMERIC', 'mg/dL', 'DYSLIPIDEMIA', 'HDL_CHOLESTEROL'),
    ('TRIGLYCERIDES', '중성지방', 'Triglycerides', 'LIPID', 'NUMERIC', 'mg/dL', 'DYSLIPIDEMIA', 'TRIGLYCERIDES'),
    ('LDL_CHOLESTEROL', '저밀도(LDL) 콜레스테롤', 'LDL cholesterol', 'LIPID', 'NUMERIC', 'mg/dL', 'DYSLIPIDEMIA', 'LDL_CHOLESTEROL'),
    ('AST', '에이에스티(AST/SGOT)', 'Aspartate aminotransferase', 'LIVER', 'NUMERIC', 'U/L', 'LIVER_FUNCTION', 'AST'),
    ('ALT', '에이엘티(ALT/SGPT)', 'Alanine aminotransferase', 'LIVER', 'NUMERIC', 'U/L', 'LIVER_FUNCTION', 'ALT'),
    ('GAMMA_GTP', '감마지티피(γ-GTP)', 'Gamma-glutamyl transferase', 'LIVER', 'NUMERIC', 'U/L', 'LIVER_FUNCTION', 'GAMMA_GTP'),
    ('SERUM_CREATININE', '혈청크레아티닌', 'Serum creatinine', 'KIDNEY', 'NUMERIC', 'mg/dL', 'KIDNEY_FUNCTION', 'SERUM_CREATININE'),
    ('EGFR', '신사구체여과율(e-GFR)', 'Estimated glomerular filtration rate', 'KIDNEY', 'NUMERIC', 'mL/min/1.73m2', 'KIDNEY_FUNCTION', 'EGFR'),
    ('URINE_PROTEIN', '요단백', 'Urine protein', 'KIDNEY', 'CODE', NULL, 'KIDNEY_FUNCTION', 'URINE_PROTEIN'),
    ('HEPATITIS_B_SURFACE_ANTIGEN', 'B형간염 표면항원', 'Hepatitis B surface antigen', 'HEPATITIS', 'NUMERIC_OR_CODE', NULL, 'HEPATITIS_B', NULL),
    ('HEPATITIS_B_SURFACE_ANTIBODY', 'B형간염 표면항체', 'Hepatitis B surface antibody', 'HEPATITIS', 'NUMERIC_OR_CODE', NULL, 'HEPATITIS_B', NULL),
    ('HEPATITIS_C_ANTIBODY', 'C형간염 항체', 'Hepatitis C antibody', 'HEPATITIS', 'NUMERIC_OR_CODE', NULL, 'HEPATITIS_C', NULL)
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

INSERT INTO screening_item_alias (
    alias_normalized,
    item_code,
    alias_display,
    source_type
) VALUES
    ('b형간염표면항원', 'HEPATITIS_B_SURFACE_ANTIGEN', 'B형간염 표면항원', 'DOCUMENT'),
    ('hbsag', 'HEPATITIS_B_SURFACE_ANTIGEN', 'HBsAg', 'INTERNAL'),
    ('hepatitisbsurfaceantigen', 'HEPATITIS_B_SURFACE_ANTIGEN', 'Hepatitis B surface antigen', 'INTERNAL'),
    ('b형간염표면항체', 'HEPATITIS_B_SURFACE_ANTIBODY', 'B형간염 표면항체', 'DOCUMENT'),
    ('hbsab', 'HEPATITIS_B_SURFACE_ANTIBODY', 'HBsAb', 'INTERNAL'),
    ('antihbs', 'HEPATITIS_B_SURFACE_ANTIBODY', 'anti-HBs', 'INTERNAL'),
    ('c형간염항체', 'HEPATITIS_C_ANTIBODY', 'C형간염 항체', 'DOCUMENT'),
    ('hcvab', 'HEPATITIS_C_ANTIBODY', 'HCV Ab', 'INTERNAL'),
    ('antihcv', 'HEPATITIS_C_ANTIBODY', 'anti-HCV', 'INTERNAL')
ON CONFLICT (alias_normalized) DO UPDATE SET
    item_code = EXCLUDED.item_code,
    alias_display = EXCLUDED.alias_display,
    source_type = EXCLUDED.source_type;

INSERT INTO lab_item_profile (
    item_code,
    display_order,
    specimen_type,
    result_representation,
    is_derived,
    derivation_mode,
    derivation_requires_sex,
    interpretation_mode,
    allowed_values,
    eligibility,
    categories,
    source_document_id,
    source_locator,
    notes
) VALUES
    (
        'HEMOGLOBIN', 1, 'WHOLE_BLOOD', 'NUMERIC', FALSE, 'NONE', FALSE,
        'RULE_ENGINE', '[]',
        '{"all_screening_subjects":true}',
        '["빈혈","혈액검사"]',
        'd7b8b2e7-f8cc-5f71-8e0e-59adddd35678',
        '별표 4의 별첨 1쪽 빈혈',
        '성별이 필요하며 고시가 분류하지 않은 상한 초과는 임의 판정하지 않음'
    ),
    (
        'FASTING_GLUCOSE', 2, 'SERUM_OR_PLASMA', 'NUMERIC', FALSE, 'NONE', FALSE,
        'RULE_ENGINE', '[]',
        '{"all_screening_subjects":true}',
        '["당뇨병","혈액검사"]',
        'd7b8b2e7-f8cc-5f71-8e0e-59adddd35678',
        '별표 4의 별첨 1쪽 당뇨병',
        '8시간 이상 공복 여부와 검진기관 원문 판정을 함께 확인'
    ),
    (
        'TOTAL_CHOLESTEROL', 3, 'SERUM_OR_PLASMA', 'NUMERIC', FALSE, 'NONE', FALSE,
        'RULE_ENGINE', '[]',
        '{"component_code":"LIPID_PANEL","any":[{"sex":"MALE","age_gte":24},{"sex":"FEMALE","age_gte":40}],"interval_years":4}',
        '["이상지질혈증","지질검사"]',
        'd7b8b2e7-f8cc-5f71-8e0e-59adddd35678',
        '별표 4의 별첨 1쪽 이상지질혈증',
        '검진일과 검진기관 참고치를 함께 보존'
    ),
    (
        'HDL_CHOLESTEROL', 4, 'SERUM_OR_PLASMA', 'NUMERIC', FALSE, 'NONE', FALSE,
        'RULE_ENGINE', '[]',
        '{"component_code":"LIPID_PANEL","any":[{"sex":"MALE","age_gte":24},{"sex":"FEMALE","age_gte":40}],"interval_years":4}',
        '["이상지질혈증","지질검사"]',
        'd7b8b2e7-f8cc-5f71-8e0e-59adddd35678',
        '별표 4의 별첨 1쪽 HDL 콜레스테롤',
        '값이 낮을수록 높은 판정 단계'
    ),
    (
        'TRIGLYCERIDES', 5, 'SERUM_OR_PLASMA', 'NUMERIC', FALSE, 'NONE', FALSE,
        'RULE_ENGINE', '[]',
        '{"component_code":"LIPID_PANEL","any":[{"sex":"MALE","age_gte":24},{"sex":"FEMALE","age_gte":40}],"interval_years":4}',
        '["이상지질혈증","지질검사"]',
        'd7b8b2e7-f8cc-5f71-8e0e-59adddd35678',
        '별표 4의 별첨 1쪽 중성지방',
        '검진일과 검진기관 참고치를 함께 보존'
    ),
    (
        'LDL_CHOLESTEROL', 6, 'SERUM_OR_PLASMA', 'NUMERIC', TRUE, 'CONDITIONAL', FALSE,
        'RULE_ENGINE', '[]',
        '{"component_code":"LIPID_PANEL","any":[{"sex":"MALE","age_gte":24},{"sex":"FEMALE","age_gte":40}],"interval_years":4}',
        '["이상지질혈증","지질검사"]',
        'd7b8b2e7-f8cc-5f71-8e0e-59adddd35678',
        '별표 4의 별첨 1쪽 LDL 콜레스테롤',
        '중성지방 400mg/dL 미만에서는 계산값일 수 있으며 당뇨 동반 주석을 별도 적용'
    ),
    (
        'AST', 7, 'SERUM', 'NUMERIC', FALSE, 'NONE', FALSE,
        'RULE_ENGINE', '[]',
        '{"all_screening_subjects":true}',
        '["간장질환","간기능검사"]',
        'd7b8b2e7-f8cc-5f71-8e0e-59adddd35678',
        '별표 4의 별첨 1쪽 AST',
        '단독 수치로 원인 질환을 확정하지 않음'
    ),
    (
        'ALT', 8, 'SERUM', 'NUMERIC', FALSE, 'NONE', FALSE,
        'RULE_ENGINE', '[]',
        '{"all_screening_subjects":true}',
        '["간장질환","간기능검사"]',
        'd7b8b2e7-f8cc-5f71-8e0e-59adddd35678',
        '별표 4의 별첨 1쪽 ALT',
        '단독 수치로 원인 질환을 확정하지 않음'
    ),
    (
        'GAMMA_GTP', 9, 'SERUM', 'NUMERIC', FALSE, 'NONE', FALSE,
        'RULE_ENGINE', '[]',
        '{"all_screening_subjects":true}',
        '["간장질환","간기능검사"]',
        'd7b8b2e7-f8cc-5f71-8e0e-59adddd35678',
        '별표 4의 별첨 1쪽 감마지티피',
        '성별이 필요하며 고시가 분류하지 않은 하한 미만은 임의 판정하지 않음'
    ),
    (
        'SERUM_CREATININE', 10, 'SERUM', 'NUMERIC', FALSE, 'NONE', FALSE,
        'RULE_ENGINE', '[]',
        '{"all_screening_subjects":true}',
        '["신장질환","신장기능검사"]',
        'd7b8b2e7-f8cc-5f71-8e0e-59adddd35678',
        '별표 4의 별첨 1쪽 혈청크레아티닌',
        '정상B 구간 없음. 검진기관 참고치와 e-GFR을 함께 표시'
    ),
    (
        'EGFR', 11, 'DERIVED', 'NUMERIC', TRUE, 'ALWAYS', TRUE,
        'RULE_ENGINE', '[]',
        '{"all_screening_subjects":true}',
        '["신장질환","신장기능검사"]',
        'd7b8b2e7-f8cc-5f71-8e0e-59adddd35678',
        '별표 4의 별첨 1쪽 e-GFR',
        '정상B 구간 없음. 검진기관 산출값과 계산식을 보존'
    ),
    (
        'URINE_PROTEIN', 12, 'URINE', 'CODE', FALSE, 'NONE', FALSE,
        'RULE_ENGINE',
        '["NEGATIVE","TRACE","POSITIVE_1","POSITIVE_2","POSITIVE_3","POSITIVE_4"]',
        '{"all_screening_subjects":true}',
        '["신장질환","요검사"]',
        'd7b8b2e7-f8cc-5f71-8e0e-59adddd35678',
        '별표 4의 별첨 1쪽 요단백',
        '코드값과 결과지 원문 기호를 함께 보존'
    ),
    (
        'HEPATITIS_B_SURFACE_ANTIGEN', 13, 'SERUM', 'NUMERIC_OR_CODE',
        FALSE, 'NONE', FALSE, 'SOURCE_REPORTED_COMPOSITE',
        '["NEGATIVE","POSITIVE","INDETERMINATE"]',
        '{"age_eq":40,"exclusions":["기존 표면항원 양성","자동·피동면역 항체형성"]}',
        '["B형간염","간염검사"]',
        'd8a4d049-4d86-4d6c-8e1e-7b263693b34e',
        '별표 1 3쪽 및 별지 제6호 결과통보서 2쪽',
        '일반/정밀 검사 구분, 정밀검사 수치와 기관 기준치를 원문대로 보존'
    ),
    (
        'HEPATITIS_B_SURFACE_ANTIBODY', 14, 'SERUM', 'NUMERIC_OR_CODE',
        FALSE, 'NONE', FALSE, 'SOURCE_REPORTED_COMPOSITE',
        '["NEGATIVE","POSITIVE","INDETERMINATE"]',
        '{"age_eq":40,"exclusions":["기존 표면항원 양성","자동·피동면역 항체형성"]}',
        '["B형간염","간염검사"]',
        'd8a4d049-4d86-4d6c-8e1e-7b263693b34e',
        '별표 1 3쪽 및 별지 제6호 결과통보서 2쪽',
        '항체 유무를 정상A/B로 임의 변환하지 않고 표면항원과 조합한 원문 판정을 우선'
    ),
    (
        'HEPATITIS_C_ANTIBODY', 15, 'SERUM', 'NUMERIC_OR_CODE',
        FALSE, 'NONE', FALSE, 'SOURCE_REPORTED',
        '["NEGATIVE","POSITIVE","INDETERMINATE"]',
        '{"age_eq":56}',
        '["C형간염","간염검사"]',
        'd8a4d049-4d86-4d6c-8e1e-7b263693b34e',
        '별표 1 3쪽 및 별지 제6호 결과통보서 2쪽',
        '항체 양성은 확진이 아니므로 확진검사 필요 문구를 유지'
    )
ON CONFLICT (item_code) DO UPDATE SET
    display_order = EXCLUDED.display_order,
    specimen_type = EXCLUDED.specimen_type,
    result_representation = EXCLUDED.result_representation,
    is_derived = EXCLUDED.is_derived,
    derivation_mode = EXCLUDED.derivation_mode,
    derivation_requires_sex = EXCLUDED.derivation_requires_sex,
    interpretation_mode = EXCLUDED.interpretation_mode,
    allowed_values = EXCLUDED.allowed_values,
    eligibility = EXCLUDED.eligibility,
    categories = EXCLUDED.categories,
    source_document_id = EXCLUDED.source_document_id,
    source_locator = EXCLUDED.source_locator,
    notes = EXCLUDED.notes,
    updated_at = NOW();

COMMIT;
