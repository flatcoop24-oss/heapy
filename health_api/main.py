from fastapi import FastAPI

from guidance_api.main import create_app as create_guidance_app
from ocr_api.main import create_app as create_ocr_app


app = FastAPI(
    title="Heapy Health API Gateway",
    version="0.2.0",
    description="Unified gateway for CLOVA OCR and policy-gated Gemini health guidance.",
)


@app.get("/healthz")
def health() -> dict:
    return {"status": "ok", "services": ["ocr", "guidance"]}


app.mount("/ocr", create_ocr_app())
app.mount("/guidance", create_guidance_app())
