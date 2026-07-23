# 건강검진 OCR API

기본 운영 백엔드는 NAVER Cloud CLOVA OCR입니다. 이미지/PDF에서 인식한 텍스트와 좌표를
내부 `OCRToken`으로 변환하고, 저장소의 건강검진 결과통보서 필드 사전에 매핑합니다. OCR
값은 사용자가 확인하기 전까지 모두 `REVIEW_REQUIRED`입니다.

## CLOVA 실행

```bash
python3 -m pip install -r requirements-ocr.txt
export OCR_BACKEND=clova
export CLOVA_OCR_INVOKE_URL='CLOVA OCR Builder invoke URL'
export CLOVA_OCR_SECRET='domain secret'
uvicorn ocr_api.main:app --reload
```

서버는 V2 JSON 요청으로 이미지 데이터를 전송합니다. Secret과 invoke URL은 모바일 앱이나
소스코드에 포함하지 않고 배포 환경의 Secret Manager에서 주입합니다.

## 로컬 개발 백엔드

실제 CLOVA 호출 없이 API와 검수 UI를 테스트할 때는 fixture를 사용합니다.

```bash
OCR_BACKEND=fixture uvicorn ocr_api.main:app --reload
```

기존 PaddleOCR 백엔드는 오프라인·장애 대응 실험을 위해 선택적으로 남겨두었습니다.

```bash
python3 -m pip install -r requirements-ocr-paddle.txt
OCR_BACKEND=paddle_vl uvicorn ocr_api.main:app --reload
```

## 요청 흐름

단독 OCR 서비스는 `/v1/ocr-jobs`, 통합 Gateway는 `/ocr/v1/ocr-jobs`를 사용합니다.

```bash
curl -X POST http://127.0.0.1:8000/ocr/v1/ocr-jobs \
  -F 'file=@health-screening.jpg;type=image/jpeg' \
  -F 'screened_on=2026-07-22' \
  -F 'provider_name=검진기관'
```

응답의 `job_id`로 상태와 결과를 조회합니다.

```bash
curl http://127.0.0.1:8000/ocr/v1/ocr-jobs/JOB_ID
curl http://127.0.0.1:8000/ocr/v1/ocr-jobs/JOB_ID/result
```

사용자가 원문과 비교한 항목만 확정합니다.

```json
{
  "accepted_observation_ids": ["OBSERVATION_UUID"],
  "corrections": []
}
```

## 보안 기본값

- 업로드 원본 바이트는 처리 후 메모리에서 제거합니다.
- 주민등록번호와 개인 검진값은 로그나 공용 VDB에 넣지 않습니다.
- OCR 결과는 사용자 확인 전 임상 입력으로 사용하지 않습니다.
- 현재 작업 저장소는 프로세스 메모리 기반입니다. 운영에서는 암호화된 PostgreSQL 작업
  저장소와 별도 worker queue로 교체합니다.
- CLOVA 전송·보관·삭제 정책과 사용자 동의는 실제 계약·배포 리전에 맞춰 확정합니다.
- reverse proxy access log에 multipart body가 기록되지 않게 합니다.

상세 Gateway와 Gemini 연결은 `docs/api-serving.md`를 참고합니다.
