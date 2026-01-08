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


def split_by_sections(txt: str, chunk_size: int = 500) -> List[Tuple[str, Optional[str]]]:
    """
    Split document into sections first, then chunk each section individually.
    
    Hierarchy: Document -> Sections -> Chunks
    - First identifies all sections based on headings (including subheadings)
    - Each heading/subheading becomes a section
    - Then treats each section as an individual entity
    - Chunks each section using the same size-based chunking as before
    - Each chunk's parent is its section, each section's parent is the document
    
    Args:
        txt: Text to split (should be markdown or have clear headings)
        chunk_size: Size of each chunk in tokens (default: 500)
    
    Returns:
        List of tuples (chunk_text, section_heading)
    """
    # Step 1: Detect ALL headings (including subheadings) with their positions
    headings = []
    
    # Markdown headings (# ## ### #### ##### ######) - all levels
    markdown_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
    for match in markdown_pattern.finditer(txt):
        level = len(match.group(1))
        heading_text = match.group(2).strip()
        position = match.start()
        if heading_text:
            headings.append((position, heading_text, level))
    
    # Bracket headings [Section] or (Section) - can be multiple brackets like [Asset,UI][TankWar]
    # Pattern 1: Single bracket [Section] or (Section)
    bracket_pattern = re.compile(r'^\[([^\]]+)\]|^\(([^\)]+)\)', re.MULTILINE)
    for match in bracket_pattern.finditer(txt):
        heading_text = (match.group(1) or match.group(2) or "").strip()
        if heading_text and len(heading_text) > 1:
            position = match.start()
            # Check if not already detected as markdown heading
            is_duplicate = any(abs(pos - position) < 10 for pos, _, _ in headings)
            if not is_duplicate:
                headings.append((position, heading_text, 2))
    
    # Pattern 2: Multiple brackets on same line like [Asset,UI][TankWar]In-gameGUIDesign
    # Match lines that start with one or more bracket pairs
    multi_bracket_pattern = re.compile(r'^(\[[^\]]+\])+([^\n]+)?', re.MULTILINE)
    for match in multi_bracket_pattern.finditer(txt):
        bracket_part = match.group(1)  # e.g., "[Asset,UI][TankWar]"
        text_part = match.group(2) if match.group(2) else ""  # e.g., "In-gameGUIDesign"
        
        # Combine brackets and text as heading
        heading_text = (bracket_part + text_part).strip()
        if heading_text and len(heading_text) > 3:
            position = match.start()
            # Check if not already detected
            is_duplicate = any(abs(pos - position) < 10 for pos, _, _ in headings)
            if not is_duplicate:
                headings.append((position, heading_text, 2))
    
    # Title-like lines (capitalized short lines that look like headings)
    # Lines that are standalone and look like section titles
    title_pattern = re.compile(r'^([A-Z][A-Za-z0-9\s]{2,60}[A-Za-z0-9])\s*$', re.MULTILINE)
    for match in title_pattern.finditer(txt):
        heading_text = match.group(1).strip()
        position = match.start()
        # Avoid duplicates and very long lines
        is_duplicate = any(abs(pos - position) < 20 for pos, _, _ in headings)
        if not is_duplicate and 3 < len(heading_text) < 60:
            # Check if next line is not empty (might be a heading)
            next_newline = txt.find('\n', position)
            if next_newline != -1 and next_newline < len(txt) - 1:
                next_char = txt[next_newline + 1]
                # If next line starts with content (not another heading pattern), it's likely a heading
                if next_char not in ['#', '[', '('] and not next_char.isupper():
                    headings.append((position, heading_text, 3))
    
    # Sort by position
    headings.sort(key=lambda x: x[0])
    
    # Debug: Print detected headings
    print(f"Detected {len(headings)} headings:")
    for pos, text, level in headings[:10]:  # Print first 10
        print(f"  - Level {level}: '{text[:50]}...' at position {pos}")
    
    # Step 2: If no headings found, treat entire document as one section
    if not headings:
        # No headings found, chunk entire document as one section
        print("No headings detected, chunking entire document as one section")
        chunks = split_text(txt, chunk_size)
        return [(chunk, None) for chunk in chunks]
    
    # Step 3: Split document into sections (one per heading), then chunk each section
    chunks_with_headings = []
    
    for i, (heading_pos, heading_text, heading_level) in enumerate(headings):
        # Determine section boundaries - from this heading to next heading (or end)
        section_start = heading_pos
        section_end = headings[i + 1][0] if i + 1 < len(headings) else len(txt)
        
        # Extract section text (includes the heading line)
        section_text = txt[section_start:section_end].strip()
        
        if not section_text or len(section_text.strip()) < 1:
            # Empty section, create a minimal chunk with just the heading
            chunks_with_headings.append((heading_text, heading_text))
            continue
        
        # Step 4: Treat each section as individual entity and chunk it
        # Use the same chunking approach as before (size-based with overlap)
        section_chunks = split_text(section_text, chunk_size)
        
        # Each chunk from this section gets the section heading as its parent
        # Ensure at least one chunk is created per section
        if not section_chunks:
            # If split_text returned nothing, use the section text as-is
            section_chunks = [section_text]
        
        print(f"Section '{heading_text[:50]}...': {len(section_chunks)} chunks created")
        
        for chunk in section_chunks:
            # Ensure chunk is not empty
            chunk = chunk.strip()
            if chunk:
                chunks_with_headings.append((chunk, heading_text))
    
    # If no chunks were created (shouldn't happen), fallback to size-based chunking
    if not chunks_with_headings:
        chunks = split_text(txt, chunk_size)
        return [(chunk, None) for chunk in chunks]
    
    return chunks_with_headings