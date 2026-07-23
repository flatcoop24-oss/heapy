# VDB 파이프라인 모듈

애플리케이션 언어와 프레임워크를 정하면 아래 경계에 맞춰 구현 파일을 배치합니다.

| 폴더 | 책임 |
|---|---|
| `collectors` | API·PDF·내부 문서를 수집하고 `source_document`를 생성 |
| `normalizers` | 출처별 원문을 공통 텍스트와 메타데이터로 변환 |
| `chunkers` | 제목과 의미 단위로 나누어 `knowledge_chunk`를 생성 |
| `embeddings` | 임베딩 생성, 모델명과 처리 시각 기록 |
| `retrieval` | pgvector 검색, 메타데이터 필터, 출처 반환 |

처리 순서를 건너뛰고 PDF나 API 응답을 바로 임베딩하지 않습니다. 원문과 버전을
`source_document`에서 먼저 확정해야 잘못된 청크를 찾아 재처리할 수 있습니다.

`corpus/screening_core_v1.json`은 MVP용 자체 설명 30개입니다. 판정 수치는 포함하지 않으며
각 청크가 실제 근거 URL과 문서 위치를 갖습니다. `scripts/build_vdb_seed.py`가 이를 검증하고
`database/seeds/030_vdb_core.sql`로 변환합니다.

임베딩 작업은 `embeddings/embed_pending.py`를 사용합니다. 이 워커는 활성·라이선스 승인·
출처검증 완료 조건을 모두 통과한 `knowledge_chunk`만 외부 임베딩 API로 전송하며,
`screening_observation`의 개인 건강정보는 선택하지 않습니다.

## 바로 실행 가능한 로컬 VDB

PostgreSQL이나 외부 임베딩 키가 없는 개발 환경에서는 재현 가능한 1536차원 로컬 인덱스를
사용합니다. 한국어 단어와 글자 n-gram을 feature hashing한 개발·CI용 인덱스이며, 운영용
의미 임베딩을 대체하지 않습니다.

```bash
python3 scripts/manage_vdb.py build
python3 scripts/manage_vdb.py search "공복혈당이 높으면 당뇨인가요"
python3 scripts/manage_vdb.py get FASTING_GLUCOSE
python3 scripts/evaluate_vdb.py
```

생성되는 실제 VDB 파일은 `index/screening_core_v1.local.json`, 구조 품질 결과는
`reports/screening_core_v1_quality.json`, 검색 회귀평가는
`reports/retrieval_evaluation.json`입니다. VS Code에서는 `Terminal > Run Task`에서
`VDB: Build + Quality Audit`, `VDB: Search`, `VDB: Test`를 실행할 수 있습니다.

운영에서는 기존 `database/migrations`와 `database/seeds`를 PostgreSQL에 적용하고
`embeddings/embed_pending.py`로 승인된 청크만 pgvector에 임베딩합니다.
