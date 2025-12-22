from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import requests


FPL_BASE_URL = "https://fantasy.premierleague.com/api"


@dataclass(frozen=True)
class CacheConfig:
    cache_dir: Path
    ttl_seconds: int = 6 * 60 * 60  # 6 hours


def _default_cache_dir() -> Path:
    # Allow override via env var, otherwise keep local + repo-friendly.
    return Path(os.getenv("FPL_CACHE_DIR", "data/cache")).resolve()


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)


def _is_fresh(path: Path, ttl_seconds: int) -> bool:
    if not path.exists():
        return False
    age = time.time() - path.stat().st_mtime
    return age <= ttl_seconds


def get_json(
    endpoint: str,
    *,
    cache: Optional[CacheConfig] = None,
    params: Optional[Dict[str, Any]] = None,
    force_refresh: bool = False,
    timeout_seconds: int = 20,
) -> Any:
    """
    Fetch JSON from the official FPL API, with simple disk caching.
    """
    cache = cache or CacheConfig(cache_dir=_default_cache_dir())
    safe_name = endpoint.strip("/").replace("/", "__")
    cache_path = cache.cache_dir / f"{safe_name}.json"

    if not force_refresh and _is_fresh(cache_path, cache.ttl_seconds):
        return _read_json(cache_path)

    url = f"{FPL_BASE_URL}/{endpoint.lstrip('/')}"
    resp = requests.get(url, params=params, timeout=timeout_seconds)
    resp.raise_for_status()
    payload = resp.json()
    _write_json(cache_path, payload)
    return payload


def bootstrap_static(*, force_refresh: bool = False) -> Dict[str, Any]:
    return get_json("bootstrap-static/", force_refresh=force_refresh)


def fixtures(*, force_refresh: bool = False) -> Any:
    return get_json("fixtures/", force_refresh=force_refresh)


def team_mapping(bootstrap: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    return {t["id"]: t for t in bootstrap.get("teams", [])}


def element_type_mapping(bootstrap: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    return {t["id"]: t for t in bootstrap.get("element_types", [])}


