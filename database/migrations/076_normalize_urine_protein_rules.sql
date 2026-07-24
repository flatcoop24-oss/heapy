-- 기존 DB에 남아 있는 요단백 기호 규칙을 애플리케이션 표준 코드로 맞춥니다.
-- 정책 기준을 바꾸는 작업이 아니라 같은 결과 표현을 정규화하는 전진 마이그레이션입니다.

BEGIN;

-- 이전 seed와 새 seed가 모두 실행되어 표준 코드 행이 이미 존재한다면,
-- 동일한 규칙의 기호 행을 먼저 제거해 unique index 충돌을 피합니다.
DELETE FROM screening_rule legacy
WHERE legacy.item_code = 'URINE_PROTEIN'
  AND legacy.expected_text IN ('-', '±', '+1', '+2', '+3', '+4')
  AND EXISTS (
      SELECT 1
      FROM screening_rule canonical
      WHERE canonical.rule_set_id = legacy.rule_set_id
        AND canonical.item_code = legacy.item_code
        AND canonical.sex_scope = legacy.sex_scope
        AND canonical.result_status = legacy.result_status
        AND canonical.lower_value IS NOT DISTINCT FROM legacy.lower_value
        AND canonical.upper_value IS NOT DISTINCT FROM legacy.upper_value
        AND canonical.expected_text = CASE legacy.expected_text
            WHEN '-' THEN 'NEGATIVE'
            WHEN '±' THEN 'TRACE'
            WHEN '+1' THEN 'POSITIVE_1'
            WHEN '+2' THEN 'POSITIVE_2'
            WHEN '+3' THEN 'POSITIVE_3'
            WHEN '+4' THEN 'POSITIVE_4'
        END
  );

UPDATE screening_rule
SET expected_text = CASE expected_text
        WHEN '-' THEN 'NEGATIVE'
        WHEN '±' THEN 'TRACE'
        WHEN '+1' THEN 'POSITIVE_1'
        WHEN '+2' THEN 'POSITIVE_2'
        WHEN '+3' THEN 'POSITIVE_3'
        WHEN '+4' THEN 'POSITIVE_4'
    END,
    notes = CASE expected_text
        WHEN '-' THEN '원문 음성(-)'
        WHEN '±' THEN '원문 약양성(±)'
        WHEN '+1' THEN '원문 양성 1+'
        WHEN '+2' THEN '원문 양성 2+'
        WHEN '+3' THEN '원문 양성 3+'
        WHEN '+4' THEN '원문 양성 4+'
    END
WHERE item_code = 'URINE_PROTEIN'
  AND expected_text IN ('-', '±', '+1', '+2', '+3', '+4');

COMMIT;
