"""
Gradio app for Keyword Extractor.
"""
import gradio as gr
from services.document_service import upload_and_index_document
from services.search_service import keyword_search
from services.storage_service import list_documents, delete_document
from services.explainer_service import explain_keyword

def simple_search_names(keyword):
    """Return hierarchical structure of documents and their sections matching a keyword."""
    if not keyword or not keyword.strip():
        return "Please enter a keyword to search."
    results = keyword_search(keyword.strip(), limit=100)
    if not results:
        return "No results found."
    
    # Group results by document, preserving section order and hierarchy
    doc_sections = {}
    for r in results:
        doc_name = r.get('doc_name', 'Unknown Document')
        section = r.get('section_heading')
        
        if doc_name not in doc_sections:
            doc_sections[doc_name] = []
        
        if section:
            # Only add if not already in list (preserve order, avoid duplicates)
            if section not in doc_sections[doc_name]:
                doc_sections[doc_name].append(section)
        else:
            if "(No section)" not in doc_sections[doc_name]:
                doc_sections[doc_name].append("(No section)")
    
    # Build hierarchical output with tree structure
    output_lines = []
    for doc_name, sections in sorted(doc_sections.items()):
        # Extract just the filename from full path for cleaner display
        display_name = doc_name.split('\\')[-1] if '\\' in doc_name else doc_name.split('/')[-1] if '/' in doc_name else doc_name
        
        # Add document name
        output_lines.append(f"📄 {display_name}")
        
        if not sections:
            output_lines.append("  └─ (No sections found)")
        else:
            # Add sections with tree structure
            for i, section in enumerate(sections):
                if i == len(sections) - 1:
                    # Last section - use └─
                    output_lines.append(f"  └─ {section}")
                else:
                    # Not last section - use ├─
                    output_lines.append(f"  ├─ {section}")
        
        # Add blank line between documents
        output_lines.append("")
    
    if not output_lines:
        return "No results found."
    
    return "\n".join(output_lines)

def upload_document(file, progress=gr.Progress()):
    """Handle document upload and indexing."""
    if file is None:
        return "Please select a PDF file to upload.", None, None
    
    try:
        with open(file.name, 'rb') as f:
            pdf_bytes = f.read()
        
        filename = file.name.split('/')[-1]
        
        def progress_callback(step):
            progress(0.5, desc=step)
        
        result = upload_and_index_document(pdf_bytes, filename, progress_callback)
        
        if result['status'] == 'success':
            return (
                f"✅ {result['message']}",
                gr.update(choices=get_document_choices(), value=None),
                None
            )
        else:
            return f"❌ {result['message']}", None, None
    
    except Exception as e:
        return f"❌ Error: {str(e)}", None, None

def get_document_choices():
    """Get list of documents for dropdown."""
    try:
        documents = list_documents()
        return [f"{doc['name']} ({doc['doc_id']})" for doc in documents]
    except Exception as e:
        print(f"Error loading documents: {e}")
        return []

def perform_search(keyword, document_filter, limit):
    """Perform keyword search."""
    if not keyword or not keyword.strip():
        return "Please enter a keyword to search."
    
    try:
        # Extract doc_id from document filter if selected
        doc_id = None
        if document_filter and document_filter != "All Documents":
            # Extract doc_id from format "Name (doc_id)"
            match = document_filter.split('(')
            if len(match) > 1:
                doc_id = match[-1].rstrip(')')
        
        results = keyword_search(keyword.strip(), limit=int(limit), doc_id_filter=doc_id)
        
        if not results:
            return "No results found."
        
        # Format results
        output = f"**Found {len(results)} result(s)**\n\n"
        output += "---\n\n"
        
        for i, result in enumerate(results, 1):
            output += f"### Result {i}\n"
            output += f"**Document:** {result['doc_name']}\n"
            if result.get('section_heading'):
                output += f"**Section:** {result['section_heading']}\n"
            else:
                output += f"**Section:** (No section)\n"
            output += f"**Relevance:** {result['relevance']:.2%}\n"
            output += f"**Content:**\n{result['content'][:500]}...\n\n"
            output += "---\n\n"
        
        return output
    
    except Exception as e:
        return f"❌ Error: {str(e)}"

def delete_selected_document(document_filter):
    """Delete selected document."""
    if not document_filter or document_filter == "All Documents":
        return "Please select a document to delete.", gr.update(choices=get_document_choices())
    
    try:
        # Extract doc_id
        match = document_filter.split('(')
        if len(match) > 1:
            doc_id = match[-1].rstrip(')')
            delete_document(doc_id)
            return f"✅ Document deleted successfully.", gr.update(choices=get_document_choices(), value=None)
        else:
            return "❌ Could not extract document ID.", gr.update(choices=get_document_choices())
    
    except Exception as e:
        return f"❌ Error: {str(e)}", gr.update(choices=get_document_choices())

# Create Gradio interface
with gr.Blocks(title="Keyword Extractor", theme=gr.themes.Soft()) as app:
    gr.Markdown("# 🔍 Keyword Extractor")
    gr.Markdown("Upload PDF documents and search by keywords using full-text search.")
    
    with gr.Tabs():
        with gr.Tab("Upload Documents"):
            gr.Markdown("### Upload PDF Document")
            file_upload = gr.File(
                label="Select PDF File",
                file_types=[".pdf"],
                type="filepath"
            )
            upload_btn = gr.Button("Upload & Index", variant="primary")
            upload_status = gr.Markdown()
            document_dropdown_upload = gr.Dropdown(
                label="Indexed Documents",
                choices=get_document_choices(),
                interactive=True
            )
            upload_btn.click(
                fn=upload_document,
                inputs=[file_upload],
                outputs=[upload_status, document_dropdown_upload, file_upload]
            )
        
        with gr.Tab("Keyword Search"):
            gr.Markdown("### Search Documents by Keyword")
            
            with gr.Row():
                keyword_input = gr.Textbox(
                    label="Enter Keyword",
                    placeholder="e.g., Minimap, Settings, Player",
                    scale=3
                )
                search_btn = gr.Button("Search", variant="primary", scale=1)
            
            with gr.Row():
                document_dropdown_search = gr.Dropdown(
                    label="Filter by Document (Optional)",
                    choices=["All Documents"] + get_document_choices(),
                    value="All Documents",
                    scale=2
                )
                limit_input = gr.Number(
                    label="Max Results",
                    value=100,
                    minimum=1,
                    maximum=500,
                    scale=1
                )
            
            search_results = gr.Markdown()
            
            search_btn.click(
                fn=perform_search,
                inputs=[keyword_input, document_dropdown_search, limit_input],
                outputs=[search_results]
            )
            
            keyword_input.submit(
                fn=perform_search,
                inputs=[keyword_input, document_dropdown_search, limit_input],
                outputs=[search_results]
            )
        
        with gr.Tab("Simple Search"):
            gr.Markdown("### Enter a keyword to see matching documents and sections")
            simple_keyword = gr.Textbox(
                label="Keyword",
                placeholder="e.g., transformer, alignment, privacy",
            )
            simple_btn = gr.Button("Search Documents & Sections", variant="primary")
            simple_output = gr.Textbox(
                label="Documents & Sections (Hierarchical View)", 
                lines=15,
                placeholder="Results will show documents with their matching sections in a hierarchical structure..."
            )
            simple_btn.click(
                fn=simple_search_names,
                inputs=[simple_keyword],
                outputs=[simple_output],
            )
            simple_keyword.submit(
                fn=simple_search_names,
                inputs=[simple_keyword],
                outputs=[simple_output],
            )
        
        with gr.Tab("Document Explainer"):
            gr.Markdown("### Get Detailed Explanations from Documents")
            gr.Markdown("Enter a keyword, select documents/sections, and get AI-generated explanations.")
            
            with gr.Row():
                explainer_keyword = gr.Textbox(
                    label="Keyword/Query",
                    placeholder="e.g., tank movement, combat system, progression",
                    scale=3
                )
                explainer_search_btn = gr.Button("Search", variant="secondary", scale=1)
            
            # Results display with checkboxes
            # Use a State to track last search keyword to detect when search changes
            last_search_keyword = gr.State(value=None)
            
            explainer_results = gr.Checkboxgroup(
                label="Search Results - Select Documents/Sections to Explain",
                choices=[],
                value=[],  # Explicitly set initial value to empty list
                visible=False,
                interactive=True
            )
            
            search_status = gr.Markdown(visible=False)
            
            with gr.Row():
                select_all_btn = gr.Button("Select All", variant="secondary", scale=1)
                select_none_btn = gr.Button("Select None", variant="secondary", scale=1)
                explain_btn = gr.Button("Generate Explanation", variant="primary", scale=2)
            
            # Output area
            explanation_output = gr.Markdown(
                label="Explanation",
                visible=True
            )
            
            source_chunks_output = gr.Markdown(
                label="Source Chunks (Click to expand)",
                visible=True
            )
            
            metadata_output = gr.Markdown(
                label="Metadata",
                visible=True
            )
            
            # Store search results internally
            explainer_search_results_store = gr.State(value=[])
            
            def search_for_explainer(keyword, last_keyword):
                """Search for keyword and return results as checkboxes for selection."""
                # Always clear selections when keyword changes
                keyword_stripped = keyword.strip() if keyword else ""
                
                if not keyword or not keyword_stripped:
                    return (
                        gr.update(choices=[], value=[], visible=False),
                        [],
                        gr.update(value="Please enter a keyword to search.", visible=True),
                        None  # Update last_search_keyword to None
                    )
                
                try:
                    results = keyword_search(keyword_stripped, limit=100)
                    if not results:
                        return (
                            gr.update(choices=[], value=[], visible=False),
                            [],
                            gr.update(value="No results found. Try a different keyword.", visible=True),
                            keyword_stripped  # Update last_search_keyword
                        )
                    
                    # Group by document and section
                    # Filter out items with no section (section_heading is None or empty)
                    doc_sections = {}
                    for r in results:
                        doc_id = r.get('doc_id')
                        doc_name = r.get('doc_name', 'Unknown Document')
                        section = r.get('section_heading')
                        
                        # Skip items without a section heading
                        if not section or section.strip() == '':
                            continue
                        
                        # Create unique key for document-section pair
                        key = (doc_id, doc_name, section)
                        if key not in doc_sections:
                            doc_sections[key] = {
                                'doc_id': doc_id,
                                'doc_name': doc_name,
                                'section_heading': section,
                                'relevance': r.get('relevance', 0.0)
                            }
                    
                    # Sort by relevance (highest first)
                    sorted_items = sorted(
                        doc_sections.values(),
                        key=lambda x: x['relevance'],
                        reverse=True
                    )
                    
                    # Create checkbox choices and store data
                    choices = []
                    store_data = []
                    
                    for item in sorted_items:
                        # Extract filename for display (remove .pdf extension if present)
                        display_name = item['doc_name']
                        if '\\' in display_name:
                            display_name = display_name.split('\\')[-1]
                        elif '/' in display_name:
                            display_name = display_name.split('/')[-1]
                        
                        # Remove .pdf extension for cleaner display
                        if display_name.lower().endswith('.pdf'):
                            display_name = display_name[:-4]
                        
                        section_display = item['section_heading'] if item['section_heading'] else "(No section)"
                        
                        # Create choice label
                        choice_label = f"{display_name} → {section_display}"
                        choices.append(choice_label)
                        
                        # Store actual data
                        store_data.append({
                            'doc_id': item['doc_id'],
                            'section_heading': item['section_heading']
                        })
                    
                    status_msg = f"✅ Found {len(sorted_items)} document/section combinations. Select which ones to explain."
                    
                    # Always clear selections when search changes
                    # IMPORTANT: Set value=[] FIRST, then update choices to prevent validation errors
                    return (
                        gr.update(value=[], choices=choices, visible=True),  # Clear value BEFORE setting choices
                        store_data,
                        gr.update(value=status_msg, visible=True),
                        keyword_stripped  # Update last_search_keyword
                    )
                    
                except Exception as e:
                    import traceback
                    return (
                        gr.update(choices=[], value=[], visible=False),
                        [],
                        gr.update(value=f"❌ Error: {str(e)}\n\n{traceback.format_exc()}", visible=True),
                        keyword_stripped if keyword_stripped else None  # Update last_search_keyword
                    )
            
            def generate_explanation(keyword, selected_choices, stored_results):
                """Generate explanation from selected items."""
                if not keyword or not keyword.strip():
                    return (
                        gr.update(value="Please enter a keyword first.", visible=True),
                        gr.update(visible=False),
                        gr.update(visible=False)
                    )
                
                if not stored_results or len(stored_results) == 0:
                    return (
                        gr.update(value="Please search for a keyword first.", visible=True),
                        gr.update(visible=False),
                        gr.update(visible=False)
                    )
                
                try:
                    # Get selected items based on checkbox selection
                    selected_items = []
                    
                    # Handle None or empty selected_choices
                    if not selected_choices:
                        selected_choices = []
                    
                    # Build choice label to item mapping from stored_results
                    # This creates the valid choices set for validation
                    choice_to_item = {}
                    valid_choices = set()
                    
                    for item in stored_results:
                        doc_id = item.get('doc_id')
                        section = item.get('section_heading')
                        
                        # Get doc_name from database for display
                        from services.storage_service import list_documents
                        docs = list_documents()
                        doc_name = 'Unknown'
                        for doc in docs:
                            if doc.get('doc_id') == doc_id:
                                doc_name = doc.get('name', 'Unknown')
                                break
                        
                        # Extract filename (same logic as search_for_explainer)
                        display_name = doc_name
                        if '\\' in display_name:
                            display_name = display_name.split('\\')[-1]
                        elif '/' in display_name:
                            display_name = display_name.split('/')[-1]
                        
                        # Remove .pdf extension for cleaner display (must match search_for_explainer)
                        if display_name.lower().endswith('.pdf'):
                            display_name = display_name[:-4]
                        
                        section_display = section if section else "(No section)"
                        choice_label = f"{display_name} → {section_display}"
                        choice_to_item[choice_label] = {
                            'doc_id': doc_id,
                            'section_heading': section
                        }
                        valid_choices.add(choice_label)
                    
                    # Filter selected_choices to only include valid ones
                    # This prevents errors when search results change between searches
                    valid_selected_choices = [c for c in selected_choices if c in valid_choices]
                    
                    if not valid_selected_choices:
                        return (
                            gr.update(value="Please select at least one document/section to explain. (Note: Previous selections were cleared due to new search results.)", visible=True),
                            gr.update(visible=False),
                            gr.update(visible=False)
                        )
                    
                    # Map valid selected choices to items
                    for choice in valid_selected_choices:
                        if choice in choice_to_item:
                            selected_items.append(choice_to_item[choice])
                    
                    if not selected_items:
                        return (
                            gr.update(value="Please select at least one document/section to explain.", visible=True),
                            gr.update(visible=False),
                            gr.update(visible=False)
                        )
                    
                    # Generate explanation
                    result = explain_keyword(keyword.strip(), selected_items, use_hyde=True)
                    
                    if result.get('error'):
                        return (
                            gr.update(value=f"❌ Error: {result['error']}", visible=True),
                            gr.update(visible=False),
                            gr.update(visible=False)
                        )
                    
                    # Build explanation output
                    explanation_text = f"## Explanation\n\n{result.get('explanation', 'No explanation generated.')}"
                    
                    # Build source chunks output
                    source_chunks = result.get('source_chunks', [])
                    chunks_text = f"### Source Chunks ({len(source_chunks)} chunks used)\n\n"
                    for i, chunk in enumerate(source_chunks[:10], 1):  # Show first 10
                        section = chunk.get('section_heading') or 'No section'
                        content = chunk.get('content') or ''
                        content_preview = content[:200] if content else '(Empty chunk)'
                        chunks_text += f"**Chunk {i}** (Section: {section})\n"
                        chunks_text += f"{content_preview}...\n\n"
                    
                    # Build metadata output
                    metadata_text = "### Metadata\n\n"
                    metadata_text += f"- **HYDE Query:** {result.get('hyde_query', keyword)}\n"
                    metadata_text += f"- **Language Detected:** {result.get('language', 'english')}\n"
                    metadata_text += f"- **Chunks Used:** {result.get('chunks_used', 0)}\n"
                    if result.get('hyde_timing'):
                        timing = result['hyde_timing']
                        if 'total_time' in timing:
                            metadata_text += f"- **HYDE Timing:** {timing['total_time']}s\n"
                    
                    return (
                        gr.update(value=explanation_text),
                        gr.update(value=chunks_text),
                        gr.update(value=metadata_text)
                    )
                    
                except Exception as e:
                    import traceback
                    return (
                        gr.update(value=f"❌ Error generating explanation: {str(e)}\n\n{traceback.format_exc()}", visible=True),
                        gr.update(visible=False),
                        gr.update(visible=False)
                    )
            
            def select_all_items(stored_results):
                """Select all items - return all choice labels."""
                if not stored_results or len(stored_results) == 0:
                    return gr.update()
                
                # Get document names from database
                from services.storage_service import list_documents
                docs = {doc.get('doc_id'): doc.get('name', 'Unknown') for doc in list_documents()}
                
                choices = []
                for item in stored_results:
                    doc_id = item.get('doc_id')
                    section = item.get('section_heading')
                    
                    doc_name = docs.get(doc_id, 'Unknown')
                    
                    # Extract filename (same logic as search_for_explainer)
                    display_name = doc_name
                    if '\\' in display_name:
                        display_name = display_name.split('\\')[-1]
                    elif '/' in display_name:
                        display_name = display_name.split('/')[-1]
                    
                    # Remove .pdf extension for cleaner display (must match search_for_explainer)
                    if display_name.lower().endswith('.pdf'):
                        display_name = display_name[:-4]
                    
                    section_display = section if section else "(No section)"
                    choice_label = f"{display_name} → {section_display}"
                    choices.append(choice_label)
                
                return gr.update(value=choices)
            
            def select_none_items():
                """Deselect all items - return empty list."""
                return gr.update(value=[])
            
            # Handler to clear checkbox selections when choices change
            # This ensures old selections don't persist when new search results are shown
            def ensure_valid_selections(selected_choices, stored_results):
                """Filter out any selections that aren't in the current choices."""
                if not stored_results or not selected_choices:
                    return []
                
                # Build valid choices set from stored_results
                from services.storage_service import list_documents
                docs = {doc.get('doc_id'): doc.get('name', 'Unknown') for doc in list_documents()}
                
                valid_choices = set()
                for item in stored_results:
                    doc_id = item.get('doc_id')
                    section = item.get('section_heading')
                    doc_name = docs.get(doc_id, 'Unknown')
                    
                    display_name = doc_name
                    if '\\' in display_name:
                        display_name = display_name.split('\\')[-1]
                    elif '/' in display_name:
                        display_name = display_name.split('/')[-1]
                    
                    if display_name.lower().endswith('.pdf'):
                        display_name = display_name[:-4]
                    
                    section_display = section if section else "(No section)"
                    choice_label = f"{display_name} → {section_display}"
                    valid_choices.add(choice_label)
                
                # Filter to only valid choices
                return [c for c in selected_choices if c in valid_choices]
            
            # Event handlers
            explainer_search_btn.click(
                fn=search_for_explainer,
                inputs=[explainer_keyword, last_search_keyword],
                outputs=[explainer_results, explainer_search_results_store, search_status, last_search_keyword]
            )
            
            explainer_keyword.submit(
                fn=search_for_explainer,
                inputs=[explainer_keyword, last_search_keyword],
                outputs=[explainer_results, explainer_search_results_store, search_status, last_search_keyword]
            )
            
            select_all_btn.click(
                fn=select_all_items,
                inputs=[explainer_search_results_store],
                outputs=[explainer_results]
            )
            
            select_none_btn.click(
                fn=select_none_items,
                inputs=[],
                outputs=[explainer_results]
            )
            
            def safe_generate_explanation(keyword, selected_choices, stored_results):
                """Wrapper that filters invalid selections before generating explanation."""
                # First, get the current valid choices from stored_results
                if stored_results:
                    from services.storage_service import list_documents
                    docs = {doc.get('doc_id'): doc.get('name', 'Unknown') for doc in list_documents()}
                    
                    valid_choices = set()
                    for item in stored_results:
                        doc_id = item.get('doc_id')
                        section = item.get('section_heading')
                        doc_name = docs.get(doc_id, 'Unknown')
                        
                        display_name = doc_name
                        if '\\' in display_name:
                            display_name = display_name.split('\\')[-1]
                        elif '/' in display_name:
                            display_name = display_name.split('/')[-1]
                        
                        if display_name.lower().endswith('.pdf'):
                            display_name = display_name[:-4]
                        
                        section_display = section if section else "(No section)"
                        choice_label = f"{display_name} → {section_display}"
                        valid_choices.add(choice_label)
                    
                    # Filter selected_choices to only include valid ones
                    if selected_choices:
                        selected_choices = [c for c in selected_choices if c in valid_choices]
                
                # Now call the actual function with filtered selections
                return generate_explanation(keyword, selected_choices or [], stored_results)
            
            explain_btn.click(
                fn=safe_generate_explanation,
                inputs=[explainer_keyword, explainer_results, explainer_search_results_store],
                outputs=[explanation_output, source_chunks_output, metadata_output]
            )
        
        with gr.Tab("Manage Documents"):
            gr.Markdown("### Manage Indexed Documents")
            
            document_dropdown_manage = gr.Dropdown(
                label="Select Document to Delete",
                choices=get_document_choices(),
                interactive=True
            )
            delete_btn = gr.Button("Delete Document", variant="stop")
            delete_status = gr.Markdown()
            
            delete_btn.click(
                fn=delete_selected_document,
                inputs=[document_dropdown_manage],
                outputs=[delete_status, document_dropdown_manage]
            )
            
            refresh_btn = gr.Button("Refresh Document List", variant="secondary")
            refresh_btn.click(
                fn=lambda: gr.update(choices=get_document_choices()),
                outputs=[document_dropdown_manage]
            )

if __name__ == "__main__":
    app.launch(share=False, server_name="0.0.0.0", server_port=7860)