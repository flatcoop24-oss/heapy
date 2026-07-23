-- 의료진 승인 capability와 LLM 응답 감사 정보를 운영 DB에서 강제합니다.
-- JSONL은 버전 관리 원본이고 이 테이블은 검증된 배포 산출물입니다.

CREATE TABLE IF NOT EXISTS clinical_capability (
    capability_id              VARCHAR(100) PRIMARY KEY,
    domain                     VARCHAR(40) NOT NULL,
    name                       VARCHAR(200) NOT NULL,
    risk_level                 VARCHAR(20) NOT NULL
                                   CHECK (risk_level IN ('LOW', 'MODERATE', 'HIGH', 'CRITICAL')),
    clinical_approval_required BOOLEAN NOT NULL,
    activation_status          VARCHAR(40) NOT NULL
                                   CHECK (activation_status IN (
                                       'ACTIVE_SOURCE_VERIFIED', 'DESIGNED',
                                       'READY_FOR_CLINICAL_REVIEW', 'CLINICALLY_APPROVED',
                                       'SUSPENDED', 'RETIRED'
                                   )),
    runtime_fail_action         VARCHAR(60) NOT NULL,
    capability_version         VARCHAR(40) NOT NULL,
    is_active                  BOOLEAN NOT NULL DEFAULT FALSE,
    metadata                   JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (
        clinical_approval_required = FALSE
        OR activation_status <> 'ACTIVE_SOURCE_VERIFIED'
    )
);

CREATE TABLE IF NOT EXISTS clinical_approval (
    approval_id                VARCHAR(120) PRIMARY KEY,
    capability_id              VARCHAR(100) NOT NULL
                                   REFERENCES clinical_capability(capability_id) ON DELETE RESTRICT,
    decision                   VARCHAR(30) NOT NULL
                                   CHECK (decision IN (
                                       'PENDING', 'CHANGES_REQUESTED', 'APPROVED',
                                       'REJECTED', 'EXPIRED', 'REVOKED'
                                   )),
    reviewer_refs              TEXT[] NOT NULL DEFAULT '{}',
    policy_ids                 TEXT[] NOT NULL DEFAULT '{}',
    evidence_ids               TEXT[] NOT NULL DEFAULT '{}',
    evaluation_case_ids        TEXT[] NOT NULL DEFAULT '{}',
    protocol_version           VARCHAR(80),
    evidence_version           VARCHAR(80),
    decision_rationale         TEXT,
    constraints                JSONB NOT NULL DEFAULT '[]'::JSONB,
    decided_at                 DATE,
    valid_from                 DATE,
    valid_until                DATE,
    approval_version           VARCHAR(40) NOT NULL,
    is_active                  BOOLEAN NOT NULL DEFAULT TRUE,
    created_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from),
    CHECK (
        decision <> 'APPROVED'
        OR (
            cardinality(reviewer_refs) > 0
            AND cardinality(policy_ids) > 0
            AND cardinality(evidence_ids) > 0
            AND cardinality(evaluation_case_ids) > 0
            AND protocol_version IS NOT NULL
            AND evidence_version IS NOT NULL
            AND decision_rationale IS NOT NULL
            AND decided_at IS NOT NULL
            AND valid_from IS NOT NULL
            AND valid_until IS NOT NULL
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_clinical_approval_gate
    ON clinical_approval (capability_id, decision, is_active, valid_from, valid_until);

CREATE TABLE IF NOT EXISTS guidance_response_audit (
    response_id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id                  UUID NOT NULL,
    user_id                     UUID,
    capability_id               VARCHAR(100) NOT NULL
                                    REFERENCES clinical_capability(capability_id) ON DELETE RESTRICT,
    policy_id                   VARCHAR(120),
    approval_id                 VARCHAR(120)
                                    REFERENCES clinical_approval(approval_id) ON DELETE RESTRICT,
    risk_level                  VARCHAR(20) NOT NULL,
    action                      VARCHAR(60) NOT NULL,
    allowed                     BOOLEAN NOT NULL,
    model_id                    VARCHAR(100),
    model_request_id            VARCHAR(200),
    evidence_ids                TEXT[] NOT NULL DEFAULT '{}',
    source_ids                  TEXT[] NOT NULL DEFAULT '{}',
    prompt_contract_version     VARCHAR(40),
    question_sha256             CHAR(64),
    encrypted_context           BYTEA,
    response_claims             JSONB NOT NULL DEFAULT '[]'::JSONB,
    error_code                  VARCHAR(80),
    latency_ms                  INTEGER CHECK (latency_ms IS NULL OR latency_ms >= 0),
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_guidance_response_audit_user_date
    ON guidance_response_audit (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_guidance_response_audit_capability_date
    ON guidance_response_audit (capability_id, created_at DESC);

CREATE OR REPLACE FUNCTION clinical_capability_is_approved(
    p_capability_id VARCHAR,
    p_policy_id VARCHAR,
    p_as_of DATE DEFAULT CURRENT_DATE
)
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM clinical_capability c
        JOIN clinical_approval a ON a.capability_id = c.capability_id
        WHERE c.capability_id = p_capability_id
          AND c.clinical_approval_required = TRUE
          AND c.activation_status = 'CLINICALLY_APPROVED'
          AND c.is_active = TRUE
          AND a.decision = 'APPROVED'
          AND a.is_active = TRUE
          AND p_policy_id = ANY(a.policy_ids)
          AND p_as_of BETWEEN a.valid_from AND a.valid_until
    );
$$;

COMMENT ON FUNCTION clinical_capability_is_approved IS
    '고위험 LLM 요청 전에 capability, policy, 승인 상태와 유효기간을 함께 검증한다';

