# 건강관리앱 데이터·VDB 골격

이 저장소는 수집 출처부터 벡터 검색까지의 흐름을 세 단계로 분리합니다.

```text
source_registry  ->  source_document  ->  knowledge_chunk
출처 정책             수집한 원문             검색 단위 + embedding
```

Health Guidance 답변 정책과 RAG 원본은 `knowledge/`에서 별도로 관리합니다.

```text
knowledge/capabilities/*.jsonl -> 기능·위험도·활성화 상태
knowledge/reviews/*.jsonl      -> 의료진 승인 게이트
knowledge/policies/*.jsonl     -> Policy Engine
knowledge/evidence/*.jsonl     -> knowledge_chunk -> embedding
```

정책은 조건식으로 실행하고, `embed=true`로 검증된 Evidence만 VDB 후보가 됩니다. 진단지원,
치료 안내, 질환별 운동, 검진 해석, 복약 의사결정, 긴급도 분류는 모두 기능 범위에 포함하되
고위험 기능은 의료진 승인 범위·버전·유효기간을 통과해야 활성화됩니다.
현재 범위와 출처 결정은 [Health Guidance 기준 문서 베이스라인](docs/guidance-policy-baseline.md)을
참고합니다.

## 폴더 구조

```text
건강관리앱/
├── knowledge/
│   ├── sources/
│   ├── evidence/
│   ├── policies/
│   ├── capabilities/
│   ├── reviews/
│   ├── templates/
│   ├── evaluations/
│   └── schemas/
├── database/
│   ├── migrations/
│   │   ├── 000_extensions.sql
│   │   ├── 010_source_registry.sql
│   │   ├── 020_source_document.sql
│   │   ├── 030_knowledge_chunk.sql
│   │   ├── 040_vdb_governance.sql
│   │   ├── 050_screening_dictionary.sql
│   │   ├── 055_labs_item_master.sql
│   │   ├── 060_vdb_retrieval.sql
│   │   ├── 070_screening_output.sql
│   │   ├── 075_user_screening_classification.sql
│   │   ├── 076_normalize_urine_protein_rules.sql
│   │   └── 080_clinical_guidance.sql
│   └── seeds/
│       ├── 010_sources.sql
│       ├── 020_screening_dictionary.sql
│       ├── 025_labs_item_master.sql
│       └── 030_vdb_core.sql
├── docs/
│   ├── official-data-sources.md
│   ├── labs-item-master.md
│   ├── product-safety-boundary.md
│   ├── clinical-governance.md
│   ├── guidance-policy-baseline.md
│   ├── vdb-architecture.md
│   ├── vdb-complete-spec.md
│   └── vdb-source-audit.md
├── storage/
│   └── source_document/
│       ├── mfds_drug_guide/
│       │   ├── raw/
│       │   └── normalized/
│       ├── kdca_health_info/
│       │   ├── raw/
│       │   └── normalized/
│       ├── mohw_screening/
│       │   ├── raw/
│       │   └── normalized/
│       ├── nhis_screening/
│       │   ├── raw/
│       │   └── normalized/
│       └── internal_guides/
│           ├── raw/
│           └── normalized/
├── vdb/
│   ├── corpus/
│   │   └── screening_core_v1.json
│   ├── collectors/
│   ├── normalizers/
│   ├── chunkers/
│   ├── embeddings/
│   └── retrieval/
├── ocr_api/                    # CLOVA OCR 어댑터와 결과 확인 API
├── guidance_api/               # 임상 승인 게이트와 Gemini 응답 API
├── health_api/                 # 두 서비스를 마운트한 통합 Gateway
└── tmp/                         # 임시 다운로드·렌더링 파일
```

`storage/source_document`는 원본 파일을 보존하는 위치이고, PostgreSQL의
`source_document` 테이블은 각 파일의 출처·버전·처리 상태·정규화 본문을 관리합니다.
실제 벡터 검색 대상은 `knowledge_chunk.embedding`입니다.

현재 MVP 코퍼스에는 국가건강검진 핵심 설명 30개가 들어 있습니다. 수치 판정은
`screening_rule`, 설명과 출처는 `knowledge_chunk`, 사용자 원값은
`screening_observation`에서 각각 분리 관리합니다.

## 로컬에서 VDB 실행

```bash
python3 scripts/manage_vdb.py build
python3 scripts/manage_vdb.py search "공복혈당이 높으면 당뇨인가요"
python3 scripts/evaluate_vdb.py
python3 -m unittest discover -s tests -v
```

실제 로컬 벡터 인덱스는 `vdb/index/screening_core_v1.local.json`입니다. 이는 키나 DB가
없는 개발·CI용이고, 운영 환경은 PostgreSQL `knowledge_chunk.embedding`의 pgvector
인덱스를 사용합니다. 개인 검진결과는 어느 인덱스에도 넣지 않습니다.

자세한 데이터 흐름과 실행 순서는 [VDB 아키텍처](docs/vdb-architecture.md)를 참고합니다.
실제 응답을 확인한 공공 API와 원문 다운로드 주소는
[공식 데이터 연동 목록](docs/official-data-sources.md)을 기준으로 사용합니다.
구현된 출력 범위와 실행 순서는 [VDB 완성 사양](docs/vdb-complete-spec.md),
출처별 적재·제외 근거는 [VDB 출처 감사](docs/vdb-source-audit.md)를 참고합니다.

현행 건강검진 규정을 JSON·CSV로 재생성하고 경계값을 검증하는 방법은
[건강검진 실시기준 전처리](docs/screening-regulation-preprocessing.md)를 참고합니다.
국가건강검진 Labs 15종의 항목 원장, 판정 방식, Notion 필드 매핑은
[Labs Item Master](docs/labs-item-master.md)를 참고합니다.

NHIS 집계·청구코드와 일반건강검진 결과통보서를 사용자 관점에서 분리하고 정규화한 방법은
[건강관리 앱 사용자 관점 전처리](docs/nhis-user-centered-preprocessing.md)를 참고합니다.

## 로컬 OCR API

CLOVA OCR로 건강검진 결과지 이미지/PDF를 처리하는 FastAPI 서비스가 `ocr_api/`에 있습니다.
업로드, 작업 상태, 구조화 결과 조회, 사용자 확인 API를 포함합니다.

```bash
python3 -m pip install -r requirements-dev.txt
uvicorn health_api.main:app --reload
python3 -m unittest tests.test_ocr_api -v
```

실제 PaddleOCR 설치와 운영 시 보안 기본값은
[Health API 설계 및 서빙](docs/api-serving.md)을 참고합니다.
