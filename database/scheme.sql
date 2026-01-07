-- ============================================================================
-- Keyword Extractor Database Schema
-- ============================================================================

-- Enable pgvector extension (if using Supabase)
CREATE EXTENSION IF NOT EXISTS vector;
-- UUID generation
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Keyword Documents table
CREATE TABLE IF NOT EXISTS keyword_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    file_path TEXT,
    file_size BIGINT,
    full_text TEXT,
    chunks_count INTEGER DEFAULT 0,
    indexed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Keyword Chunks table
CREATE TABLE IF NOT EXISTS keyword_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id TEXT UNIQUE NOT NULL,
    doc_id TEXT NOT NULL REFERENCES keyword_documents(doc_id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    section_heading TEXT,
    chunk_index INTEGER,
    metadata JSONB,
    -- Optional: semantic embedding for vector search
    embedding vector(1536),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Full-text search indexes
CREATE INDEX IF NOT EXISTS keyword_chunks_content_fts_idx 
ON keyword_chunks USING GIN (to_tsvector('english', content));

CREATE INDEX IF NOT EXISTS keyword_documents_fulltext_fts_idx 
ON keyword_documents USING GIN (to_tsvector('english', full_text));

CREATE INDEX IF NOT EXISTS keyword_documents_name_fts_idx 
ON keyword_documents USING GIN (to_tsvector('english', name));

CREATE INDEX IF NOT EXISTS keyword_chunks_section_heading_idx 
ON keyword_chunks(section_heading);

CREATE INDEX IF NOT EXISTS keyword_chunks_doc_id_idx 
ON keyword_chunks(doc_id);

CREATE INDEX IF NOT EXISTS keyword_chunks_index_idx 
ON keyword_chunks(doc_id, chunk_index);

-- Optional: vector index for embeddings (requires pgvector >= 0.4.0)
-- You can tune 'lists' based on data size
CREATE INDEX IF NOT EXISTS keyword_chunks_embedding_idx
ON keyword_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Function to update document chunks count
CREATE OR REPLACE FUNCTION update_keyword_document_chunks_count()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE keyword_documents
    SET chunks_count = (
        SELECT COUNT(*) FROM keyword_chunks WHERE doc_id = NEW.doc_id
    ),
    updated_at = NOW()
    WHERE doc_id = NEW.doc_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update chunks count
CREATE TRIGGER update_keyword_chunks_count
AFTER INSERT OR DELETE ON keyword_chunks
FOR EACH ROW
EXECUTE FUNCTION update_keyword_document_chunks_count();

-- Keyword search function
CREATE OR REPLACE FUNCTION keyword_search_documents(
    search_query TEXT,
    match_count INTEGER DEFAULT 100,
    doc_id_filter TEXT DEFAULT NULL
)
RETURNS TABLE (
    doc_id TEXT,
    doc_name TEXT,
    content TEXT,
    section_heading TEXT,
    relevance REAL,
    chunk_id TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    WITH search_results AS (
        -- Search in document titles
        SELECT 
            kd.doc_id,
            kd.name as doc_name,
            kd.name as content,
            NULL::TEXT as section_heading,
            ts_rank(to_tsvector('english', kd.name), plainto_tsquery('english', search_query)) as relevance,
            NULL::TEXT as chunk_id
        FROM keyword_documents kd
        WHERE 
            (doc_id_filter IS NULL OR kd.doc_id = doc_id_filter)
            AND to_tsvector('english', kd.name) @@ plainto_tsquery('english', search_query)
        
        UNION ALL
        
        -- Search in chunk content
        SELECT 
            kc.doc_id,
            kd.name as doc_name,
            kc.content,
            kc.section_heading,
            ts_rank(to_tsvector('english', kc.content), plainto_tsquery('english', search_query)) as relevance,
            kc.chunk_id
        FROM keyword_chunks kc
        JOIN keyword_documents kd ON kc.doc_id = kd.doc_id
        WHERE 
            (doc_id_filter IS NULL OR kc.doc_id = doc_id_filter)
            AND to_tsvector('english', kc.content) @@ plainto_tsquery('english', search_query)
        
        UNION ALL
        
        -- Search in document full_text
        SELECT 
            kd.doc_id,
            kd.name as doc_name,
            substring(kd.full_text, 1, 500) as content,
            NULL::TEXT as section_heading,
            ts_rank(to_tsvector('english', kd.full_text), plainto_tsquery('english', search_query)) as relevance,
            NULL::TEXT as chunk_id
        FROM keyword_documents kd
        WHERE 
            (doc_id_filter IS NULL OR kd.doc_id = doc_id_filter)
            AND kd.full_text IS NOT NULL
            AND to_tsvector('english', kd.full_text) @@ plainto_tsquery('english', search_query)
    )
    SELECT 
        sr.doc_id,
        sr.doc_name,
        sr.content,
        sr.section_heading,
        MAX(sr.relevance)::REAL as relevance,
        sr.chunk_id
    FROM search_results sr
    WHERE sr.relevance > 0
    GROUP BY sr.doc_id, sr.doc_name, sr.content, sr.section_heading, sr.chunk_id
    ORDER BY relevance DESC
    LIMIT match_count;
END;
$$;