"""
Storage service for keyword extractor.
"""
from typing import List, Dict, Optional, Any
from database.connection import get_supabase_client

def insert_document(
    doc_id: str,
    name: str,
    file_path: Optional[str] = None,
    file_size: Optional[int] = None,
    full_text: Optional[str] = None
) -> Dict[str, Any]:
    """Insert or update a keyword document."""
    client = get_supabase_client(use_service_key=True)
    
    result = client.table('keyword_documents').upsert({
        'doc_id': doc_id,
        'name': name,
        'file_path': file_path,
        'file_size': file_size,
        'full_text': full_text,
    }).execute()
    
    return result.data[0] if result.data else None

def insert_chunks(
    doc_id: str,
    chunks: List[Dict[str, Any]]
) -> int:
    """
    Insert keyword chunks for a document.
    
    Args:
        doc_id: Document ID
        chunks: List of dicts with keys: chunk_id, content, section_heading, chunk_index
    
    Returns:
        Number of chunks inserted
    """
    client = get_supabase_client(use_service_key=True)
    
    # Delete existing chunks for this document
    client.table('keyword_chunks').delete().eq('doc_id', doc_id).execute()
    
    # Insert new chunks
    if chunks:
        result = client.table('keyword_chunks').insert(chunks).execute()
        return len(result.data) if result.data else 0
    return 0

def list_documents() -> List[Dict[str, Any]]:
    """List all keyword documents."""
    client = get_supabase_client()
    
    result = client.table('keyword_documents').select('*').order('name').execute()
    return result.data if result.data else []

def delete_document(doc_id: str) -> bool:
    """Delete a keyword document and all its chunks."""
    client = get_supabase_client(use_service_key=True)
    
    result = client.table('keyword_documents').delete().eq('doc_id', doc_id).execute()
    return len(result.data) > 0 if result.data else False