import hmac
import os
from typing import List, Optional

from fastapi import FastAPI, Header, HTTPException

from .clinical_gate import ClinicalApprovalGate
from .knowledge import KnowledgeRepository
from .llm import GeminiFlashLiteClient, LLMError
from .models import CapabilitySummary, GuidanceDecision, GuidanceRequest, GuidanceResponse
from .retrieval import JsonlEvidenceRetriever
from .routing import CapabilityRouter
from .service import GuidanceService


def create_app(
    repository: Optional[KnowledgeRepository] = None,
    llm: Optional[GeminiFlashLiteClient] = None,
) -> FastAPI:
    knowledge = repository or KnowledgeRepository()
    model = llm or GeminiFlashLiteClient()
    service = GuidanceService(
        router=CapabilityRouter(knowledge),
        gate=ClinicalApprovalGate(knowledge),
        retriever=JsonlEvidenceRetriever(knowledge),
        llm=model,
    )
    app = FastAPI(
        title="Health Guidance API",
        version="0.2.0",
        description="Clinical-approval-gated guidance served by Gemini Flash-Lite.",
    )
    app.state.knowledge = knowledge
    app.state.guidance_service = service

    @app.get("/healthz")
    def health() -> dict:
        return {
            "status": "ok",
            "model": model.model,
            "model_configured": bool(model.api_key),
            "capability_count": len(knowledge.capability_list()),
        }

    @app.get("/v1/capabilities", response_model=List[CapabilitySummary])
    def list_capabilities() -> List[CapabilitySummary]:
        return [CapabilitySummary.model_validate(item) for item in knowledge.capability_list()]

    @app.post("/v1/guidance/route", response_model=GuidanceDecision)
    def route_guidance(request: GuidanceRequest) -> GuidanceDecision:
        try:
            return service.route(request).decision
        except KeyError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    @app.post("/v1/guidance/respond", response_model=GuidanceResponse)
    def respond(request: GuidanceRequest) -> GuidanceResponse:
        try:
            return service.respond(request)
        except KeyError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        except LLMError as exc:
            raise HTTPException(status_code=502, detail=str(exc))

    @app.get("/v1/internal/clinical-reviews")
    def list_clinical_reviews(x_admin_key: Optional[str] = Header(default=None)) -> list:
        _require_admin(x_admin_key)
        return list(knowledge.reviews.values())

    @app.post("/v1/internal/knowledge/reload")
    def reload_knowledge(x_admin_key: Optional[str] = Header(default=None)) -> dict:
        _require_admin(x_admin_key)
        knowledge.reload()
        return {"status": "reloaded", "capability_count": len(knowledge.capability_list())}

    return app


def _require_admin(provided: Optional[str]) -> None:
    expected = os.getenv("GUIDANCE_ADMIN_KEY", "")
    if not expected:
        raise HTTPException(status_code=503, detail="admin API is not configured")
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="invalid admin key")


app = create_app()
