"""Health-screening OCR domain package.

Import ``create_app`` from ``ocr_api.main`` when the HTTP layer is needed.
Keeping package import side-effect free allows backend and parser tests to run
without loading FastAPI multipart support.
"""
