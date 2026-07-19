"""Cache JSON local léger avec TTL.

Ce module est volontairement indépendant du reste de la base de code. Il fournit
une couche de cache simple basée sur un fichier JSON, avec écriture atomique et
nettoyage des entrées expirées.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

try:
    import fcntl
except Exception:  # pragma: no cover - Windows / environnements sans fcntl
    fcntl = None  # type: ignore


class CacheManager:
    """Gestionnaire de cache JSON local avec TTL.

    Args:
        cache_file: Chemin du fichier JSON. Par défaut, `.magia_cache.json` dans
            le répertoire courant.
        default_ttl_seconds: TTL utilisé si `set()` ne reçoit pas de TTL explicite.
    """

    def __init__(
        self,
        cache_file: str | Path | None = None,
        default_ttl_seconds: int = 24 * 60 * 60,
    ) -> None:
        self.cache_file = Path(cache_file) if cache_file is not None else Path.cwd() / ".magia_cache.json"
        self.default_ttl_seconds = int(default_ttl_seconds)
        self._lock = threading.RLock()

    def get(self, key: str) -> Any | None:
        """Récupère la valeur associée à `key` si elle existe et n'est pas expirée."""

        with self._lock:
            data = self._read_cache()
            entry = data.get(key)
            if not isinstance(entry, dict):
                return None

            expires_at = entry.get("expires_at")
            if not isinstance(expires_at, (int, float)):
                return None

            if expires_at <= time.time():
                return None

            return entry.get("value")

    def set(self, key: str, value: Any, ttl_seconds: int = 86400) -> None:
        """Stocke `value` sous `key` avec une date d'expiration."""

        ttl = int(ttl_seconds) if ttl_seconds is not None else self.default_ttl_seconds
        expires_at = time.time() + max(0, ttl)

        with self._lock:
            data = self._read_cache()
            data[key] = {
                "value": value,
                "expires_at": expires_at,
                "created_at": time.time(),
            }
            self._write_cache(data)

    def clear_expired(self) -> None:
        """Supprime du fichier toutes les entrées périmées."""

        with self._lock:
            data = self._read_cache()
            now = time.time()
            filtered = {
                key: entry
                for key, entry in data.items()
                if isinstance(entry, dict)
                and isinstance(entry.get("expires_at"), (int, float))
                and entry["expires_at"] > now
            }
            self._write_cache(filtered)

    def _read_cache(self) -> dict[str, Any]:
        try:
            if not self.cache_file.exists():
                return {}

            with self.cache_file.open("r", encoding="utf-8") as handle:
                self._lock_file(handle)
                try:
                    payload = json.load(handle)
                finally:
                    self._unlock_file(handle)

            if isinstance(payload, dict):
                return payload
        except Exception:
            return {}

        return {}

    def _write_cache(self, data: dict[str, Any]) -> None:
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(prefix=f".{self.cache_file.name}.", dir=str(self.cache_file.parent))
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    self._lock_file(handle)
                    try:
                        json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
                        handle.flush()
                        os.fsync(handle.fileno())
                    finally:
                        self._unlock_file(handle)
                os.replace(tmp_path, self.cache_file)
            finally:
                try:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                except Exception:
                    pass
        except Exception:
            # Les erreurs d'écriture restent silencieuses pour ne pas casser le flux principal.
            return

    def _lock_file(self, handle: Any) -> None:
        if fcntl is None:
            return
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        except Exception:
            return

    def _unlock_file(self, handle: Any) -> None:
        if fcntl is None:
            return
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except Exception:
            return


__all__ = ["CacheManager"]
