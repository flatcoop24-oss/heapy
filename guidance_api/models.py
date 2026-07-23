from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GuidanceRequest(BaseModel):
    request_id: UUID = Field(default_factory=uuid4)
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    question: str = Field(min_length=1, max_length=4000)
    requested_capability_id: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    locale: str = "ko-KR"
    dry_run: bool = False


class GuidanceDecision(BaseModel):
    request_id: UUID
    capability_id: str
    risk_level: str
    allowed: bool
    action: str
    policy_id: Optional[str] = None
    clinical_review_id: Optional[str] = None
    protocol_version: Optional[str] = None
    reason: str
    required_context: List[str] = Field(default_factory=list)
    missing_context: List[str] = Field(default_factory=list)


class EvidenceCitation(BaseModel):
    evidence_id: str
    source_id: str
    source_locator: str
    statement: str


class GuidanceResponse(BaseModel):
    request_id: UUID
    decision: GuidanceDecision
    answer: Optional[str] = None
    basis: List[str] = Field(default_factory=list)
    uncertainty: List[str] = Field(default_factory=list)
    next_actions: List[str] = Field(default_factory=list)
    citations: List[EvidenceCitation] = Field(default_factory=list)
    model: Optional[str] = None
    generated_at: datetime = Field(default_factory=utc_now)


class CapabilitySummary(BaseModel):
    capability_id: str
    domain: str
    name: str
    risk_level: str
    clinical_approval_required: bool
    activation_status: str
    status: str

