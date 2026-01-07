"""
Text utilities for keyword extractor.
Extracted from open-notebook's text_utils.py
"""
import re
from typing import List, Optional, Tuple
from langchain_text_splitters import RecursiveCharacterTextSplitter
from utils.token_utils import token_count

def split_text(txt: str, chunk_size=500):
    """
    Split text into chunks using RecursiveCharacterTextSplitter.
    
    Args:
        txt: Text to split
        chunk_size: Size of each chunk in tokens (default: 500)
    
    Returns:
        List of text chunks
    """
    overlap = int(chunk_size * 0.15)
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        length_function=token_count,
        separators=[
            "\n\n",
            "\n",
            ".",
            ",",
            " ",
            "\u200b",  # Zero-width space
            "\uff0c",  # Fullwidth comma
            "\u3001",  # Ideographic comma
            "\uff0e",  # Fullwidth full stop
            "\u3002",  # Ideographic full stop
            "",
        ],
    )
    return text_splitter.split_text(txt)

def split_text_with_headings(txt: str, chunk_size=500) -> List[Tuple[str, Optional[str]]]:
    """
    Split text into chunks with section headings.
    
    Extracts headings in multiple formats:
    - Markdown-style headings (# Heading, ## Heading, etc.)
    - PDF-style headings (lines in brackets like [Section Name])
    - Title-like lines (short lines that look like section titles)
    
    and associates each chunk with the most recent heading that appears before it.
    
    Args:
        txt: Text to split
        chunk_size: Size of each chunk in tokens (default: 500)
    
    Returns:
        List of tuples (chunk_text, section_heading) where section_heading
        is the most recent heading before the chunk, or None if no heading exists.
    """
    # Pattern to match markdown headings
    markdown_heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
    
    # Pattern to match PDF-style headings in brackets
    bracket_heading_pattern = re.compile(r'^\[([^\]]+)\]|^\(([^\)]+)\)', re.MULTILINE)
    
    # Pattern to match title-like lines
    title_line_pattern = re.compile(r'^([A-Z][A-Za-z\s]{1,48}[A-Za-z])\s*$', re.MULTILINE)
    
    # Find all headings with their positions
    headings = []
    
    # Find markdown headings
    for match in markdown_heading_pattern.finditer(txt):
        level = len(match.group(1))
        heading_text = match.group(2).strip()
        position = match.start()
        headings.append((position, heading_text, level))
    
    # Find bracket-style headings
    for match in bracket_heading_pattern.finditer(txt):
        heading_text = (match.group(1) or match.group(2) or "").strip()
        if heading_text and len(heading_text) > 1:
            position = match.start()
            headings.append((position, heading_text, 2))
    
    # Find title-like lines
    for match in title_line_pattern.finditer(txt):
        heading_text = match.group(1).strip()
        position = match.start()
        is_duplicate = any(abs(pos - position) < 10 for pos, _, _ in headings)
        if not is_duplicate and len(heading_text) > 2:
            headings.append((position, heading_text, 3))
    
    # Sort headings by position
    headings.sort(key=lambda x: x[0])
    
    # Split text into chunks
    chunks = split_text(txt, chunk_size)
    
    # Map chunks to their section headings
    chunks_with_headings = []
    current_pos = 0
    
    for chunk in chunks:
        chunk_start = txt.find(chunk, current_pos)
        if chunk_start == -1:
            chunk_start = current_pos
        
        overlap = int(chunk_size * 0.15)
        current_pos = max(chunk_start + len(chunk) - overlap, current_pos + 1)
        
        # Find the most recent heading before this chunk
        section_heading = None
        for heading_pos, heading_text, heading_level in headings:
            if heading_pos <= chunk_start:
                section_heading = heading_text
            else:
                break
        
        chunks_with_headings.append((chunk, section_heading))
    
    return chunks_with_headings