"""
Document service for uploading and indexing documents.
"""
import re
import string
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from io import BytesIO
import tempfile
import os
from utils.text_utils import split_by_sections
from services.storage_service import insert_document, insert_chunks
from config.settings import CHUNK_SIZE
from services.embedding_service import embed_document_chunks

# Control characters to clean from markdown
_CONTROL_CHARS = {
    *[c for c in map(chr, range(0x00, 0x20)) if c not in ("\t", "\n", "\r")],
    chr(0x7F),
    "\uFFFD",  # Replacement character
}
_CONTROL_TRANSLATION = {ord(c): None for c in _CONTROL_CHARS}


def clean_markdown(text: str) -> str:
    """Remove non-printable/control artifacts while preserving content & layout."""
    cleaned = text.translate(_CONTROL_TRANSLATION)
    return cleaned.encode("utf-8", "ignore").decode("utf-8")


def pdf_to_markdown(pdf_bytes: bytes) -> str:
    """
    Convert PDF bytes to markdown using Docling.
    Preserves structure and headings for better section detection.
    
    Args:
        pdf_bytes: PDF file bytes
    
    Returns:
        Markdown text with preserved structure
    """
    try:
        from docling.document_converter import DocumentConverter
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(pdf_bytes)
            tmp_path = tmp_file.name
        
        try:
            # Convert to markdown
            converter = DocumentConverter()
            result = converter.convert(tmp_path)
            markdown = result.document.export_to_markdown()
            markdown = clean_markdown(markdown)
            return markdown
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    except ImportError:
        # Fallback to simple text extraction if docling not available
        from PyPDF2 import PdfReader
        pdf_file = BytesIO(pdf_bytes)
        reader = PdfReader(pdf_file)
        text_parts = []
        for page in reader.pages:
            text_parts.append(page.extract_text())
        return "\n\n".join(text_parts)
    except Exception as e:
        # Fallback on any error
        print(f"Warning: Docling conversion failed, using fallback: {e}")
        from PyPDF2 import PdfReader
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
        # Step 1: Convert PDF to markdown (preserves structure)
        if progress_callback:
            progress_callback("Converting PDF to markdown...")
        
        text = pdf_to_markdown(pdf_bytes)
        
        if not text or len(text.strip()) < 10:
            return {'status': 'error', 'message': 'Failed to extract text from PDF or PDF is empty'}
        
        # Step 2: Generate document ID
        doc_id = generate_doc_id(filename)
        
        # Step 3: Split into sections first, then chunk each section
        if progress_callback:
            progress_callback("Splitting document into sections, then chunking each section...")
        
        # First split into sections, then chunk each section using size-based chunking
        chunks_with_headings = split_by_sections(text, chunk_size=CHUNK_SIZE)
        
        if not chunks_with_headings:
            return {'status': 'error', 'message': 'No chunks created from document'}
        
        # Debug: Log chunk count
        unique_sections = set(h for _, h in chunks_with_headings if h)
        print(f"Created {len(chunks_with_headings)} chunks from {len(unique_sections)} unique sections")
        
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