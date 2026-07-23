import json
import unittest

from ocr_api.backends import ClovaOCRBackend, OCRBackendError


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class ClovaOCRBackendTest(unittest.TestCase):
    def test_calls_v2_json_api_and_parses_fields(self):
        captured = {}

        def opener(request, timeout):
            captured["headers"] = dict(request.header_items())
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return FakeResponse(
                {
                    "version": "V2",
                    "images": [
                        {
                            "inferResult": "SUCCESS",
                            "convertedImageInfo": {"pageIndex": 0},
                            "fields": [
                                {
                                    "inferText": "공복혈당 | 102 | mg/dL",
                                    "inferConfidence": 0.987,
                                    "boundingPoly": {
                                        "vertices": [
                                            {"x": 10, "y": 20},
                                            {"x": 300, "y": 20},
                                            {"x": 300, "y": 60},
                                            {"x": 10, "y": 60},
                                        ]
                                    },
                                }
                            ],
                        }
                    ],
                }
            )

        backend = ClovaOCRBackend(
            invoke_url="https://example.invalid/infer",
            secret="test-secret",
            opener=opener,
        )
        tokens = backend.extract(b"image", "image/png")
        self.assertEqual("V2", captured["payload"]["version"])
        self.assertEqual("ko", captured["payload"]["lang"])
        self.assertTrue(captured["payload"]["images"][0]["data"])
        self.assertEqual("test-secret", captured["headers"]["X-ocr-secret"])
        self.assertEqual(1, len(tokens))
        self.assertEqual("공복혈당 | 102 | mg/dL", tokens[0].text)
        self.assertEqual(0.987, tokens[0].confidence)
        self.assertEqual(1, tokens[0].page)

    def test_missing_configuration_fails_without_leaking_secret(self):
        backend = ClovaOCRBackend(invoke_url="", secret="")
        with self.assertRaisesRegex(OCRBackendError, "not configured"):
            backend.extract(b"image", "image/png")

    def test_failed_inference_is_rejected(self):
        backend = ClovaOCRBackend(
            invoke_url="https://example.invalid/infer",
            secret="secret",
            opener=lambda request, timeout: FakeResponse(
                {"images": [{"inferResult": "FAILURE", "message": "internal detail"}]}
            ),
        )
        with self.assertRaisesRegex(OCRBackendError, "could not recognize"):
            backend.extract(b"image", "image/png")


if __name__ == "__main__":
    unittest.main()
