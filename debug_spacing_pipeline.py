"""
Debug script to trace spacing through the entire pipeline.
Shows text at each stage so we can identify where words get concatenated.
"""
import sys
import os
from pathlib import Path

# Add current directory to path so we can import modules
sys.path.insert(0, str(Path(__file__).parent))

import re
from io import BytesIO
import tempfile
from services.document_service import pdf_to_markdown, clean_markdown
from utils.text_utils import normalize_spacing, split_by_sections, split_text
from config.settings import CHUNK_SIZE


def find_concatenated_words(text: str, sample_size: int = 500, min_length: int = 15):
    """Find likely concatenated words in text."""
    sample = text[:sample_size]
    if not sample:
        return []
    
    # Find sequences of min_length+ alphanumeric chars (likely concatenated words)
    potential_concat = re.findall(r'[a-zA-Z0-9]{' + str(min_length) + ',}', sample)
    # Filter to only fully alphanumeric (no punctuation inside)
    return [w for w in potential_concat[:10] if w.isalnum()]


def print_stage(stage_name: str, text: str, max_chars: int = 300, compare_with=None):
    """Print stage info and sample text."""
    print(f"\n{'='*80}")
    print(f"STAGE: {stage_name}")
    print(f"{'='*80}")
    
    if not text:
        print("❌ TEXT IS EMPTY!")
        input("\n⏸️  Press ENTER to continue...")
        return
    
    # Show sample
    sample = text[:max_chars]
    print(f"\n📄 Sample (first {len(sample)} chars):")
    print("-" * 80)
    print(repr(sample))  # Use repr to show exact characters
    print("-" * 80)
    
    # Also show human-readable version (first 200 chars)
    readable = text[:200].replace('\n', '\\n')
    print(f"\n📖 Human-readable preview:")
    print(f"   {readable}")
    
    # Analyze spacing
    analysis_window = text[:500]
    space_count = analysis_window.count(" ")
    newline_char = "\n"  # Extract to variable to avoid f-string backslash issue
    tab_char = "\t"  # Extract to variable to avoid f-string backslash issue
    newline_count = analysis_window.count(newline_char)
    tab_count = analysis_window.count(tab_char)
    total_chars = len(analysis_window)
    
    # Check for concatenated words
    concatenated_found = find_concatenated_words(text, sample_size=500, min_length=15)
    
    # Pre-compute boolean checks to avoid backslashes in f-string expressions
    has_spaces = ' ' in analysis_window
    has_newlines = newline_char in analysis_window
    
    print(f"\n📊 Statistics (first 500 chars):")
    print(f"  - Total characters: {total_chars}")
    if total_chars > 0:
        print(f"  - Space count: {space_count} ({space_count/total_chars*100:.1f}%)")
    else:
        print(f"  - Space count: 0")
    print(f"  - Newline count: {newline_count}")
    print(f"  - Tab count: {tab_count}")
    print(f"  - Has spaces: {'✅ YES' if has_spaces else '❌ NO'}")
    print(f"  - Has newlines: {'✅ YES' if has_newlines else '❌ NO'}")
    
    # Compare with previous stage if provided
    if compare_with:
        prev_analysis = compare_with[:500] if compare_with else ""
        prev_space_count = prev_analysis.count(" ")
        space_diff = space_count - prev_space_count
        print(f"\n🔄 Comparison with previous stage:")
        if prev_space_count > 0:
            print(f"  - Space count change: {space_diff:+d} ({'+' if space_diff > 0 else ''}{space_diff/prev_space_count*100:.1f}%)")
        else:
            print(f"  - Space count change: {space_diff:+d}")
        if space_diff < -10:
            print(f"  ⚠️  WARNING: Significant space loss detected!")
    
    if concatenated_found:
        print(f"\n⚠️  POTENTIAL CONCATENATED WORDS DETECTED:")
        for word in concatenated_found[:5]:
            print(f"  - '{word}' (length: {len(word)})")
            # Try to suggest where it might split
            if len(word) > 20:
                mid = len(word) // 2
                suggestion = f"{word[:mid]}...{word[mid:]}"
                print(f"    (possibly: '{suggestion}')")
    else:
        print(f"\n✅ No obviously concatenated words detected in sample")
    
    input("\n⏸️  Press ENTER to continue to next stage...")


def main():
    if len(sys.argv) < 2:
        print("Usage: python debug_spacing_pipeline.py <path_to_pdf>")
        print("\nExample:")
        print("  python debug_spacing_pipeline.py example.pdf")
        sys.exit(1)
    
    pdf_path = Path(sys.argv[1])
    if not pdf_path.exists():
        print(f"❌ Error: PDF file not found: {pdf_path}")
        sys.exit(1)
    
    print(f"\n🔍 Starting spacing debug pipeline...")
    print(f"📄 PDF: {pdf_path}")
    print(f"📏 Chunk size: {CHUNK_SIZE} tokens")
    
    # Read PDF
    with open(pdf_path, 'rb') as f:
        pdf_bytes = f.read()
    
    print(f"📦 PDF size: {len(pdf_bytes)} bytes")
    input("\n⏸️  Press ENTER to start processing...")
    
    try:
        # Stage 1: Docling conversion - raw output
        print("\n" + "="*80)
        print("STAGE 1: Docling PDF to Markdown Conversion (RAW OUTPUT)")
        print("="*80)
        try:
            from docling.document_converter import DocumentConverter
            
            # Create temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_file.write(pdf_bytes)
                tmp_path = tmp_file.name
            
            try:
                converter = DocumentConverter()
                result = converter.convert(tmp_path)
                markdown_raw_original = result.document.export_to_markdown()
                
                # Check for ASCII 1 (0x01) being used as spaces by Docling
                ascii1_count = markdown_raw_original[:500].count("\x01") if markdown_raw_original else 0
                total_ascii1 = markdown_raw_original.count("\x01") if markdown_raw_original else 0
                
                print_stage("1. Docling export_to_markdown() - RAW OUTPUT (BEFORE FIX)", markdown_raw_original)
                
                # CRITICAL FIX: Replace ASCII 1 with actual spaces BEFORE cleaning
                if ascii1_count > 0:
                    print("\n" + "="*80)
                    print("🔧 CRITICAL FIX: Replacing ASCII 1 (\\x01) with actual spaces")
                    print("="*80)
                    print(f"⚠️  DETECTED: Docling is using ASCII 1 (\\x01) as space characters!")
                    print(f"   Found {total_ascii1} total instances in document")
                    print(f"   Found {ascii1_count} instances in first 500 chars")
                    print("   These will be removed by clean_markdown(), causing spacing loss!")
                    print("\n   Applying fix: replacing all \\x01 with actual spaces (' ')...")
                    
                    markdown_raw = markdown_raw_original.replace("\x01", " ")
                    
                    replaced_count = total_ascii1
                    print(f"   ✅ Replaced {replaced_count} instances")
                    
                    # Verify the fix
                    remaining_ascii1 = markdown_raw.count("\x01")
                    new_space_count = markdown_raw[:500].count(" ")
                    old_space_count = markdown_raw_original[:500].count(" ")
                    
                    print(f"\n   Verification:")
                    print(f"   - Remaining \\x01 characters: {remaining_ascii1} (should be 0)")
                    print(f"   - Spaces in first 500 chars: {old_space_count} → {new_space_count}")
                    
                    if remaining_ascii1 == 0 and new_space_count > old_space_count:
                        print(f"   ✅ Fix successful!")
                    else:
                        print(f"   ⚠️  Warning: Fix may not have worked as expected")
                    
                    input("\n⏸️  Press ENTER to see the fixed output...")
                    print_stage("1b. After replacing \\x01 with spaces - FIXED OUTPUT", markdown_raw, compare_with=markdown_raw_original)
                else:
                    markdown_raw = markdown_raw_original
                    print("\n✅ No ASCII 1 characters found - no fix needed")
                    input("\n⏸️  Press ENTER to continue to next stage...")
                
                # Stage 2: Clean markdown
                markdown_cleaned = clean_markdown(markdown_raw)
                print_stage("2. clean_markdown()", markdown_cleaned, compare_with=markdown_raw)
                
                # Stage 3: Normalize spacing (first time)
                markdown_normalized = normalize_spacing(markdown_cleaned)
                print_stage("3. normalize_spacing() - FIRST PASS", markdown_normalized, compare_with=markdown_cleaned)
                
                # Stage 4: Split by sections (this calls normalize_spacing again inside)
                print("\n" + "="*80)
                print("STAGE 4: Split by Sections (includes normalize_spacing per section)")
                print("="*80)
                chunks_with_headings = split_by_sections(markdown_normalized, chunk_size=CHUNK_SIZE)
                
                if chunks_with_headings:
                    print(f"\n✅ Created {len(chunks_with_headings)} chunks")
                    print(f"📑 First chunk sample:")
                    first_chunk = chunks_with_headings[0][0]
                    first_heading = chunks_with_headings[0][1]
                    print(f"   Section heading: {first_heading}")
                    print(f"\n   Chunk content (first 300 chars):")
                    print(f"   {repr(first_chunk[:300])}")
                    
                    # Analyze first chunk spacing
                    space_count = first_chunk[:500].count(" ")
                    print(f"\n   Space count (first 500 chars): {space_count}")
                    print(f"   Has spaces: {'✅ YES' if ' ' in first_chunk[:500] else '❌ NO'}")
                    
                    # Check for concatenated words
                    potential_concat = re.findall(r'[a-zA-Z0-9]{15,}', first_chunk[:500])
                    if potential_concat:
                        print(f"\n   ⚠️  Concatenated words found:")
                        for word in potential_concat[:3]:
                            print(f"      - '{word}'")
                    
                    input("\n⏸️  Press ENTER to continue...")
                    
                    # Stage 5: Final cleanup (what happens in document_service)
                    print("\n" + "="*80)
                    print("STAGE 5: Final Cleanup (re.sub whitespace normalization)")
                    print("="*80)
                    
                    chunk_before = first_chunk
                    chunk_after = re.sub(r'\s+', ' ', first_chunk).strip()
                    
                    print(f"\n📄 Before final cleanup (first 300 chars):")
                    print(f"   {repr(chunk_before[:300])}")
                    print(f"\n📄 After final cleanup (first 300 chars):")
                    print(f"   {repr(chunk_after[:300])}")
                    print(f"\n   Changed: {'✅ YES' if chunk_before != chunk_after else '❌ NO'}")
                    
                    space_count_before = chunk_before[:500].count(" ")
                    space_count_after = chunk_after[:500].count(" ")
                    print(f"\n   Spaces before: {space_count_before}")
                    print(f"   Spaces after: {space_count_after}")
                    
                else:
                    print("❌ No chunks created!")
                    
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
        
        except ImportError:
            print("❌ Docling not available, using PyPDF2 fallback...")
            from PyPDF2 import PdfReader
            pdf_file = BytesIO(pdf_bytes)
            reader = PdfReader(pdf_file)
            text_parts = []
            for page in reader.pages:
                text_parts.append(page.extract_text())
            text_raw = "\n\n".join(text_parts)
            print_stage("1. PyPDF2 extract_text() - RAW OUTPUT", text_raw)
            
            # Normalize
            text_normalized = normalize_spacing(text_raw)
            print_stage("2. normalize_spacing()", text_normalized)
        
        print("\n" + "="*80)
        print("✅ Pipeline trace complete!")
        print("="*80)
        print("\n📝 Summary:")
        print("   Check each stage above to see where spacing is lost.")
        print("   Look for stages where:")
        print("     - Space count decreases unexpectedly")
        print("     - Concatenated words appear")
        print("     - 'Has spaces' changes from YES to NO")
        
    except Exception as e:
        print(f"\n❌ Error during processing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

