# Keyword Extractor

A Gradio app that implements the Open Notebook keyword search flow (upload → chunk → index → keyword search) using Supabase (Postgres).

## Features

- **PDF Upload & Indexing**: Upload PDFs, extract text, chunk with section-heading detection
- **Keyword Search**: Full‑text search (BM25‑style via Postgres FTS)
- **Simple Results**: “Simple Search” tab outputs unique matching document names
- **Detailed Results**: Full results with snippet, section, and relevance
- **Document Management**: List and delete indexed documents

## Setup

1) Install dependencies

```bash
pip install -r requirements.txt
```

2) Configure environment

Create a `.env` with:

```
SUPABASE_URL=https://YOUR_PROJECT_ID.supabase.co
SUPABASE_KEY=YOUR_ANON_KEY
SUPABASE_SERVICE_KEY=YOUR_SERVICE_ROLE_KEY

# Optional chunking params (tokens)
CHUNK_SIZE=500
CHUNK_OVERLAP=0.15
```

3) Create database schema in Supabase

- Open Supabase SQL Editor and run the contents of `database/scheme.sql`
  - Creates `keyword_documents`, `keyword_chunks`
  - Adds FTS indexes and the `keyword_search_documents(search_query, match_count, doc_id_filter)` function

4) Run the app

```bash
python app.py
```

Open http://localhost:7860

## Usage

- Upload Documents: “Upload Documents” tab → select PDF → “Upload & Index”
- Simple Search: “Simple Search” tab → enter keyword → list of matching document names
- Detailed Search: “Keyword Search” tab → keyword, optional doc filter, max results
- Manage: “Manage Documents” tab → delete or refresh list

## Architecture

- Chunking: `RecursiveCharacterTextSplitter` (~500 tokens, 15% overlap)
- Section Headings: markdown, bracket headings, title‑like lines
- Storage/Index: Postgres via Supabase; FTS on `keyword_chunks.content`, `keyword_documents.full_text`, `keyword_documents.name`
- Search: Postgres `to_tsvector`/`plainto_tsquery` through RPC `keyword_search_documents`