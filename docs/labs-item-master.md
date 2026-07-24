# Labs Item Master

## 결정

국가건강검진 Labs 범위는 15개 항목으로 관리한다.

- 핵심 혈액·요검사 12종
- B형간염 표면항원·표면항체 2종
- C형간염 항체 1종

`item_name`은 표시명이 아니라 변경되지 않는 `item_code`로 사용한다. 항목 정보는
`screening_item`, Labs 전용 메타데이터는 `lab_item_profile`, 버전별 판정 경계는
`screening_rule_set`과 `screening_rule`에 저장한다. 현재 읽기 모델은
`labs_item_master` 뷰다.

기존 초안의 `normal_range_a`, `normal_range_b`, `suspect_range` 문자열은 DB 판정에
사용하지 않는다. 성별 조건, 열린 경계, 정성값, 규정 유효기간을 잃기 때문이다. 사람이
검토하거나 Notion에 붙여넣는 용도로만
`2026-01-07__MOHW-2026-6__labs-item-master.csv`에 표시 문자열을 생성한다.

## 15개 항목

| 순서 | item_code | 한글명 | 단위 | `sex_for_clinical_use` 필요 | 판정 방식 |
|---:|---|---|---|:---:|---|
| 1 | `HEMOGLOBIN` | 혈색소 | g/dL | Y | 규칙 엔진 |
| 2 | `FASTING_GLUCOSE` | 공복혈당 | mg/dL | N | 규칙 엔진 |
| 3 | `TOTAL_CHOLESTEROL` | 총콜레스테롤 | mg/dL | Y (대상조건) | 규칙 엔진 |
| 4 | `HDL_CHOLESTEROL` | 고밀도(HDL) 콜레스테롤 | mg/dL | Y (대상조건) | 규칙 엔진 |
| 5 | `TRIGLYCERIDES` | 중성지방 | mg/dL | Y (대상조건) | 규칙 엔진 |
| 6 | `LDL_CHOLESTEROL` | 저밀도(LDL) 콜레스테롤 | mg/dL | Y (대상조건) | 규칙 엔진 |
| 7 | `AST` | 에이에스티(AST/SGOT) | U/L | N | 규칙 엔진 |
| 8 | `ALT` | 에이엘티(ALT/SGPT) | U/L | N | 규칙 엔진 |
| 9 | `GAMMA_GTP` | 감마지티피(γ-GTP) | U/L | Y | 규칙 엔진 |
| 10 | `SERUM_CREATININE` | 혈청크레아티닌 | mg/dL | N | 규칙 엔진 |
| 11 | `EGFR` | 신사구체여과율(e-GFR) | mL/min/1.73m² | Y (계산식) | 규칙 엔진·계산값 |
| 12 | `URINE_PROTEIN` | 요단백 | 정성 | N | 규칙 엔진 |
| 13 | `HEPATITIS_B_SURFACE_ANTIGEN` | B형간염 표면항원 | 기관 보고 단위 | N | 항체와 조합한 원문 판정 |
| 14 | `HEPATITIS_B_SURFACE_ANTIBODY` | B형간염 표면항체 | 기관 보고 단위 | N | 항원과 조합한 원문 판정 |
| 15 | `HEPATITIS_C_ANTIBODY` | C형간염 항체 | 기관 보고 단위 | N | 검진기관 원문 판정 |

## 필드 매핑

| Notion 초안 | 최종 저장 위치 | 비고 |
|---|---|---|
| `item_name` | `screening_item.item_code` | PK, 대문자 snake case |
| `item_name_kr` | `screening_item.display_name_ko` | 사용자 표시명 |
| `unit` | `screening_item.canonical_unit` | 원문 단위는 observation에 별도 보존 |
| `gender_specific` | 저장하지 않음 | 의미가 불명확하고 판정 규칙과 중복되므로 제거 |
| 판정 규칙의 성별 의존성 | `classification_sex_specific` | `screening_rule.sex_scope`에서 자동 산출 |
| 대상조건의 성별 의존성 | `eligibility_sex_specific` | `eligibility`에서 자동 산출 |
| 계산식의 성별 의존성 | `derivation_requires_sex` | 계산식 입력에 필요한 경우만 저장 |
| 임상 사용 성별 필요 여부 | `requires_sex_for_clinical_use` | 위 세 조건을 OR로 합쳐 자동 산출 |
| `normal_range_*` | `screening_rule` | 숫자·포함 여부·성별·버전으로 정규화 |
| `categories` | `lab_item_profile.categories` | JSON 배열 |
| 대상 연령·주기 | `lab_item_profile.eligibility` | 지질·간염의 조건 보존 |
| 출처 | `source_document_id`, `source_locator` | 시행일과 원문 위치 보존 |

## 중요한 예외

- 혈색소의 고시 상한 초과와 감마지티피의 고시 하한 미만은 임의 판정하지 않는다.
- 혈청크레아티닌과 e-GFR에는 정상B 구간이 없다.
- LDL 콜레스테롤은 중성지방 수치에 따라 계산값 또는 실측값일 수 있다.
- B형간염 표면항원·표면항체는 두 결과를 함께 보며, 항체 유무를 정상A/B로 임의 변환하지
  않는다.
- C형간염 항체 양성은 확진이 아니므로 `C형간염 의심, 확진검사 필요` 문구를 유지한다.
- 결과통보서는 혈액검사 기준이 검진기관의 검사방법에 따라 달라질 수 있다고 명시하므로
  `screening_observation.reference_*`에 기관 참고치를 함께 보존한다.

## Sex와 gender

검사 판정과 계산에 사용하는 값은 `gender`가 아니라 `sex_for_clinical_use`로 관리한다.
사용자의 성정체성이나 행정상 gender를 검사 판정값으로 추정해서 사용하지 않는다.

- `screening_report.sex_for_clinical_use`: 해당 검진 결과를 해석할 때 사용할 값
- `screening_rule.sex_scope`: 규칙이 적용되는 임상 사용 성별
- `classification_sex_specific`: 현재 판정 규칙에 남성·여성 분기가 있는지 자동 산출
- `eligibility_sex_specific`: 국가검진 대상조건에 성별 분기가 있는지 자동 산출
- `derivation_requires_sex`: 계산식이 임상 사용 성별을 요구하는지 저장
- `requires_sex_for_clinical_use`: 위 조건 중 하나라도 참이면 자동으로 `true`

`sex_for_clinical_use = UNKNOWN`이면 성별에 의존하는 판정·대상조건 확인·계산만 실행하지
않고 `UNCLASSIFIED` 또는 `REVIEW_REQUIRED`로 처리한다. 검진기관이 보고한 원값과
성별에 의존하지 않는 판정까지 함께 숨기지는 않는다.

## 출처와 버전

- 기준: `건강검진 실시기준`, 보건복지부고시 제2026-6호
- 시행일: 2026-01-07
- [현행 고시](https://www.law.go.kr/LSW/admRulInfoP.do?admRulSeq=2100000272270&chrClsCd=010201)
- [검사항목별 판정기준](https://law.go.kr/LSW/flDownload.do?bylClsCd=200207&flNm=%5B%EB%B3%84%EC%B2%A8+1%5D+%EA%B2%80%EC%82%AC%ED%95%AD%EB%AA%A9%EB%B3%84+%ED%8C%90%EC%A0%95%EA%B8%B0%EC%A4%80&flSeq=160922929)
- [일반건강검진 결과통보서](https://law.go.kr/LSW/flDownload.do?bylClsCd=200203&flNm=%5B%EB%B3%84%EC%A7%80+6%5D+%EC%9D%BC%EB%B0%98%EA%B1%B4%EA%B0%95%EA%B2%80%EC%A7%84+%EA%B2%B0%EA%B3%BC%ED%86%B5%EB%B3%B4%EC%84%9C&flSeq=160922671)

이 마스터는 국가건강검진 결과 분류용이며, 질병 진단 기준이나 개별 검사실 참고범위를
대체하지 않는다.
