import unittest

from fastapi.testclient import TestClient

from ocr_api.backends import FixtureOCRBackend, PaddleOCRVLBackend
from ocr_api.dictionary import ScreeningDictionary, normalize_label
from ocr_api.main import create_app
from ocr_api.models import ConfirmationRequest, VerificationStatus
from ocr_api.service import OCRService


FIXTURE = """공복혈당 | 102 | mg/dL | 70~99 | H
AST | 24 | U/L | 0~40 | N
요단백 | 음성 | | 음성 | N
""".encode("utf-8")


class ScreeningDictionaryTest(unittest.TestCase):
    def test_normalize_label_handles_spacing_and_case(self):
        self.assertEqual("hdl콜레스테롤", normalize_label("HDL 콜레스테롤"))

    def test_aliases_map_to_canonical_item(self):
        dictionary = ScreeningDictionary.load_default()
        self.assertEqual("FASTING_GLUCOSE", dictionary.match("공복 혈장 포도당 100").item_code)
        self.assertEqual("SERUM_CREATININE", dictionary.match("Creatinine 0.9").item_code)


class OCRServiceTest(unittest.TestCase):
    def setUp(self):
        self.service = OCRService(FixtureOCRBackend())

    def test_extracts_values_and_keeps_ocr_result_unconfirmed(self):
        job = self.service.submit(FIXTURE, "image/png")
        self.service.process(job.job_id)
        completed = self.service.get(job.job_id)
        self.assertEqual("COMPLETED", completed.status.value)
        self.assertEqual(3, len(completed.result.observations))
        glucose = completed.result.observations[0]
        self.assertEqual("FASTING_GLUCOSE", glucose.item_code)
        self.assertEqual(102, glucose.value_numeric)
        self.assertEqual(70, glucose.reference_range.lower)
        self.assertEqual(99, glucose.reference_range.upper)
        self.assertEqual(VerificationStatus.REVIEW_REQUIRED, glucose.quality.verification_status)

    def test_confirmation_marks_report_only_after_all_items_are_confirmed(self):
        job = self.service.submit(FIXTURE, "image/png")
        self.service.process(job.job_id)
        result = self.service.get(job.job_id).result
        confirmed = self.service.confirm(
            job.job_id,
            ConfirmationRequest(accepted_observation_ids=[item.observation_id for item in result.observations]),
        )
        self.assertEqual(VerificationStatus.USER_CONFIRMED, confirmed.report.verification_status)


class PaddleOCRVLAdapterTest(unittest.TestCase):
    def test_parses_official_reading_order_block_shape(self):
        results = [
            {
                "res": {
                    "parsing_res_list": [
                        {
                            "block_bbox": [10, 20, 500, 120],
                            "block_label": "table",
                            "block_content": "| 검사명 | 결과 | 단위 |\n|---|---:|---|\n| 공복혈당 | 102 | mg/dL |",
                        }
                    ]
                }
            }
        ]
        tokens = PaddleOCRVLBackend._parse_vl(results, page=1)
        self.assertEqual(2, len(tokens))
        self.assertIn("공복혈당", tokens[1].text)
        self.assertEqual(0.90, tokens[1].confidence)


class OCRAPITest(unittest.TestCase):
    def test_upload_job_and_fetch_result(self):
        client = TestClient(create_app(OCRService(FixtureOCRBackend())))
        response = client.post(
            "/v1/ocr-jobs",
            files={"file": ("fixture.png", FIXTURE, "image/png")},
            data={"provider_name": "테스트 검진기관"},
        )
        self.assertEqual(202, response.status_code)
        job_id = response.json()["job_id"]
        result = client.get("/v1/ocr-jobs/%s/result" % job_id)
        self.assertEqual(200, result.status_code)
        self.assertEqual("테스트 검진기관", result.json()["report"]["provider_name"])
        self.assertEqual(3, len(result.json()["observations"]))

    def test_rejects_unsupported_content_type(self):
        client = TestClient(create_app(OCRService(FixtureOCRBackend())))
        response = client.post(
            "/v1/ocr-jobs",
            files={"file": ("fixture.txt", FIXTURE, "text/plain")},
        )
        self.assertEqual(415, response.status_code)


if __name__ == "__main__":
    unittest.main()
