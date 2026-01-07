"""
Document service for uploading and indexing documents.
"""
import re
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from PyPDF2 import PdfReader
from io import BytesIO
from utils.text_utils import split_text_with_headings
from services.storage_service import insert_document, insert_chunks
from config.settings import CHUNK_SIZE
from services.embedding_service import embed_document_chunks

def pdf_to_text(pdf_bytes: bytes) -> str:
    """
    Convert PDF bytes to text.
    
    Args:
        pdf_bytes: PDF file bytes
    
    Returns:
        Extracted text
    """
    pdf_file = BytesIO(pdf_bytes)
    reader = PdfReader(pdf_file)
    
    text_parts = []
    for page in reader.pages:
        text_parts.append(page.extract_text())
    
    return "\n\n".join(text_parts)

def generate_doc_id(filename: str) -> str:
    """
    Generate document ID from filename.
    
    Args:
        filename: Original filename
    
    Returns:
        Sanitized document ID
    """
    doc_id = Path(filename).stem
    doc_id = doc_id.replace(" ", "_").replace("[", "").replace("]", "")
    doc_id = doc_id.replace("-", "_").replace(",", "_")
    while "__" in doc_id:
        doc_id = doc_id.replace("__", "_")
    return doc_id.strip("_")

def upload_and_index_document(
    pdf_bytes: bytes,
    filename: str,
    progress_callback: Optional[Callable[[str], None]] = None
) -> Dict[str, Any]:
    """
    Upload and index a PDF document for keyword search.
    
    Args:
        pdf_bytes: PDF file bytes
        filename: Original filename
        progress_callback: Optional callback for progress updates
    
    Returns:
        Dict with status, message, doc_id
    """
    try:
        # Step 1: Convert PDF to text
        if progress_callback:
            progress_callback("Converting PDF to text...")
        
        text = pdf_to_text(pdf_bytes)
        
        if not text or len(text.strip()) < 10:
            return {'status': 'error', 'message': 'Failed to extract text from PDF or PDF is empty'}
        
        # Step 2: Generate document ID
        doc_id = generate_doc_id(filename)
        
        # Step 3: Split into chunks with headings
        if progress_callback:
            progress_callback("Splitting text into chunks with headings...")
        
        chunks_with_headings = split_text_with_headings(text, chunk_size=CHUNK_SIZE)
        
        if not chunks_with_headings:
            return {'status': 'error', 'message': 'No chunks created from document'}
        
        # Step 4: Prepare chunks for database
        if progress_callback:
            progress_callback("Preparing chunks for indexing...")
        
        chunk_records = []
        for idx, (chunk_text, section_heading) in enumerate(chunks_with_headings):
            chunk_id = f"{doc_id}_{idx}"
            chunk_records.append({
                'chunk_id': chunk_id,
                'doc_id': doc_id,
                'content': chunk_text,
                'section_heading': section_heading,
                'chunk_index': idx,
                'metadata': {}
            })
        
        # Step 5: Store document and chunks
        if progress_callback:
            progress_callback("Storing document and chunks in database...")
        
        insert_document(
            doc_id=doc_id,
            name=filename,
            file_path=filename,
            file_size=len(pdf_bytes),
            full_text=text
        )
        
        chunks_inserted = insert_chunks(doc_id, chunk_records)

        # Step 6: Optional embeddings
        if progress_callback:
            progress_callback("Embedding chunks (optional)...")
        try:
            embedded = embed_document_chunks(doc_id)
        except Exception:
            embedded = 0
        
        if progress_callback:
            progress_callback("Completed")
        
        return {
            'status': 'success',
            'message': f'Document indexed successfully. {chunks_inserted} chunks created. {embedded} embedded.',
            'doc_id': doc_id,
            'chunks_count': chunks_inserted
        }
    
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Error indexing document: {str(e)}'
        }