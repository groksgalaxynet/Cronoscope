"""Bounded, exact-range, SHA-256-verified disk cache."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Callable


class RangeCache:
    """Thread-safe LRU cache; atomic replacement prevents partial reads."""

    def __init__(self, root: Path | str, *, max_bytes: int = 2 * 1024 * 1024) -> None:
        if max_bytes <= 0:
            raise ValueError("cache max_bytes must be positive")
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max_bytes
        self._guard = threading.RLock()
        self._key_locks: dict[str, threading.Lock] = {}
        self.hits = 0
        self.misses = 0
        self.corruptions = 0
        self.evictions = 0
        self._remove_stale_temporary_files()

    @staticmethod
    def _key(product_url: str, content_length: int, start: int, end: int) -> str:
        material = f"{product_url}\n{content_length}\n{start}\n{end}".encode()
        return hashlib.sha256(material).hexdigest()

    def _paths(self, key: str) -> tuple[Path, Path]:
        return self.root / f"{key}.bin", self.root / f"{key}.json"

    def _remove_stale_temporary_files(self) -> None:
        for path in self.root.glob("*.tmp"):
            path.unlink(missing_ok=True)

    def _discard(self, data_path: Path, metadata_path: Path) -> None:
        data_path.unlink(missing_ok=True)
        metadata_path.unlink(missing_ok=True)

    def get(self, product_url: str, content_length: int, start: int, end: int) -> bytes | None:
        key = self._key(product_url, content_length, start, end)
        data_path, metadata_path = self._paths(key)
        with self._guard:
            if not data_path.is_file() or not metadata_path.is_file():
                if data_path.exists() or metadata_path.exists():
                    self.corruptions += 1
                    self._discard(data_path, metadata_path)
                self.misses += 1
                return None
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                data = data_path.read_bytes()
                expected = {
                    "product_url": product_url,
                    "content_length": content_length,
                    "start": start,
                    "end": end,
                    "bytes": end - start + 1,
                }
                if any(metadata.get(name) != value for name, value in expected.items()):
                    raise ValueError("cache identity mismatch")
                if len(data) != expected["bytes"] or hashlib.sha256(data).hexdigest() != metadata.get("sha256"):
                    raise ValueError("cache hash mismatch")
            except (OSError, ValueError, json.JSONDecodeError):
                self.corruptions += 1
                self._discard(data_path, metadata_path)
                self.misses += 1
                return None
            now = time.time()
            os.utime(data_path, (now, now)); os.utime(metadata_path, (now, now))
            self.hits += 1
            return data

    def get_or_fetch(
        self, product_url: str, content_length: int, start: int, end: int,
        fetch: Callable[[], bytes],
    ) -> bytes:
        key = self._key(product_url, content_length, start, end)
        with self._guard:
            key_lock = self._key_locks.setdefault(key, threading.Lock())
        with key_lock:
            cached = self.get(product_url, content_length, start, end)
            if cached is not None:
                return cached
            data = fetch()
            expected_length = end - start + 1
            if len(data) != expected_length:
                raise ValueError("retrieved range length does not match cache key")
            digest = hashlib.sha256(data).hexdigest()
            data_path, metadata_path = self._paths(key)
            suffix = f".{os.getpid()}.{threading.get_ident()}.tmp"
            data_tmp = data_path.with_name(data_path.name + suffix)
            metadata_tmp = metadata_path.with_name(metadata_path.name + suffix)
            metadata = {
                "schema_version": 1,
                "product_url": product_url,
                "content_length": content_length,
                "start": start,
                "end": end,
                "bytes": len(data),
                "sha256": digest,
            }
            try:
                with data_tmp.open("wb") as handle:
                    handle.write(data); handle.flush(); os.fsync(handle.fileno())
                with metadata_tmp.open("w", encoding="utf-8") as handle:
                    json.dump(metadata, handle, sort_keys=True)
                    handle.write("\n"); handle.flush(); os.fsync(handle.fileno())
                with self._guard:
                    os.replace(data_tmp, data_path)
                    os.replace(metadata_tmp, metadata_path)
            finally:
                data_tmp.unlink(missing_ok=True)
                metadata_tmp.unlink(missing_ok=True)
            self._evict()
            return data

    def _evict(self) -> None:
        with self._guard:
            entries = sorted(self.root.glob("*.bin"), key=lambda item: item.stat().st_mtime)
            total = sum(item.stat().st_size for item in entries)
            while total > self.max_bytes and entries:
                victim = entries.pop(0)
                size = victim.stat().st_size
                self._discard(victim, victim.with_suffix(".json"))
                total -= size
                self.evictions += 1

    def stats(self) -> dict[str, int]:
        with self._guard:
            allocated = sum(path.stat().st_size for path in self.root.glob("*.bin"))
            return {
                "max_bytes": self.max_bytes,
                "stored_bytes": allocated,
                "entries": sum(1 for _ in self.root.glob("*.bin")),
                "hits": self.hits,
                "misses": self.misses,
                "corruptions": self.corruptions,
                "evictions": self.evictions,
            }
