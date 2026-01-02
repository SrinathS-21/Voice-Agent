"""
Session Cache
Simple in-memory cache for session config and metadata
"""

import threading
import time

# { session_id: (data_dict, expires_at) }
session_cache = {}
cache_lock = threading.Lock()
CACHE_TTL_SECONDS = 600  # 10 minutes

def set_session_cache(session_id, data):
    expires_at = time.time() + CACHE_TTL_SECONDS
    with cache_lock:
        session_cache[session_id] = (data, expires_at)

def get_session_cache(session_id):
    now = time.time()
    with cache_lock:
        entry = session_cache.get(session_id)
        if not entry:
            return None
        data, expires_at = entry
        if expires_at < now:
            del session_cache[session_id]
            return None
        return data

def clear_session_cache(session_id):
    with cache_lock:
        session_cache.pop(session_id, None)
