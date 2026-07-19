"""Utilitaires transverses pour MagiaStream.

- Logging configurable (RotatingFileHandler optionnel, JSON optionnel)
- Retry decorator basé sur tenacity
- Fonctions utilitaires pour fichiers
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import re
from pathlib import Path
from typing import Any, Callable

try:
    from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

    HAS_TENACITY = True
except Exception:
    HAS_TENACITY = False
    # fallback: we'll implement a simple retry decorator below

DEFAULT_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def setup_logging(level: int = logging.INFO, log_file: Path | None = None, json_format: bool = False) -> None:
    """Configure le logging global.

    - `level`: niveau de logging
    - `log_file`: si fourni, active la rotation (max 5MB, 5 backups)
    - `json_format`: si True, les logs sont formatés en JSON simple
    """

    root = logging.getLogger()
    root.setLevel(level)

    # console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(JsonLogFormatter() if json_format else logging.Formatter(DEFAULT_LOG_FORMAT))
    root.addHandler(console_handler)

    if log_file:
        # ensure directory exists for log file
        try:
            ensure_directory(log_file.parent)
        except Exception:
            pass
        file_handler = logging.handlers.RotatingFileHandler(
            filename=str(log_file), maxBytes=5 * 1024 * 1024, backupCount=5
        )
        file_handler.setFormatter(JsonLogFormatter() if json_format else logging.Formatter(DEFAULT_LOG_FORMAT))
        root.addHandler(file_handler)


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # pragma: no cover - small helper
        payload = {
            "ts": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def tenacity_retry(
    retries: int = 3, min_wait: int = 1, max_wait: int = 10, retry_exceptions: Any = Exception
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Décorateur configurable; utilise `tenacity` si disponible sinon un fallback.

    - `retries`: nombre maximal de tentatives
    - `min_wait` / `max_wait`: attente exponentielle
    - `retry_exceptions`: exceptions à retenter
    """

    if HAS_TENACITY:
        stop = stop_after_attempt(retries)
        wait = wait_exponential(multiplier=1, min=min_wait, max=max_wait)
        retry_on = retry_if_exception_type(retry_exceptions)

        def _decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            return retry(stop=stop, wait=wait, retry=retry_on)(fn)

        return _decorator

    # simple fallback implementation
    import functools
    import time

    def _decorator(fn: Callable[..., Any]) -> Callable[..., Any]:  # type: ignore
        @functools.wraps(fn)
        def _wrapped(*args: Any, **kwargs: Any) -> Any:
            attempt = 0
            while True:
                try:
                    return fn(*args, **kwargs)
                except retry_exceptions:
                    attempt += 1
                    if attempt > retries:
                        raise
                    sleep_for = min(max_wait, min_wait * (2 ** (attempt - 1)))
                    time.sleep(sleep_for)

        return _wrapped

    return _decorator


def sanitize_filename(name: str, max_length: int = 200) -> str:
    """Sanitize a filename for safe use on most filesystems.

    Replace whitespace by underscore and remove unsafe characters.
    """

    name = name.strip()
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"[^\w\-.]", "", name)
    return name[:max_length]


def get_file_size(path: Path) -> int:
    """Retourne la taille du fichier en octets, 0 si absent."""

    try:
        return path.stat().st_size
    except Exception:
        return 0


def human_readable_size(num: int, suffix: str = "B") -> str:
    """Convertit une taille en octets vers une représentation lisible."""

    for unit in ["", "K", "M", "G", "T", "P"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0  # type: ignore
    return f"{num:.1f}Y{suffix}"


def ensure_directory(path: Path) -> Path:
    """Crée le dossier cible si nécessaire et le retourne.

    Utilisé par le downloader pour s'assurer que le répertoire de sortie existe.
    """

    path.mkdir(parents=True, exist_ok=True)
    return path
