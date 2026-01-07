"""
Database connection management.
"""
from supabase import create_client, Client
from config.settings import SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_KEY, USE_SUPABASE

_supabase_client: Client = None
_supabase_service_client: Client = None

def get_supabase_client(use_service_key: bool = False) -> Client:
    """
    Get Supabase client instance.
    
    Args:
        use_service_key: If True, use service key (for admin operations)
    
    Returns:
        Supabase client instance
    """
    global _supabase_client, _supabase_service_client
    
    if not USE_SUPABASE:
        raise ValueError("Supabase not configured. Set SUPABASE_URL and SUPABASE_KEY in .env")
    
    if use_service_key:
        if _supabase_service_client is None:
            if not SUPABASE_SERVICE_KEY:
                raise ValueError("SUPABASE_SERVICE_KEY not configured")
            _supabase_service_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        return _supabase_service_client
    else:
        if _supabase_client is None:
            _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        return _supabase_client