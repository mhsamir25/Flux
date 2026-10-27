import time
import uuid
from dataclasses import dataclass
from typing import Optional

from app.dataframe.frame import FluxDataFrame

DEFAULT_TTL_SECONDS = 2 * 60 * 60  # 2 hours


@dataclass
class _CacheEntry:
    data: FluxDataFrame
    expires_at: float
    raw: Optional[bytes] = None


class DataReferenceCache:
    def __init__(self, ttl_seconds: float = DEFAULT_TTL_SECONDS):
        self._ttl_seconds = ttl_seconds
        self._entries: dict[str, _CacheEntry] = {}

    def put(self, data: FluxDataFrame, raw: Optional[bytes] = None) -> str:
        self._evict_expired()
        reference_id = str(uuid.uuid4())
        self._entries[reference_id] = _CacheEntry(
            data=data, expires_at=time.monotonic() + self._ttl_seconds, raw=raw
        )
        return reference_id

    def get(self, reference_id: str) -> Optional[FluxDataFrame]:
        entry = self._entry(reference_id)
        return entry.data if entry is not None else None

    def get_raw(self, reference_id: str) -> Optional[bytes]:
        """The original upload bytes, or None if they weren't kept for this entry."""
        entry = self._entry(reference_id)
        return entry.raw if entry is not None else None

    def _entry(self, reference_id: str) -> Optional[_CacheEntry]:
        self._evict_expired()
        return self._entries.get(reference_id)

    def _evict_expired(self) -> None:
        now = time.monotonic()
        expired = [key for key, entry in self._entries.items() if entry.expires_at <= now]
        for key in expired:
            del self._entries[key]


data_reference_cache = DataReferenceCache()
