"""Gestion centralisée de Playwright pour les opérations de scraping.

Le module expose un `BrowserManager` synchrone qui encapsule :
- l'initialisation de Playwright,
- le lancement de Chromium,
- la création d'un `BrowserContext` standardisé,
- le nettoyage complet des ressources.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional

try:  # pragma: no cover - depends on environment
    from playwright.sync_api import (
        Browser,
        BrowserContext,
        Page,
        Playwright,
        sync_playwright,
    )
    from playwright.sync_api import (
        Error as PlaywrightError,
    )
except Exception:  # pragma: no cover - fallback when Playwright is unavailable
    sync_playwright = None  # type: ignore
    Browser = BrowserContext = Page = Playwright = object  # type: ignore
    PlaywrightError = Exception  # type: ignore

try:  # pragma: no cover - optional dependency
    from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
except Exception:  # pragma: no cover - fallback without tenacity

    def retry(*_args: Any, **_kwargs: Any):  # type: ignore
        def decorator(fn):
            return fn

        return decorator

    def stop_after_attempt(*_args: Any, **_kwargs: Any):  # type: ignore
        return None

    def wait_exponential(*_args: Any, **_kwargs: Any):  # type: ignore
        return None

    def retry_if_exception_type(*_args: Any, **_kwargs: Any):  # type: ignore
        return None


logger = logging.getLogger(__name__)


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
DEFAULT_VIEWPORT = {"width": 1920, "height": 1080}
DEFAULT_LOCALE = "fr-FR"


@dataclass
class BrowserManager:
    """Cycle de vie Playwright/Chromium avec un contexte standardisé.

    La classe peut être utilisée comme context manager :

    ```python
    with BrowserManager() as browser_manager:
        page = browser_manager.get_page()
    ```
    """

    headless: bool = False
    user_agent: str = DEFAULT_USER_AGENT
    user_data_dir: Optional[str] = None
    viewport: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_VIEWPORT))
    locale: str = DEFAULT_LOCALE
    timezone_id: str = "Europe/Paris"
    extra_http_headers: dict[str, str] = field(default_factory=lambda: {"accept-language": DEFAULT_LOCALE})

    playwright: Optional[Playwright] = field(init=False, default=None)
    browser: Optional[Browser] = field(init=False, default=None)
    context: Optional[BrowserContext] = field(init=False, default=None)
    _playwright_ctx: Optional[Any] = field(init=False, default=None, repr=False)

    def __enter__(self) -> BrowserManager:
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    def start(self) -> BrowserManager:
        """Démarre Playwright, le navigateur Chromium et le contexte par défaut."""

        if self.context is not None:
            return self

        if sync_playwright is None:
            raise RuntimeError("Playwright n'est pas installé dans cet environnement")

        self._playwright_ctx = sync_playwright()
        self.playwright = self._playwright_ctx.__enter__()

        if self.user_data_dir:
            import os
            os.makedirs(self.user_data_dir, exist_ok=True)
            self.context = self.playwright.chromium.launch_persistent_context(
                user_data_dir=self.user_data_dir,
                headless=self.headless,
                user_agent=self.user_agent,
                viewport=self.viewport,
                locale=self.locale,
                timezone_id=self.timezone_id,
                extra_http_headers=self.extra_http_headers
            )
            self._inject_init_scripts(self.context)
        else:
            self.browser = self.playwright.chromium.launch(headless=self.headless)
            self.context = self._create_context()
            
        logger.debug("Playwright démarré (headless=%s)", self.headless)
        return self

    def stop(self) -> None:
        """Ferme le contexte, le navigateur et l'instance Playwright."""

        context = self.context
        browser = self.browser
        playwright_ctx = self._playwright_ctx

        self.context = None
        self.browser = None
        self.playwright = None
        self._playwright_ctx = None

        if context is not None:
            try:
                context.close()
            except Exception:
                logger.debug("Erreur lors de la fermeture du BrowserContext", exc_info=True)

        if browser is not None:
            try:
                browser.close()
            except Exception:
                logger.debug("Erreur lors de la fermeture du navigateur", exc_info=True)

        if playwright_ctx is not None:
            try:
                playwright_ctx.__exit__(None, None, None)
            except Exception:
                logger.debug("Erreur lors de l'arrêt de Playwright", exc_info=True)

    def _create_context(self, **overrides: Any) -> BrowserContext:
        if self.browser is None:
            raise RuntimeError("Le navigateur n'est pas démarré")

        context_kwargs: dict[str, Any] = {
            "user_agent": overrides.pop("user_agent", self.user_agent),
            "viewport": overrides.pop("viewport", dict(self.viewport)),
            "locale": overrides.pop("locale", self.locale),
            "timezone_id": overrides.pop("timezone_id", self.timezone_id),
            "extra_http_headers": overrides.pop("extra_http_headers", dict(self.extra_http_headers)),
        }
        context_kwargs.update(overrides)

        context = self.browser.new_context(**context_kwargs)
        self._inject_init_scripts(context)
        return context

    def _inject_init_scripts(self, context: BrowserContext) -> None:
        context.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['fr-FR', 'fr'] });
            Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
            """
        )

    def new_context(self, **overrides: Any) -> BrowserContext:
        """Crée un nouveau contexte Playwright avec les paramètres standards."""

        if self.user_data_dir:
            raise RuntimeError("Impossible de créer un nouveau contexte quand user_data_dir est utilisé")
        return self._create_context(**overrides)

    def get_page(self) -> Page:
        """Retourne une nouvelle page issue du contexte par défaut."""

        if self.context is None:
            raise RuntimeError("Le BrowserManager doit être démarré avant get_page()")
            
        if self.user_data_dir and self.context.pages:
            # Réutiliser la page par défaut du contexte persistant
            return self.context.pages[0]
            
        return self.context.new_page()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(PlaywrightError),
        reraise=True,
    )
    def goto_with_retry(self, page: Page, url: str, timeout: int = 30_000) -> None:
        """Navigue vers une URL en appliquant un retry exponentiel sur les erreurs Playwright."""

        logger.debug("Navigation vers %s (timeout=%s)", url, timeout)
        page.goto(url, timeout=timeout)

    def close(self) -> None:
        """Alias de compatibilité pour `stop()`."""

        self.stop()


@contextmanager
def managed_browser() -> Iterator[BrowserManager]:
    """Context manager de compatibilité pour le code existant."""

    manager = BrowserManager()
    with manager:
        yield manager
