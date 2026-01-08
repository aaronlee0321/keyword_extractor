"""
Configuration settings for keyword extractor.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL')

# Chunking configuration
CHUNK_SIZE = int(os.getenv('CHUNK_SIZE', 500))
CHUNK_OVERLAP = float(os.getenv('CHUNK_OVERLAP', 0.15))

# Use Supabase if configured
USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY)

# Embeddings configuration (optional)
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'text-embedding-3-small')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_COMPATIBLE_BASE_URL_EMBEDDING = os.getenv('OPENAI_COMPATIBLE_BASE_URL_EMBEDDING')
OPENAI_COMPATIBLE_API_KEY_EMBEDDING = os.getenv('OPENAI_COMPATIBLE_API_KEY_EMBEDDING')