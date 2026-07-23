# Health Guidance 기준 문서

이 디렉터리는 일반 건강관리와 의료 기능의 근거, 실행 정책, 임상 승인 상태를 관리하는 버전
관리 원본(Source of Truth)입니다. 운영 DB와 VDB는 검증된 JSONL에서 생성하는 파생물입니다.

## 원칙

1. 모든 의료 기능은 제품 범위에 포함할 수 있습니다.
2. `policies/`는 정확 조건으로 실행하며 임베딩 결과로 발동시키지 않습니다.
3. `evidence/`는 원문 위치와 적용 대상을 가져야 하며 승인 상태에 따라 검색 범위를 나눕니다.
4. 고위험 기능은 `capabilities/`와 `reviews/`의 임상 승인 게이트를 통과해야 활성화됩니다.
5. 임상 해석이 필요한 Evidence는 `CLINICALLY_APPROVED` 후 임베딩할 수 있습니다.
6. 사용자 건강기록은 공용 지식 VDB와 분리합니다.
7. 승인 범위를 벗어나면 추가 질문, 근거 부족, 의료진 검토, 긴급도 프로토콜 중 하나로
   fail-safe 합니다.

## 구조

```text
knowledge/
├── schemas/                 JSONL 레코드 스키마
├── sources/                 공식·임상 원문과 내부 운영정책
├── evidence/                RAG에 사용할 원자적 근거문
├── policies/                조건·우선순위·허용 출력
├── capabilities/            기능별 위험도와 활성화 상태
├── reviews/                 의료진 검토·승인·만료·철회 기록
├── templates/               정책 action별 응답 계약
└── evaluations/             정책·임상 골든 평가 케이스
```

## 관계

```text
source_id ──> evidence_id ──> VDB
     │             │
     └────────> policy_id ──> Policy Engine
                     │
capability_id <──────┘
     │
clinical_review ──> activation gate
```

## 상태 의미

- `SOURCE_VERIFIED`: 원문과 정규화 내용이 일치함
- `READY_FOR_CLINICAL_REVIEW`: 의료진이 검토할 구조와 자료가 준비됨
- `CLINICALLY_APPROVED`: 지정 범위·버전·유효기간에 대해 의료진 승인 완료
- `SUSPENDED`, `EXPIRED`, `REVOKED`: 운영 검색과 실행에서 즉시 제외

## 현재 v0.2

- 일반 운동, 기록 표시, 공식 의약품 정보는 기존 Source 검증 범위 유지
- 진단지원, 치료 안내, 질환별 운동, 검진 해석, 복약 의사결정, 긴급도 분류는 기능 범위에 포함
- 고위험 기능은 임상 검토 패킷과 활성화 게이트를 먼저 정의
- 실제 임상 승인 값은 의료진 검토 후 기록

세부 경계는 `docs/product-safety-boundary.md`, 운영 방식은
`docs/clinical-governance.md`를 기준으로 합니다.

## 검증

```bash
python3 scripts/validate_guidance_knowledge.py
python3 -m unittest tests.test_guidance_knowledge -v
```
