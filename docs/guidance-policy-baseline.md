# Health Guidance 기준 문서 베이스라인 v0.2

기준일: 2026-07-23

## 1. 목적

의료 자문과 임상 검수가 가능한 프로젝트를 전제로 일반 웰니스부터 진단지원, 치료 안내,
질환별 운동, 검진 해석, 복약 의사결정, 응급도 분류까지 확장할 수 있는 기준 계층을 만듭니다.
LLM의 역할은 승인된 정책을 자연어로 실행·설명하는 것이며 임상 기준을 즉석에서 생성하는
것이 아닙니다.

```text
공식·임상 원문
├── Evidence JSONL     원자적 근거와 적용 범위
├── Policy JSONL       조건·우선순위·출력 수준
├── Capability JSONL   기능별 위험도와 활성화 상태
└── Clinical Review    의료진 승인 범위·버전·유효기간
```

## 2. 기능 범위

| 위험도 | 기능 | 기본 상태 |
|---|---|---|
| 낮음 | 일반 운동, 기록 표시, 공식 품목정보 설명 | 출처 검증 후 활성화 가능 |
| 중간 | 개인 맥락을 반영한 생활습관 계획 | 정책 검증 및 필요 시 임상 검수 |
| 높음 | 검진 해석, 위험층화, 질환별 운동, 복약 판단 | 의료진 승인 필수 |
| 치명적 | 긴급도 분류, 중대한 금기·중단 판단 | 별도 승인·모니터링·fail-safe 필수 |

“높음”이나 “치명적”은 제품 범위 밖이라는 뜻이 아닙니다. 승인 단위와 런타임 통제가 더
엄격하다는 뜻입니다.

## 3. 저장 계층

```text
knowledge/sources       출처와 라이선스
knowledge/evidence      RAG 근거문
knowledge/policies      실행 조건과 action
knowledge/capabilities  제공 가능한 의료 기능과 활성화 상태
knowledge/reviews       의료진 검토·승인 기록
knowledge/templates     action별 응답 계약
knowledge/evaluations   개발·골든·임상 평가 사례
```

운영 DB와 VDB는 위 JSONL에서 생성되는 파생물입니다. JSONL의 승인 상태를 우회해 운영
DB에서 직접 기능을 활성화할 수 없도록 배포 검증기를 둡니다.

## 4. 임베딩 정책

- 정책 조건, 숫자 임계치, 금기, 긴급도 분기는 임베딩하지 않습니다.
- 설명 가능한 문장 단위 Evidence만 임베딩합니다.
- 임상 해석 Evidence도 의료진 승인 후 임베딩할 수 있습니다.
- 검색 시 대상군, 관할, 지침 버전, 임상 승인 상태를 메타데이터 필터로 강제합니다.
- 사용자 건강정보는 공용 VDB에 저장하지 않습니다.

현재 v0.2에 포함된 4개 WHO Evidence는 일반 운동용입니다. 고위험 의료 Evidence는 의료진이
원문, 적용 대상, 예외와 표현을 확정한 뒤 추가합니다.

## 5. 정책 우선순위

```text
1000대  승인된 고위험 신호·긴급도 분기
900대   임상 승인 게이트 및 약물 식별 확인
800대   필수 맥락·근거 부족·충돌 처리
600대   승인된 임상 평가·치료·복약·질환별 운동
300대   추가 질문
100대   일반 정보·기록 표시
```

정책 선택은 구조화된 조건 엔진이 담당합니다. 벡터 유사도는 정책을 발동하거나 임상 승인
범위를 확대할 수 없습니다.

## 6. 임상 승인 단위

승인 레코드는 최소한 다음을 고정합니다.

- capability와 policy ID
- 대상 인구집단과 제외 대상
- 필수 입력과 허용 출력
- Evidence·규칙·템플릿 버전
- 의료 전문분야와 검토 역할
- 승인일, 유효기간, 변경·철회 이력
- 골든셋과 허용 오류 한계

현재 고위험 capability는 `READY_FOR_CLINICAL_REVIEW`로 설계합니다. 실제 의료진의 검토 결과가
들어오기 전에는 `CLINICALLY_APPROVED`로 표시하지 않습니다.

## 7. 전체 런타임 흐름

```text
사용자 질문
  → 의도·위험 신호 구조화
  → 필수 Context 확인
  → Capability/Clinical Review 게이트
  → 정확 규칙 실행
  → 승인된 Evidence만 Hybrid Retrieval
  → LLM 응답 생성
  → Claim·Citation·Policy Validator
  → 답변 및 감사 로그
```

## 8. 기존 VDB와 연결

```text
knowledge/sources      → source_registry/source_document
knowledge/evidence     → knowledge_chunk → embedding
knowledge/policies     → guidance_policy → Policy Engine
knowledge/capabilities → clinical_capability
knowledge/reviews      → clinical_approval
```

기존 `vdb/corpus/screening_core_v1.json`의 숫자 규칙은 계속 관계형 규칙으로 실행합니다. 설명
청크는 새 Evidence 규격과 임상 승인 상태를 부여한 뒤 VDB에 이관합니다.

## 9. 현재와 다음 단계

현재 단계는 임상 기능 전체를 담을 수 있는 문서·스키마·게이트의 v0.2 전환입니다. 다음으로
의료진과 영역별 프로토콜을 채웁니다.

1. 검진·운동·복약·증상분류의 의료 전문분야와 검토자를 지정합니다.
2. 질환별 공식 지침을 Source Registry에 등록합니다.
3. 원문에서 Evidence, 정확 규칙, 예외와 중단 조건을 추출합니다.
4. 의료진이 정책과 골든셋을 함께 승인합니다.
5. 승인된 capability만 DB seed와 VDB corpus에 포함합니다.
6. 오프라인 평가와 shadow mode를 통과한 뒤 운영에서 활성화합니다.

## 10. 검증

```bash
python3 scripts/validate_guidance_knowledge.py
python3 -m unittest tests.test_guidance_knowledge -v
```

검증기는 ID·출처·정책·템플릿 참조뿐 아니라 고위험 정책이 임상 승인 없이 활성화되지
않는지도 확인합니다.
