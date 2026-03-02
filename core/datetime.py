from datetime import timezone, datetime

"""
Returns time in supabase default [timestampz] format
"""
def get_supabase_timestampz() -> str:
    """
    Get current timestamp in supabase default format
    """
    time = datetime.now(timezone.utc)
    
    return time.isoformat()

def parse_supabase_timestampz(time: str) -> datetime:
    """
    Parse supabase timestampz to datetime object
    """
    return datetime.fromisoformat(time)
