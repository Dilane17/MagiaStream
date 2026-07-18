"""Utilitaires transverses pour MagiaStream.

- Logging configurable (RotatingFileHandler optionnel, JSON optionnel)
- Retry decorator basé sur tenacity
- safe_filename pour normaliser noms de fichier
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import re
from pathlib import Path
from typing import Callable, Any

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

DEFAULT_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def setup_logging(level: int = logging.INFO, log_file: Path | None = None, json_format: bool = False) -> None:
    """Configure le logging global.

    - `level`: niveau de logging
    - `log_file`: si fourni, active la rotation journalière
    - `json_format`: si True, les logs sont formatés en JSON simple
    """

    root = logging.getLogger()
    root.setLevel(level)

    # handler de console
    console_handler = logging.StreamHandler()
    if json_format:
        console_handler.setFormatter(JsonLogFormatter())
    else:
        console_handler.setFormatter(logging.Formatter(DEFAULT_LOG_FORMAT))
    root.addHandler(console_handler)

    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            filename=str(log_file), maxBytes=10 * 1024 * 1024, backupCount=5
        )
        if json_format:
            file_handler.setFormatter(JsonLogFormatter())
        else:
            file_handler.setFormatter(logging.Formatter(DEFAULT_LOG_FORMAT))
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


def tenacity_retry(**kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Retourne un décorateur `retry` basé sur tenacity avec paramètres raisonnables.

    Usage:
    @tenacity_retry(stop_max_attempts=5)
    def foo(...):
        ...
    """

    stop = kwargs.pop("stop", stop_after_attempt(3))
    wait = kwargs.pop("wait", wait_exponential(multiplier=1, min=1, max=10))
    retry_on = kwargs.pop("retry", retry_if_exception_type(Exception))

    def _decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        return retry(stop=stop, wait=wait, retry=retry_on)(fn)

    return _decorator


def safe_filename(name: str, max_length: int = 200) -> str:
    """Retourne un nom de fichier sûr en supprimant caractères invalides.

    Règles : remplace les espaces par des underscores, garde alphanumériques, '-', '_', '.'
    """

    name = name.strip()
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"[^\w\-.]", "", name)
    return name[:max_length]
