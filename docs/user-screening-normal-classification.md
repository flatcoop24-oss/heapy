# Users 건강검진 기록 정상판정 로직 v1

## 목적

검증된 사용자 건강검진 기록을 보건복지부 고시의 국가건강검진 결과 분류에
맞춰 `정상A`, `정상B(경계)`, `질환의심`, `판정불가`로 구분한다.

이 로직은 질병 진단이나 치료 판단이 아니다. RAG와 LLM은 판정값을 만들지
않고, RDB 규칙 엔진의 결과를 설명하는 역할만 맡는다.

## 결과 계약

| `classification_status` | 화면 표시 | `is_normal_a` | 의미 |
|---|---|---:|---|
| `NORMAL_A` | 정상 | `true` | 고시의 정상A 규칙과 일치 |
| `NORMAL_B` | 경계 | `false` | 정상B(경계). 정상으로 축약하지 않음 |
| `DISEASE_SUSPECTED` | 질환의심 | `false` | 검진 후 확인이 필요한 분류이며 확정 진단이 아님 |
| `SOURCE_REPORTED` | 결과지 판정 | `null` | 정상/비정상으로 임의 환산하지 않는 출처 복합판정 |
| `UNCLASSIFIED` | 검수 필요 | `null` | 입력 또는 공식 규칙만으로 안전하게 판정할 수 없음 |

## 정상판정 전 필수 조건

다음 조건을 모두 통과해야 `CLASSIFIED`가 된다.

1. `item_code`가 LABS Item Master에 매핑돼야 한다.
2. 보고서와 관찰값이 `AUTO_VALIDATED` 또는 `USER_CONFIRMED` 상태여야 한다.
3. 자동검증 값은 OCR 신뢰도 `0.95` 이상이어야 한다. 사용자 확인값은 OCR
   신뢰도와 관계없이 확인한 값을 사용한다.
4. 숫자 항목은 단위가 canonical unit과 일치해야 한다. v1은 단위 환산을
   하지 않는다.
5. 혈색소와 감마지티피는 `sex_for_clinical_use`가 필요하다.
6. 검사일에 적용할 규칙 버전이 있어야 한다.
7. 결과지 판정과 계산 판정이 다르면 자동 확정하지 않는다.

## 15개 항목 처리

| 처리 방식 | 항목 | 판정 |
|---|---|---|
| 공식 수치 규칙 | 혈색소, 공복혈당, 지질 4종, AST, ALT, 감마지티피, 혈청크레아티닌, eGFR | 검사일에 유효한 `screening_rule` 적용 |
| 공식 코드 규칙 | 요단백 | 음성·약양성·양성 기호를 표준 코드로 정규화 후 판정 |
| 결과지 복합판정 | B형간염 표면항원·표면항체 | 항원/항체 각각을 정상으로 환산하지 않고 결과지 판정 보존 |
| 결과지 판정 | C형간염 항체 | 항체 없음은 정상A, 항체 있음은 질환의심으로 기록하되 확진이 아님 |

혈색소의 공식 상한 초과와 감마지티피의 공식 하한 미만처럼 고시 표에 분류가
없는 범위는 `OUTSIDE_DEFINED_OFFICIAL_RANGE`로 반환한다.

## 판정불가 사유 코드

| `reason_code` | 의미 |
|---|---|
| `ITEM_UNMAPPED` | 검사명이 item_code로 정규화되지 않음 |
| `UNVERIFIED_RESULT` | 사용자 확인 또는 자동검증 전 |
| `LOW_EXTRACTION_CONFIDENCE` | 자동검증 OCR 신뢰도 미달 |
| `SCREENING_DATE_REQUIRED` | 검사일 없음 |
| `HISTORICAL_RULE_NOT_AVAILABLE` | 검사일에 해당하는 규칙 버전 없음 |
| `SEX_FOR_CLINICAL_USE_REQUIRED` | 성별 의존 판정에 필요한 값 없음 |
| `UNIT_REQUIRED` / `UNIT_MISMATCH` | 단위 없음 또는 canonical unit 불일치 |
| `CODE_VALUE_UNRECOGNIZED` | 요단백 등 코드형 결과 정규화 실패 |
| `SOURCE_RESULT_REQUIRED` | 결과지 우선 항목의 판정값 없음 |
| `SOURCE_COMPUTED_MISMATCH` | 결과지 판정과 계산 판정 불일치 |
| `OUTSIDE_DEFINED_OFFICIAL_RANGE` | 공식 고시가 해당 구간을 정의하지 않음 |

## 파일과 실행

| 파일 | 역할 |
|---|---|
| `scripts/classify_user_screening.py` | JSONL 배치 판정 및 애플리케이션 참조 구현 |
| `database/migrations/075_user_screening_classification.sql` | DB 보호 함수와 읽기 전용 View |
| `database/migrations/076_normalize_urine_protein_rules.sql` | 기존 DB의 요단백 기호 규칙을 표준 코드로 변환 |
| `knowledge/schemas/user-screening-classification.schema.json` | 판정 결과 공유 계약 |
| `tests/test_user_screening_classification.py` | 경계값·오류 경로 테스트 |
| `tests/sql/user_screening_classification_integration.sql` | 실제 PostgreSQL 통합 테스트 |
| `storage/.../screening-regulation.json` | 보건복지부 고시에서 정규화한 판정 규칙 |

JSONL 배치 실행:

```bash
python3 scripts/classify_user_screening.py \
  --input examples/user-screening-records-v1.jsonl \
  --output output/user-screening-classification-v1.jsonl
```

DB 조회:

```sql
SELECT *
FROM user_screening_record_classification
WHERE user_id = :user_id
ORDER BY screened_on DESC, item_code;
```

PostgreSQL 스키마와 Seed를 적용한 테스트 DB에서는 다음 SQL로 15개 항목과
오류 보호조건을 한 번에 검증한다.

```bash
psql "$TEST_DATABASE_URL" \
  -v ON_ERROR_STOP=1 \
  -f tests/sql/user_screening_classification_integration.sql
```

통합 테스트 데이터는 트랜잭션 마지막에 `ROLLBACK`되므로 테스트 DB에
사용자 기록을 남기지 않는다.

## 출력 예

```json
{
  "item_code": "FASTING_GLUCOSE",
  "classification_status": "NORMAL_B",
  "normality": "BORDERLINE",
  "is_normal_a": false,
  "decision_state": "CLASSIFIED",
  "requires_review": false,
  "reason_code": "OFFICIAL_RULE_MATCH",
  "basis": "OFFICIAL_RULE",
  "normalized_value": "100",
  "rule": {
    "rule_id": "GLUCOSE_NORMAL_B",
    "rule_version": "보건복지부고시 제2026-6호",
    "source_document_code": "MOHW_SCREENING_2026_6_APPENDIX_4_DETAIL",
    "source_locator": "별표4의 별첨 1쪽 당뇨병"
  }
}
```

## 출처와 적용 경계

- 보건복지부고시 제2026-6호 `건강검진 실시기준`
- 별표 4의 별첨 `검사항목별 판정기준`
- 별지 제6호서식 `일반건강검진 결과통보서`

혈액검사 결과는 검진기관별 검사방법에 따라 참고치와 판정이 다를 수 있으므로,
결과지 판정 원문과 기관 참고범위를 별도로 보존한다. 앱의 계산 결과와 결과지
판정이 다르면 자동으로 하나를 선택하지 않고 검수 대상으로 보낸다.
