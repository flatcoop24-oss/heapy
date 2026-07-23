-- 키워드와 벡터를 함께 사용하고, 라이선스·버전·검수 게이트를 강제하는 검색 함수입니다.
CREATE OR REPLACE FUNCTION search_knowledge(
    p_query TEXT,
    p_query_embedding VECTOR(1536) DEFAULT NULL,
    p_route VARCHAR DEFAULT 'SIMPLE_LOOKUP',
    p_domain VARCHAR DEFAULT NULL,
    p_limit INTEGER DEFAULT 5
)
RETURNS TABLE (
    chunk_id UUID,
    canonical_key VARCHAR,
    heading TEXT,
    content TEXT,
    domain VARCHAR,
    safety_level VARCHAR,
    evidence JSONB,
    source_title TEXT,
    source_url TEXT,
    citation_label TEXT,
    score DOUBLE PRECISION
)
LANGUAGE SQL
STABLE
AS $$
    WITH gated AS (
        SELECT
            kc.*,
            sd.title AS source_title,
            sd.source_url,
            sd.citation_label,
            CASE
                WHEN trim(COALESCE(p_query, '')) = '' THEN 0.0
                ELSE ts_rank_cd(
                    to_tsvector('simple', kc.search_text),
                    plainto_tsquery('simple', p_query)
                )::DOUBLE PRECISION
            END AS keyword_score,
            CASE
                WHEN p_query_embedding IS NULL OR kc.embedding IS NULL THEN 0.0
                ELSE GREATEST(0.0, 1.0 - (kc.embedding <=> p_query_embedding))::DOUBLE PRECISION
            END AS vector_score
        FROM knowledge_chunk kc
        JOIN source_document sd ON sd.id = kc.source_document_id
        JOIN source_registry sr ON sr.id = sd.source_id
        WHERE kc.is_retrievable = TRUE
          AND sd.is_retrievable = TRUE
          AND sr.is_active = TRUE
          AND sr.license_status = 'APPROVED'
          AND UPPER(p_route) = ANY(kc.route_scope)
          AND (p_domain IS NULL OR kc.domain = UPPER(p_domain))
          AND (kc.valid_from IS NULL OR CURRENT_DATE >= kc.valid_from)
          AND (kc.valid_to IS NULL OR CURRENT_DATE <= kc.valid_to)
          AND (sd.effective_from IS NULL OR CURRENT_DATE >= sd.effective_from)
          AND (sd.effective_to IS NULL OR CURRENT_DATE <= sd.effective_to)
          AND sd.review_status IN ('SOURCE_VERIFIED', 'CLINICALLY_APPROVED')
          AND (
              (
                  UPPER(p_route) IN ('COMPREHENSIVE_ANALYSIS', 'PROACTIVE_CARE')
                  AND kc.review_status = 'CLINICALLY_APPROVED'
                  AND sd.clinical_review_status = 'APPROVED'
              )
              OR (
                  UPPER(p_route) NOT IN ('COMPREHENSIVE_ANALYSIS', 'PROACTIVE_CARE')
                  AND kc.review_status IN ('SOURCE_VERIFIED', 'CLINICALLY_APPROVED')
              )
          )
    )
    SELECT
        g.id,
        g.canonical_key,
        g.heading,
        g.content,
        g.domain,
        g.safety_level,
        COALESCE(g.metadata -> 'evidence', '[]'::JSONB),
        g.source_title,
        g.source_url,
        g.citation_label,
        CASE
            WHEN p_query_embedding IS NULL THEN g.keyword_score
            ELSE (0.75 * g.vector_score) + (0.25 * LEAST(g.keyword_score, 1.0))
        END AS score
    FROM gated g
    WHERE g.keyword_score > 0 OR g.vector_score > 0
    ORDER BY score DESC, g.chunk_index ASC
    LIMIT GREATEST(1, LEAST(p_limit, 20));
$$;

COMMENT ON FUNCTION search_knowledge IS
    'SIMPLE_LOOKUP은 출처검증 청크를 허용하고, 종합분석·선제케어는 임상검수 완료 청크만 반환';

