# 건강검진 청크 데이터 v1

이 문서는 보드의 `[Data] 건강검진 청크 데이터` 작업 범위를 정의한다. v1은 LABS Item Master 15개 항목마다 교육용 개요 청크 1개를 제공한다.

## 결론

- `[Data]`는 사람이 검토하고 공유할 수 있는 청크 작성 원본을 소유한다.
- `[Decider]`의 `intent`, `sub_intent`는 작성 원본에 넣지 않는다.
- `[RAG]`의 임베딩, 검색 텍스트, 토큰 수, 해시, 컬렉션 라우팅은 작성 원본에 넣지 않는다.
- 판정 기준값과 개인 검사 결과는 RDB 및 규칙 엔진이 소유한다.
- 원문 위치는 공유 청크에서 제외하고 내부 provenance 레지스트리로 분리한다.

## 파일

| 구분 | 경로 | 용도 |
|---|---|---|
| 공유용 청크 | `knowledge/chunks/screening-labs-v1.jsonl` | 협업·리뷰 기준 원본 |
| 내부 provenance | `knowledge/provenance/screening-labs-evidence-v1.jsonl` | 근거 URL과 임시 locator 관리 |
| 청크 스키마 | `knowledge/schemas/screening-chunk-authoring.schema.json` | 허용 컬럼과 상태 제약 |
| provenance 스키마 | `knowledge/schemas/screening-chunk-evidence.schema.json` | 내부 근거 레코드 제약 |
| 검증기 | `scripts/validate_screening_chunks.py` | 마스터 커버리지와 경계 검사 |
| 테스트 | `tests/test_screening_chunks.py` | 회귀 방지 |

## 공유용 최소 스키마

| 컬럼 | 타입 | 설명 | 소유 |
|---|---|---|---|
| `canonical_key` | `text` | 청크의 안정 식별자. v1은 `item_code`와 동일 | Data |
| `item_codes` | `text[]` | LABS Item Master 연결 키 | Data |
| `section_type` | `enum` | `LAB_EXPLANATION` 또는 `TEST_EXPLANATION` | Data |
| `domain` | `enum` | 혈액·당대사·지질·간·신장·감염 영역 | Data |
| `heading` | `text` | 사용자에게 보일 제목 | Data |
| `content` | `text` | 기준값을 포함하지 않는 교육용 설명 | Data |
| `keywords` | `text[]` | 동의어와 약어 | Data |
| `safety_level` | `enum` | `LOW`, `MODERATE`, `HIGH` | Data |
| `evidence_ids` | `text[]` | 내부 provenance 레지스트리 참조 | Data |
| `review_status` | `enum` | 근거·임상 검토 상태 | Data/검수 |
| `version` | `semver` | 콘텐츠 버전 | Data |
| `status` | `enum` | 배포 가능 여부를 나타내는 생명주기 상태 | Data/검수 |

`evidence_ids`는 공유 청크가 원문 위치 표기 방식에 종속되지 않도록 하는 안정 참조다. `source_document_id`, `source_locator`는 공유 청크에 없다. 내부 레지스트리의 `locator_hint`도 아직 표준 위치가 아니므로 모두 `PENDING_STANDARDIZATION`으로 표시한다.

## v1 데이터 상태

| 상태 | 수량 | 대상 |
|---|---:|---|
| `ACTIVE` + `SOURCE_VERIFIED` | 15 | 질병관리청·보건복지부 등 연결된 공식·전문 출처와 문구를 대조한 항목 |
| `DRAFT` + `DRAFT` | 0 | 현재 없음 |

간염 3개는 LABS Item Master의 항목 단위로 기존 통합 설명을 분리한 신규 청크다. 2026-07-24 질병관리청 공개자료와 대조하고 협업 검수를 완료해 `SOURCE_VERIFIED`와 `ACTIVE`로 전환했다.

### 현재 검수 정책

- 현재 팀에는 의료진 검수자가 없으므로 `CLINICALLY_APPROVED`를 사용하지 않는다.
- `SOURCE_VERIFIED`는 질병관리청·보건복지부 등 공식 공개자료와 청크 문구를 대조했다는 의미다.
- `SOURCE_VERIFIED`는 의료진의 진단·처방 검수를 의미하지 않는다.
- 질환 진단, 치료 선택, 투약, 개인별 위험도 판단을 직접 안내하는 콘텐츠는 공식자료 대조만으로 활성화하지 않고 별도의 전문가 검수 절차를 마련한다.

### Notion 공유용 현황표

| `item_code` | 제목 | 도메인 | 유형 | 안전도 | 검토·배포 상태 |
|---|---|---|---|---|---|
| `HEMOGLOBIN` | 혈색소(헤모글로빈) | `HEMATOLOGY` | `LAB_EXPLANATION` | `MODERATE` | `SOURCE_VERIFIED` · `ACTIVE` |
| `FASTING_GLUCOSE` | 공복혈당 | `GLUCOSE_METABOLISM` | `LAB_EXPLANATION` | `MODERATE` | `SOURCE_VERIFIED` · `ACTIVE` |
| `TOTAL_CHOLESTEROL` | 총콜레스테롤 | `LIPID` | `LAB_EXPLANATION` | `LOW` | `SOURCE_VERIFIED` · `ACTIVE` |
| `HDL_CHOLESTEROL` | HDL 콜레스테롤 | `LIPID` | `LAB_EXPLANATION` | `LOW` | `SOURCE_VERIFIED` · `ACTIVE` |
| `TRIGLYCERIDES` | 중성지방 | `LIPID` | `LAB_EXPLANATION` | `LOW` | `SOURCE_VERIFIED` · `ACTIVE` |
| `LDL_CHOLESTEROL` | LDL 콜레스테롤 | `LIPID` | `LAB_EXPLANATION` | `MODERATE` | `SOURCE_VERIFIED` · `ACTIVE` |
| `AST` | AST(SGOT) | `LIVER` | `LAB_EXPLANATION` | `MODERATE` | `SOURCE_VERIFIED` · `ACTIVE` |
| `ALT` | ALT(SGPT) | `LIVER` | `LAB_EXPLANATION` | `MODERATE` | `SOURCE_VERIFIED` · `ACTIVE` |
| `GAMMA_GTP` | 감마지티피(γ-GTP, GGT) | `LIVER` | `LAB_EXPLANATION` | `MODERATE` | `SOURCE_VERIFIED` · `ACTIVE` |
| `SERUM_CREATININE` | 혈청 크레아티닌 | `KIDNEY` | `LAB_EXPLANATION` | `MODERATE` | `SOURCE_VERIFIED` · `ACTIVE` |
| `EGFR` | 추정사구체여과율(eGFR) | `KIDNEY` | `LAB_EXPLANATION` | `MODERATE` | `SOURCE_VERIFIED` · `ACTIVE` |
| `URINE_PROTEIN` | 요단백 | `KIDNEY` | `LAB_EXPLANATION` | `MODERATE` | `SOURCE_VERIFIED` · `ACTIVE` |
| `HEPATITIS_B_SURFACE_ANTIGEN` | B형간염 표면항원(HBsAg) | `INFECTIOUS_DISEASE` | `TEST_EXPLANATION` | `MODERATE` | `SOURCE_VERIFIED` · `ACTIVE` |
| `HEPATITIS_B_SURFACE_ANTIBODY` | B형간염 표면항체(anti-HBs) | `INFECTIOUS_DISEASE` | `TEST_EXPLANATION` | `MODERATE` | `SOURCE_VERIFIED` · `ACTIVE` |
| `HEPATITIS_C_ANTIBODY` | C형간염 항체(anti-HCV) | `INFECTIOUS_DISEASE` | `TEST_EXPLANATION` | `MODERATE` | `SOURCE_VERIFIED` · `ACTIVE` |

## 파이프라인 인계

```text
[Data] screening-labs-v1.jsonl
        |
        | status=ACTIVE && review_status 승인
        v
[RAG] 검색 텍스트 생성 -> 토큰화 -> 임베딩 -> 컬렉션 적재
        |
        | 검색 결과에는 canonical_key/item_codes/evidence_ids 유지
        v
[LLM] RDB의 개인 결과·판정과 결합해 답변 생성

[Decider] intent/sub-intent는 질의 라우팅만 담당
[RDB] 기준값·대상자 조건·개인 검사값·판정 결과를 담당
```

## 검수 규칙

1. LABS Item Master의 15개 `item_code`가 정확히 한 번씩 등장해야 한다.
2. `ACTIVE` 청크는 `SOURCE_VERIFIED` 또는 `CLINICALLY_APPROVED`여야 한다.
3. 숫자 판정 기준은 청크 본문에 넣지 않는다.
4. 임베딩·라우팅·intent 필드를 작성 원본에 넣지 않는다.
5. 모든 `evidence_ids`는 내부 provenance 레지스트리에서 해석되어야 한다.

검증 명령:

```bash
python3 scripts/validate_screening_chunks.py
python3 -m unittest tests.test_screening_chunks
```
