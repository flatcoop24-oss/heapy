# Health API 설계 및 서빙

## 1. 배포 구성

```text
Mobile App
   │
   ▼
Health API Gateway
   ├── /ocr/*       → CLOVA OCR → 검진항목 정규화 → 사용자 확인
   └── /guidance/*  → Router → Clinical Gate → Evidence → Gemini Flash-Lite
```

외부 API 키는 모바일 앱에 넣지 않습니다. CLOVA와 Gemini 호출은 서버에서만 수행합니다.

## 2. 실행

```bash
python3 -m pip install -r requirements-dev.txt
cp config.example.env .env
# .env 값을 안전한 비밀 저장소에서 주입한 뒤
uvicorn health_api.main:app --host 0.0.0.0 --port 8000 --env-file .env
```

프로덕션에서는 `.env` 파일 대신 배포 플랫폼의 Secret Manager를 사용합니다.

## 3. 공개 API

| Method | Endpoint | 역할 |
|---|---|---|
| `GET` | `/healthz` | Gateway 상태 |
| `POST` | `/ocr/v1/ocr-jobs` | 검진표 이미지·PDF OCR 작업 생성 |
| `GET` | `/ocr/v1/ocr-jobs/{job_id}` | OCR 상태 조회 |
| `GET` | `/ocr/v1/ocr-jobs/{job_id}/result` | 정규화된 검진항목 조회 |
| `POST` | `/ocr/v1/ocr-jobs/{job_id}/confirm` | 사용자 OCR 결과 확인·수정 |
| `GET` | `/guidance/v1/capabilities` | 제공 기능과 활성화 상태 조회 |
| `POST` | `/guidance/v1/guidance/route` | capability·정책·승인 게이트 결과 조회 |
| `POST` | `/guidance/v1/guidance/respond` | 승인 범위의 최종 Health Guidance 생성 |

FastAPI가 `/docs`에 Gateway 문서를, 각 하위 앱의 `/ocr/docs`, `/guidance/docs`에 상세 OpenAPI
문서를 제공합니다.

## 4. 내부 운영 API

| Method | Endpoint | 인증 |
|---|---|---|
| `GET` | `/guidance/v1/internal/clinical-reviews` | `X-Admin-Key` |
| `POST` | `/guidance/v1/internal/knowledge/reload` | `X-Admin-Key` |

운영에서 승인 레코드를 직접 수정하는 API는 제공하지 않습니다. 의료진 승인 내용은 검토된
JSONL 또는 운영 DB 배포 절차로 반영하고 검증기를 통과시킨 뒤 reload 합니다.

## 5. 고위험 응답 조건

다음 조건을 모두 만족해야 Gemini가 호출됩니다.

1. capability가 `CLINICALLY_APPROVED`이며 `ACTIVE`
2. 임상 review가 `APPROVED`이고 유효기간 내
3. 실제 검토자 참조와 프로토콜·Evidence 버전이 존재
4. 선택 Policy가 review의 `policy_ids`에 포함
5. Policy가 `CLINICALLY_APPROVED`이며 `ACTIVE`
6. 필수 사용자 Context가 모두 존재
7. review 범위에 포함된 `CLINICALLY_APPROVED` Evidence가 검색됨

하나라도 실패하면 Gemini를 호출하지 않고 `ASK_CONTEXT`, `CLINICAL_REVIEW_REQUIRED`,
`INSUFFICIENT_EVIDENCE`, `SAFETY_ESCALATION` 중 하나를 반환합니다.

## 6. 요청 예시

```json
{
  "question": "고혈압에 맞춰 오늘 운동 강도를 정해줘",
  "requested_capability_id": "CAP_CONDITION_SPECIFIC_EXERCISE",
  "context": {
    "condition": "HYPERTENSION",
    "current_symptoms": [],
    "functional_status": "INDEPENDENT",
    "medications": ["verified-medication-id"],
    "professional_restrictions": [],
    "available_equipment": ["MAT"]
  }
}
```

현재 실제 승인 데이터가 없으면 이 요청은 `CLINICAL_REVIEW_REQUIRED`를 반환합니다. 승인된
정책·근거·평가셋이 배포되면 동일 API가 `PROVIDE_CONDITION_SPECIFIC_PLAN`으로 응답합니다.

## 7. 외부 어댑터

### CLOVA OCR

- V2 JSON API
- `X-OCR-SECRET` 서버 헤더
- 이미지·PDF를 base64 `images.data`로 전송
- `inferText`, `inferConfidence`, `boundingPoly`를 내부 OCRToken으로 변환
- 추출값은 사용자 확인 전 임상 입력으로 사용하지 않음

### Gemini Flash-Lite

- 기본 모델: `gemini-3.5-flash-lite`
- REST `models/{model}:generateContent`
- `responseMimeType=application/json`
- 낮은 temperature와 고정 응답 계약 사용
- 사용자 ID·대화 ID는 모델 프롬프트에서 제외
- 승인된 Policy·Evidence·Context만 전달

## 8. DB

`database/migrations/080_clinical_guidance.sql`은 capability, 임상 승인, 응답 감사 테이블과
`clinical_capability_is_approved()` 게이트 함수를 추가합니다. 운영 전 JSONL → DB seed 생성과
애플리케이션 저장소 어댑터를 연결해야 합니다.
