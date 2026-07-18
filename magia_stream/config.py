"""Configuration centrale de MagiaStream avec hydratation depuis .env."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


load_dotenv()


@dataclass(slots=True)
class Config:
    """Contient les valeurs par défaut et les chemins de sortie.

    Utiliser `Config.from_env()` pour hydrater depuis l'environnement.
    """

    BASE_URL: str = "https://voir-anime.to"
    output_dir: Path = field(default_factory=lambda: Path.cwd() / "downloads")
    temp_dir: Path = field(default_factory=lambda: Path.cwd() / ".tmp")
    user_agent: str = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
    timeout_seconds: int = 30
    aria2c_path: str = "aria2c"
    playwright_browsers: str = "chromium"
    log_level: str = "INFO"
    log_json: bool = False
    aria2c_opts: str = "-x 16 -s 16"

    @classmethod
    def from_env(cls) -> "Config":
        """Construit une config à partir des variables d'environnement.

        Valide sommairement les types et retourne une instance.
        """

        def get(key: str, default: Optional[str] = None) -> Optional[str]:
            return os.getenv(key, default)

        base = get("BASE_URL", cls.BASE_URL)
        output = Path(get("OUTPUT_DIR", str(cls.output_dir)))
        temp = Path(get("TEMP_DIR", str(cls.temp_dir)))
        user_agent = get("USER_AGENT", cls.user_agent)
        timeout = int(get("TIMEOUT_SECONDS", str(cls.timeout_seconds)))
        aria2c_path = get("ARIA2C_PATH", cls.aria2c_path)
        playwright_browsers = get("PLAYWRIGHT_BROWSERS", cls.playwright_browsers)
        log_level = get("LOG_LEVEL", cls.log_level)
        log_json = get("LOG_JSON", "false").lower() in ("1", "true", "yes")
        aria2c_opts = get("ARIA2C_OPTS", cls.aria2c_opts)

        cfg = cls(
            BASE_URL=base,  # type: ignore[arg-type]
            output_dir=output,
            temp_dir=temp,
            user_agent=user_agent,
            timeout_seconds=timeout,
            aria2c_path=aria2c_path,
            playwright_browsers=playwright_browsers,
            log_level=log_level,
            log_json=log_json,
            aria2c_opts=aria2c_opts,
        )

        # validations simples
        if not cfg.BASE_URL.startswith("http"):
            raise ValueError("BASE_URL doit commencer par http ou https")

        return cfg
