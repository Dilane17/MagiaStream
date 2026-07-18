"""Accès réseau et extraction des informations de streaming.

Cette implémentation utilise Playwright si disponible pour valider
la fonctionnalité de navigation. Elle retourne un dict minimal
contenant le titre de la page et l'URL courante.

Si Playwright n'est pas installé ou si l'environnement est incompatible,
une `ScraperError` est levée.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict

from magia_stream.config import Config
from magia_stream.exceptions import ScraperError

logger = logging.getLogger(__name__)

try:  # pragma: no cover - runtime availability depends on environment
    from playwright.sync_api import sync_playwright, Error as PlaywrightError
except Exception:  # Playwright absent -> graceful fallback
    sync_playwright = None  # type: ignore
    PlaywrightError = Exception  # type: ignore


@dataclass(slots=True)
class Scraper:
    """Encapsule la logique de récupération des métadonnées."""

    config: Config

    def search_episode(self, serie: str, saison: int, episode: int) -> Dict[str, str]:
        """Recherche basique d'un épisode.

        Actuellement la méthode ouvre simplement la `BASE_URL` et
        retourne un petit jeu de métadonnées pour valider l'intégration
        Playwright. L'implémentation complète (navigation vers la page
        d'un épisode, extraction des sources) sera réalisée en Phase 2.
        """

        logger.debug(
            "Recherche d'épisode: serie=%s saison=%s episode=%s",
            serie,
            saison,
            episode,
        )

        if sync_playwright is None:
            raise ScraperError(
                "Playwright n'est pas disponible. Installez 'playwright' et exécutez 'playwright install'."
            )

        try:  # use Playwright to open the base page and return title/url
            with sync_playwright() as pw:
                browser_type = getattr(pw, self.config.PLAYWRIGHT_BROWSERS, None)
                if browser_type is None:
                    browser_type = pw.chromium

                browser = browser_type.launch(headless=True)
                context = browser.new_context(
                    user_agent=self.config.USER_AGENT,
                    ignore_https_errors=True,
                )
                page = context.new_page()
                page.goto(self.config.BASE_URL, timeout=self.config.TIMEOUT_SECONDS * 1000)
                title = page.title() or ""
                current = page.url
                # cleanup
                context.close()
                browser.close()

                return {"title": title, "url": current, "base": self.config.BASE_URL}

        except PlaywrightError as exc:  # pragma: no cover - environment-dependent
            logger.exception("Erreur Playwright lors du scraping: %s", exc)
            raise ScraperError(f"Erreur Playwright: {exc}") from exc
        except Exception as exc:  # pragma: no cover - unexpected runtime errors
            logger.exception("Erreur inattendue lors du scraping: %s", exc)
            raise ScraperError(str(exc)) from exc
