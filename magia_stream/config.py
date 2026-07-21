"""Configuration centrale de MagiaStream avec hydratation depuis .env."""

from __future__ import annotations

import os
from dataclasses import MISSING, dataclass, field
from pathlib import Path
from typing import Dict

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - fallback when python-dotenv is not installed

    def load_dotenv(*_args, **_kwargs):  # type: ignore
        return None


from magia_stream.exceptions import ConfigError

load_dotenv()


@dataclass(slots=True)
class Config:
    """Contient les valeurs par défaut et les chemins de sortie.

    Utiliser `Config.from_env()` pour hydrater depuis l'environnement.
    """

    BASE_URL: str = "https://voir-anime.to"
    OUTPUT_DIR: Path = field(default_factory=lambda: Path.cwd() / "downloads")
    TEMP_DIR: Path = field(default_factory=lambda: Path.cwd() / ".tmp")
    USER_DATA_DIR: Path = field(default_factory=lambda: Path.cwd() / ".playwright_profile")
    USER_AGENT: str = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
    TIMEOUT_SECONDS: int = 30
    ARIA2C_PATH: str = "aria2c"
    PLAYWRIGHT_BROWSERS: str = "chromium"
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = False
    ARIA2C_OPTS: str = "-x 16 -s 16"
    MAX_RETRIES: int = 3
    HEADLESS: bool = True

    @classmethod
    def from_env(cls) -> "Config":
        """Construit une config à partir des variables d'environnement.

        Lève `ConfigError` si des valeurs critiques sont manquantes ou invalides.
        """

        # fetch defaults from dataclass fields to avoid potential descriptor issues
        fields = getattr(cls, "__dataclass_fields__", {})

        def _default(name: str, fallback: str) -> str:
            if name in fields:
                f = fields[name]
                if f.default is not MISSING:
                    return f.default
                if getattr(f, "default_factory", MISSING) is not MISSING:
                    try:
                        return f.default_factory()
                    except Exception:
                        return fallback
            return fallback

        try:
            base_default = _default("BASE_URL", cls.BASE_URL)  # type: ignore
            base = os.getenv("BASE_URL", base_default)
            if not isinstance(base, str) or not base.startswith("http"):
                raise ConfigError("BASE_URL invalide")

            output_default = _default("OUTPUT_DIR", str(cls.OUTPUT_DIR))  # type: ignore
            temp_default = _default("TEMP_DIR", str(cls.TEMP_DIR))  # type: ignore
            user_data_default = _default("USER_DATA_DIR", str(cls.USER_DATA_DIR))  # type: ignore

            output = Path(os.getenv("OUTPUT_DIR", str(output_default)))
            temp = Path(os.getenv("TEMP_DIR", str(temp_default)))
            user_data_dir = Path(os.getenv("USER_DATA_DIR", str(user_data_default)))
            user_agent = os.getenv("USER_AGENT", _default("USER_AGENT", cls.USER_AGENT))  # type: ignore
            timeout = int(os.getenv("TIMEOUT_SECONDS", str(_default("TIMEOUT_SECONDS", cls.TIMEOUT_SECONDS))))  # type: ignore
            aria2c_path = os.getenv("ARIA2C_PATH", _default("ARIA2C_PATH", cls.ARIA2C_PATH))  # type: ignore
            playwright_browsers = os.getenv(
                "PLAYWRIGHT_BROWSERS",
                _default("PLAYWRIGHT_BROWSERS", cls.PLAYWRIGHT_BROWSERS),  # type: ignore
            )
            log_level = os.getenv("LOG_LEVEL", _default("LOG_LEVEL", cls.LOG_LEVEL))  # type: ignore
            log_json = os.getenv("LOG_JSON", str(_default("LOG_JSON", cls.LOG_JSON))).lower() in ("1", "true", "yes")  # type: ignore
            aria2c_opts = os.getenv("ARIA2C_OPTS", _default("ARIA2C_OPTS", cls.ARIA2C_OPTS))  # type: ignore
            max_retries = int(os.getenv("MAX_RETRIES", str(_default("MAX_RETRIES", cls.MAX_RETRIES))))  # type: ignore
            headless = os.getenv("HEADLESS", str(_default("HEADLESS", cls.HEADLESS))).lower() in ("1", "true", "yes")  # type: ignore

        except ValueError as exc:
            raise ConfigError(f"Erreur de parsing de la config: {exc}") from exc

        cfg = cls(
            BASE_URL=base,
            OUTPUT_DIR=output,
            TEMP_DIR=temp,
            USER_DATA_DIR=user_data_dir,
            USER_AGENT=user_agent,
            TIMEOUT_SECONDS=timeout,
            ARIA2C_PATH=aria2c_path,
            PLAYWRIGHT_BROWSERS=playwright_browsers,
            LOG_LEVEL=log_level,
            LOG_JSON=log_json,
            ARIA2C_OPTS=aria2c_opts,
            MAX_RETRIES=max_retries,
            HEADLESS=headless,
        )

        # validations simples
        if not cfg.OUTPUT_DIR:
            raise ConfigError("OUTPUT_DIR est requis")

        return cfg

    def to_dict(self) -> Dict[str, str]:
        """Retourne la config sous forme de dict simple pour affichage."""

        return {
            "BASE_URL": self.BASE_URL,
            "OUTPUT_DIR": str(self.OUTPUT_DIR),
            "TEMP_DIR": str(self.TEMP_DIR),
            "USER_DATA_DIR": str(self.USER_DATA_DIR),
            "USER_AGENT": self.USER_AGENT,
            "TIMEOUT_SECONDS": str(self.TIMEOUT_SECONDS),
            "ARIA2C_PATH": self.ARIA2C_PATH,
            "PLAYWRIGHT_BROWSERS": self.PLAYWRIGHT_BROWSERS,
            "LOG_LEVEL": self.LOG_LEVEL,
            "LOG_JSON": str(self.LOG_JSON),
            "ARIA2C_OPTS": self.ARIA2C_OPTS,
            "MAX_RETRIES": str(self.MAX_RETRIES),
        }

    def save_to_env(self, path: Path) -> None:
        """Écrit les variables de configuration dans un fichier .env (optionnel)."""

        with path.open("w", encoding="utf8") as fh:
            for k, v in self.to_dict().items():
                fh.write(f"{k}={v}\n")
        return None
