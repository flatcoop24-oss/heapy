# source_document 파일 보관 규칙

DB의 `source_document` 한 건과 여기의 원본 파일 한 개가 추적 가능해야 합니다.

```text
source_document/
├── mfds_drug_guide/    # e약은요: VDB 대상
├── kdca_health_info/   # 질병관리청: 허가 확인 전 적재 중지
├── mohw_screening/     # 검진 판정기준: 관계형 DB 대상
├── nhis_screening/     # 건보공단 검사항목 코드·집계 API 원본
└── internal_guides/    # 자체 FAQ·안전 안내: VDB 대상
```

각 출처 아래에서 `raw`는 받은 그대로, `normalized`는 정제한 결과를 보관합니다.

권장 파일명:

```text
YYYY-MM-DD__외부문서ID__v버전.확장자
2026-07-16__MFDS-200410018__v1.json
```

- 원본 파일은 수정하지 않습니다.
- 재수집한 내용이 달라지면 덮어쓰지 않고 새 버전을 만듭니다.
- SHA-256 체크섬을 `source_document.checksum_sha256`에 기록합니다.
- 개인정보가 포함된 사용자 검사결과나 처방전은 이 폴더에 넣지 않습니다.
- `KDCA_HEALTH_INFO`는 사용 허가가 확인되기 전까지 운영 VDB로 처리하지 않습니다.

현재 보존한 판정 원문:

```text
mohw_screening/raw/2026-01-07__MOHW-2026-6__v2026-6.pdf
SHA-256 5f804efa7257c067eabe8084cff6b9fb3d140f8f33e10234fc5423351f6ed11a
```
