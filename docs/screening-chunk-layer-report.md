# 건강검진 Authoring Chunk / RAG Serving Chunk 분리 보고서

## 결론

건강검진 청크를 하나의 파일로 공동 사용하지 않고 다음 두 레이어로 분리한다.

1. **Authoring Chunk**: 사람이 문구·근거·상태를 검수하는 유일한 원본
2. **RAG Serving Chunk**: 승인된 Authoring Chunk에서 자동 생성하는 검색·임베딩용 파생물

RAG Serving 파일은 직접 수정하지 않는다. 문구를 바꾸려면 Authoring을 수정하고 검증 후 Serving을 다시 생성한다.

## 산출물

| 레이어 | 파일 | 용도 | 직접 수정 |
|---|---|---|---|
| Authoring 원본 | `knowledge/chunks/screening-labs-v1.jsonl` | 버전 관리·자동 검증 기준 | Data 담당자 |
| Authoring 검수 화면 | `LABS_Authoring_Chunks_검수용_v1.xlsx` | 사람이 문구·근거·검수 의견 확인 | 검수 결과·메모 열 |
| RAG Serving | `vdb/corpus/screening_labs_rag_v1.jsonl` | 임베딩 입력 및 Vector DB 적재 | 금지 |
| 근거 레지스트리 | `knowledge/provenance/screening-labs-evidence-v1.jsonl` | evidence_id 해석과 출처 추적 | Data 담당자 |

## 1. Authoring Chunk

Authoring Chunk는 콘텐츠를 만들고 검수하기 위한 레코드다.

```json
{
  "canonical_key": "FASTING_GLUCOSE",
  "item_codes": ["FASTING_GLUCOSE"],
  "section_type": "LAB_EXPLANATION",
  "domain": "GLUCOSE_METABOLISM",
  "heading": "공복혈당",
  "content": "공복혈당은 일정 시간 금식한 뒤 혈액 속 포도당 농도를 측정해 당 대사 상태를 살피는 검사입니다...",
  "keywords": ["공복혈당", "혈당", "glucose", "당뇨", "FPG"],
  "safety_level": "MODERATE",
  "evidence_ids": ["MOHW_SCREENING_JUDGEMENT_2026", "KDA_DIABETES_GUIDELINE_2025"],
  "review_status": "SOURCE_VERIFIED",
  "version": "1.0.0",
  "status": "ACTIVE"
}
```

### 사람이 검수할 항목

| 검수 대상 | 확인 질문 |
|---|---|
| 제목 | 일반 사용자가 검사명을 이해할 수 있는가 |
| 설명 | 한 검사만 설명하며, 독립적으로 이해되는가 |
| 표현 | 질환을 단정하거나 치료를 지시하지 않는가 |
| 숫자 | 판정 기준값이 섞이지 않았는가 |
| 키워드 | 한글명·영문명·약어가 포함됐는가 |
| 근거 | 모든 evidence_id가 레지스트리에서 해석되는가 |
| 상태 | 공식자료 대조 전에는 ACTIVE로 바뀌지 않았는가 |

현재 팀에는 의료진 검수자가 없으므로 `CLINICALLY_APPROVED`는 사용하지 않는다. `SOURCE_VERIFIED`는 질병관리청·보건복지부 등 연결된 공개자료와 문구를 대조했다는 의미이며 의료진 검수를 뜻하지 않는다.

## 2. RAG Serving Chunk

RAG Serving Chunk는 승인된 Authoring 레코드를 검색 시스템에 전달하기 위한 최소 레코드다.

```json
{
  "chunk_id": "FASTING_GLUCOSE",
  "text": "공복혈당\n\n공복혈당은 일정 시간 금식한 뒤...\n\n키워드: 공복혈당 · 혈당 · glucose · 당뇨 · FPG",
  "text_sha256": "64자리 SHA-256",
  "metadata": {
    "item_codes": ["FASTING_GLUCOSE"],
    "domain": "GLUCOSE_METABOLISM",
    "safety_level": "MODERATE",
    "evidence_ids": ["MOHW_SCREENING_JUDGEMENT_2026", "KDA_DIABETES_GUIDELINE_2025"],
    "version": "1.0.0"
  }
}
```

### 필드 역할

| 필드 | 임베딩 여부 | 역할 |
|---|---|---|
| `chunk_id` | 제외 | 검색 결과 식별 |
| `text` | **임베딩** | `heading + content + keywords`를 합친 유일한 입력 |
| `text_sha256` | 제외 | 텍스트 변경 여부 확인·불필요한 재임베딩 방지 |
| `metadata.item_codes` | 제외 | LABS Item Master·RDB 연결 |
| `metadata.domain` | 제외 | 검색 필터 |
| `metadata.safety_level` | 제외 | 답변 안전정책 |
| `metadata.evidence_ids` | 제외 | 검색 후 출처 연결 |
| `metadata.version` | 제외 | 동기화·재적재 판단 |

`review_status`, `status`, `section_type`은 적재 전 필터링에만 사용하고 Serving에는 복사하지 않는다. 출처 URL과 locator도 Serving에 넣지 않는다.

## 필드 변환

| Authoring | RAG Serving | 처리 |
|---|---|---|
| `canonical_key` | `chunk_id` | 이름 변경 |
| `heading` | `text` | 본문 첫 부분으로 결합 |
| `content` | `text` | 본문 중심 내용으로 결합 |
| `keywords` | `text` | `키워드:` 구간으로 결합 |
| `item_codes` | `metadata.item_codes` | 그대로 전달 |
| `domain` | `metadata.domain` | 그대로 전달 |
| `safety_level` | `metadata.safety_level` | 그대로 전달 |
| `evidence_ids` | `metadata.evidence_ids` | 그대로 전달 |
| `version` | `metadata.version` | 그대로 전달 |
| `review_status` | 없음 | 생성 대상 필터 |
| `status` | 없음 | 생성 대상 필터 |
| `section_type` | 없음 | v1 Serving에서 불필요 |

## 생성 워크플로우

```text
Authoring JSONL
    |
    | status=ACTIVE
    | review_status=SOURCE_VERIFIED 또는 CLINICALLY_APPROVED
    v
heading + content + keywords 조합
    |
    +-- SHA-256 생성
    +-- 최소 metadata 선택
    v
RAG Serving JSONL
    |
    | text만 임베딩
    v
Vector DB
```

생성 명령:

```bash
python3 scripts/build_screening_rag_serving.py
```

검증 명령:

```bash
python3 -m unittest tests.test_screening_chunks tests.test_screening_rag_serving
```

## 현재 결과

| 항목 | 수량 |
|---|---:|
| Authoring Chunk | 15 |
| `ACTIVE + SOURCE_VERIFIED` | 15 |
| RAG Serving Chunk | 15 |
| 제외된 DRAFT | 0 |
| 연결된 evidence 레코드 | 9 |

Authoring이 변경되면 Serving 파일과 해시가 함께 변경된다. 동기화 테스트가 두 파일의 불일치를 차단한다.
