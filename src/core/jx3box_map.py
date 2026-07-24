import json
import logging
import threading
import time
import urllib.request
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

log = logging.getLogger("jx3box_map")

CACHE_FILE_NAME = "jx3box_map_cache.json"
MAP_API_URL = "https://cdn.jsdelivr.net/gh/JX3BOX/jx3box-data@master/data/fb/fb_map.json"
CACHE_EXPIRY_SECONDS = 7 * 24 * 3600  # 7 days

_cache: Dict[str, Any] = {}
_cache_loaded = False
_map_index: Dict[str, Dict[str, Any]] = {}
_bg_thread: Optional[threading.Thread] = None

def get_cache_path() -> Path:
    from src.config import AppConfig
    out_dir = AppConfig().out_dir or "sessions"
    return Path(out_dir) / CACHE_FILE_NAME

def _build_index(data: Dict[str, Any]) -> None:
    global _map_index
    index = {}
    for expansion_name, expansion_data in data.items():
        if "dungeon" in expansion_data:
            for dungeon_name, dungeon_info in expansion_data["dungeon"].items():
                if "maps" in dungeon_info:
                    for map_entry in dungeon_info["maps"]:
                        map_id = str(map_entry.get("map_id"))
                        if map_id:
                            index[map_id] = {
                                "expansion": expansion_name,
                                "dungeon_name": dungeon_name,
                                "mode": map_entry.get("mode"),
                                "bosses": dungeon_info.get("boss", [])
                            }
    _map_index = index

def _fetch_from_api_sync() -> Dict[str, Any]:
    try:
        log.info(f"Fetching fb_map.json from {MAP_API_URL}")
        req = urllib.request.Request(MAP_API_URL, headers={'User-Agent': 'Mozilla/5.0 Xiaoyingwu/1.0'})
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode('utf-8'))
        return data
    except Exception as e:
        log.error(f"Failed to fetch fb_map.json: {e}")
        return {}

def _update_cache_bg():
    global _cache, _cache_loaded
    data = _fetch_from_api_sync()
    if data:
        _cache = data
        _build_index(data)
        _cache_loaded = True
        try:
            cache_path = get_cache_path()
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump({"timestamp": time.time(), "data": data}, f, ensure_ascii=False)
            log.info("fb_map.json cache updated successfully.")
        except Exception as e:
            log.error(f"Failed to save fb_map.json cache: {e}")

def load_cache():
    global _cache, _cache_loaded, _bg_thread
    if _cache_loaded:
        return
    
    cache_path = get_cache_path()
    needs_update = True
    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                wrapped = json.load(f)
                if isinstance(wrapped, dict) and "data" in wrapped:
                    _cache = wrapped["data"]
                    _build_index(_cache)
                    _cache_loaded = True
                    if time.time() - wrapped.get("timestamp", 0) < CACHE_EXPIRY_SECONDS:
                        needs_update = False
                else:
                    _cache = wrapped
                    _build_index(_cache)
                    _cache_loaded = True
        except Exception as e:
            log.error(f"Error reading jx3box_map_cache.json: {e}")
            
    if needs_update and (_bg_thread is None or not _bg_thread.is_alive()):
        _bg_thread = threading.Thread(target=_update_cache_bg, daemon=True)
        _bg_thread.start()

def get_dungeon_info(map_id: int | str) -> Optional[Dict[str, Any]]:
    """
    Returns dict with keys: 'expansion', 'dungeon_name', 'mode', 'bosses' (list of str).
    Returns None if map_id is not found.
    """
    if not _cache_loaded:
        load_cache()
    return _map_index.get(str(map_id))

def get_dungeon_name(map_id: int | str) -> Optional[str]:
    info = get_dungeon_info(map_id)
    if info:
        mode = info.get("mode", "")
        name = info.get("dungeon_name", "")
        return f"{mode} {name}".strip()
    return None
