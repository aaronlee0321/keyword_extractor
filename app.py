"""
Gradio app for Keyword Extractor.
"""
import gradio as gr
from services.document_service import upload_and_index_document
from services.search_service import keyword_search
from services.storage_service import list_documents, delete_document

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