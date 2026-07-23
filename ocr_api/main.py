import os
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile, status

from .backends import build_backend
from .models import ConfirmationRequest, JobStatus, OCRJob, OCRResult
from .service import JobConflict, JobNotFound, OCRService


ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
MAX_UPLOAD_BYTES = int(os.getenv("OCR_MAX_UPLOAD_BYTES", str(20 * 1024 * 1024)))


def create_app(service: Optional[OCRService] = None) -> FastAPI:
    active_service = service or OCRService(build_backend(os.getenv("OCR_BACKEND", "clova")))
    app = FastAPI(
        title="Health Screening OCR API",
        version="0.2.0",
        description="CLOVA OCR extraction with deterministic health-field normalization and user confirmation.",
    )
    app.state.ocr_service = active_service

    @app.get("/healthz")
    def health() -> dict:
        return {"status": "ok", "backend": active_service.backend.name}

    @app.post("/v1/ocr-jobs", response_model=OCRJob, status_code=status.HTTP_202_ACCEPTED)
    async def create_job(
        background_tasks: BackgroundTasks,
        file: UploadFile = File(...),
        client_user_id: Optional[str] = Form(default=None),
        screened_on: Optional[date] = Form(default=None),
        provider_name: Optional[str] = Form(default=None),
    ) -> OCRJob:
        content_type = (file.content_type or "").casefold()
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(status_code=415, detail="JPEG, PNG, WEBP, or PDF is required")
        content = await file.read(MAX_UPLOAD_BYTES + 1)
        await file.close()
        if not content:
            raise HTTPException(status_code=400, detail="empty file")
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="file is too large")
        job = active_service.submit(
            content=content,
            content_type=content_type,
            client_user_id=client_user_id,
            screened_on=screened_on,
            provider_name=provider_name,
        )
        background_tasks.add_task(active_service.process, job.job_id)
        return job

    @app.get("/v1/ocr-jobs/{job_id}", response_model=OCRJob)
    def get_job(job_id: UUID) -> OCRJob:
        try:
            return active_service.get(job_id)
        except JobNotFound:
            raise HTTPException(status_code=404, detail="job not found")

    @app.get("/v1/ocr-jobs/{job_id}/result", response_model=OCRResult)
    def get_result(job_id: UUID) -> OCRResult:
        try:
            job = active_service.get(job_id)
        except JobNotFound:
            raise HTTPException(status_code=404, detail="job not found")
        if job.status == JobStatus.FAILED:
            raise HTTPException(status_code=422, detail={"code": job.error_code, "message": job.error_message})
        if job.status != JobStatus.COMPLETED or job.result is None:
            raise HTTPException(status_code=409, detail="job is not completed")
        return job.result

    @app.post("/v1/ocr-jobs/{job_id}/confirm", response_model=OCRResult)
    def confirm_result(job_id: UUID, request: ConfirmationRequest) -> OCRResult:
        try:
            return active_service.confirm(job_id, request)
        except JobNotFound:
            raise HTTPException(status_code=404, detail="job not found")
        except JobConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc))

    return app


app = create_app()
