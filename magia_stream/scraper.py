"""Scraper core utilisant BrowserManager pour naviguer et extraire des donnees.

Adaptations specifiques pour https://voir-anime.to :
- slug strategy predominante (/anime/{slug}/)
- fallback : parcours des ancres sur la home et fuzzy match
- patterns d'URL d'episode courants : {slug}-{ep:02d}-vf, {slug}-{ep:02d}-vostfr, /{ep}/, /episode-{ep}/
"""

from __future__ import annotations

import logging
import random
import re
import shutil
import tempfile
import time
import unicodedata
import uuid
from difflib import get_close_matches
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote_plus, urljoin, urlparse

try:  # pragma: no cover - optional dependency in some environments
    import requests
except Exception:  # pragma: no cover - fallback when requests is unavailable
    requests = None  # type: ignore

try:  # pragma: no cover - fallback when Playwright is unavailable
    from magia_stream.browser import BrowserManager
except Exception:  # pragma: no cover - keep import-time failure isolated
    BrowserManager = None  # type: ignore

from magia_stream.cache import CacheManager
from magia_stream.exceptions import ScraperError
from magia_stream.models import Episode

logger = logging.getLogger(__name__)


class Scraper:
    def __init__(self, config: Any = None):
        # lazy import to avoid cycles; accept either Config or None
        if config is None:
            try:
                from magia_stream.config import Config

                config = Config.from_env()
            except Exception:
                try:
                    from magia_stream.config import Config

                    config = Config()
                except Exception:
                    config = None

        self.config = config

        cache_base_dir = (
            getattr(self.config, "TEMP_DIR", Path.cwd() / ".tmp") if self.config is not None else Path.cwd() / ".tmp"
        )
        self.cache = CacheManager(
            cache_file=Path(cache_base_dir) / ".magia_cache.json",
            default_ttl_seconds=24 * 60 * 60,
        )

        browser_user_agent = getattr(self.config, "USER_AGENT", None)
        browser_headless = getattr(self.config, "HEADLESS", True)
        
        if BrowserManager is None:
            self.browser_manager = None
        else:
            kwargs = {"headless": browser_headless}
            if browser_user_agent:
                kwargs["user_agent"] = browser_user_agent
            self.browser_manager = BrowserManager(**kwargs)

    @staticmethod
    def _normalize_for_match(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value)
        normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        return re.sub(r"\s+", " ", normalized).strip().lower()

    @staticmethod
    def _slugify(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value)
        normalized = normalized.encode("ascii", "ignore").decode("ascii")
        normalized = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-")
        return normalized.lower()

    def _series_cache_key(self, serie_name: str) -> str:
        return f"series_page:{self._slugify(serie_name)}"

    @staticmethod
    def _extract_slug_from_page_url(page_url: str) -> Optional[str]:
        parts = page_url.strip("/").split("/")
        try:
            idx = parts.index("anime")
            if idx + 1 < len(parts):
                return parts[idx + 1]
        except ValueError:
            return None
        return None

    @staticmethod
    def _resolution_height(resolution: Optional[str]) -> Optional[int]:
        if not resolution:
            return None
        match = re.search(r"(\d{3,4})", str(resolution))
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None

    @staticmethod
    def _parse_attribute_list(raw_value: str) -> dict[str, str]:
        attrs: dict[str, str] = {}
        for match in re.finditer(r"([A-Z0-9-]+)=(\".*?\"|[^,]*)", raw_value):
            key = match.group(1).strip().upper()
            value = match.group(2).strip().strip('"')
            attrs[key] = value
        return attrs

    @staticmethod
    def _variant_resolution_height(attrs: dict[str, str]) -> Optional[int]:
        resolution = attrs.get("RESOLUTION")
        if not resolution:
            return None
        match = re.search(r"(\d{2,4})x(\d{2,4})", resolution)
        if not match:
            return None
        try:
            return int(match.group(2))
        except ValueError:
            return None

    @staticmethod
    def _variant_bandwidth(attrs: dict[str, str]) -> int:
        bandwidth = attrs.get("BANDWIDTH")
        if not bandwidth:
            return 0
        try:
            return int(bandwidth)
        except ValueError:
            return 0

    def _choose_hls_variant(self, variants: list[dict[str, Any]], resolution: Optional[str]) -> Optional[str]:
        if not variants:
            return None

        target_height = self._resolution_height(resolution)
        enriched: list[dict[str, Any]] = []
        for variant in variants:
            attrs = variant.get("attrs", {}) or {}
            enriched.append(
                {
                    "url": variant.get("url"),
                    "attrs": attrs,
                    "height": self._variant_resolution_height(attrs),
                    "bandwidth": self._variant_bandwidth(attrs),
                }
            )

        if target_height is not None:
            exact = [v for v in enriched if v["height"] == target_height]
            if exact:
                exact.sort(key=lambda item: item["bandwidth"], reverse=True)
                return exact[0]["url"]

            above = [v for v in enriched if isinstance(v["height"], int) and v["height"] >= target_height]
            if above:
                above.sort(key=lambda item: (item["height"], item["bandwidth"]))
                return above[0]["url"]

            below = [v for v in enriched if isinstance(v["height"], int)]
            if below:
                below.sort(key=lambda item: (item["height"], item["bandwidth"]), reverse=True)
                return below[0]["url"]

        resolved = [v for v in enriched if v.get("url")]
        if not resolved:
            return None

        resolved.sort(
            key=lambda item: (
                item["height"] if isinstance(item["height"], int) else 0,
                item["bandwidth"],
            ),
            reverse=True,
        )
        return resolved[0]["url"]

    def _fetch_text(
        self,
        url: str,
        scratch_dir: Path,
        trace: bool = False,
        referer: Optional[str] = None,
        browser_manager: Optional[Any] = None,
    ) -> str:
        page_referer = referer or getattr(self.config, "BASE_URL", "https://voir-anime.to")
        headers = {
            "User-Agent": getattr(self.config, "USER_AGENT", "Mozilla/5.0"),
            "Referer": page_referer,
            "Origin": page_referer.rstrip("/"),  # type: ignore
        }
        timeout = int(getattr(self.config, "TIMEOUT_SECONDS", 30))

        # Secours 1 : Utilisation du browser context global si disponible
        browser_context = getattr(browser_manager, "context", None) if browser_manager is not None else None
        if browser_context is not None:
            try:
                response = browser_context.request.get(url, headers=headers, timeout=timeout * 1000)
                status = getattr(response, "status", 0)
                if status == 200:
                    text = response.text()
                    if text:
                        return text
                elif trace:
                    print(f"[trace] browser_context.request.get a renvoye le statut {status} pour {url}")
            except Exception as exc:
                if trace:
                    print(f"[trace] browser-context HLS fetch failed for {url}: {exc}")

        # Secours 2 : Requete classique HTTP isolée
        if requests is not None:
            try:
                response = requests.get(url, headers=headers, timeout=timeout)  # type: ignore
                response.raise_for_status()
                text = response.text
                return text
            except Exception as exc:
                if trace:
                    print(f"[trace] requests HLS fetch failed for {url}: {exc}")
        else:  # pragma: no cover
            import urllib.request

            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                text = response.read().decode("utf-8", errors="ignore")
                return text

        return ""

    def _candidate_referers(self, current_url: str, page_referer: Optional[str] = None) -> list[str]:
        referers: list[str] = []
        for candidate in [page_referer, current_url, getattr(self.config, "BASE_URL", "https://voir-anime.to")]:
            if isinstance(candidate, str) and candidate:
                normalized = candidate.rstrip("/")
                if normalized not in referers:
                    referers.append(normalized)
        return referers

    def _resolve_hls_variant_playlist(
        self,
        manifest_url: str,
        resolution: Optional[str],
        scratch_dir: Path,
        trace: bool = False,
        max_depth: int = 5,
        page: Optional[Any] = None,
    ) -> str:
        current_url = manifest_url
        seen: set[str] = set()

        for depth in range(max_depth):
            if current_url in seen:
                break
            seen.add(current_url)

            try:
                manifest_text = ""
                for referer in self._candidate_referers(current_url):
                    try:
                        manifest_text = self._fetch_text(
                            current_url,
                            scratch_dir=scratch_dir,
                            trace=trace,
                            referer=referer,
                            browser_manager=self.browser_manager,
                        )
                        if manifest_text:
                            break
                    except Exception:
                        continue

                if not manifest_text:
                    if trace:
                        print(f"[trace] Aucun contenu de manifeste recupere pour {current_url}")
                    return current_url
            except Exception as exc:
                if trace:
                    print(f"[trace] HLS fetch failed at depth {depth + 1}: {current_url} ({exc})")
                break

            if "#EXT-X-STREAM-INF" not in manifest_text:
                return current_url

            variants: list[dict[str, Any]] = []
            pending_attrs: Optional[dict[str, str]] = None
            for raw_line in manifest_text.splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                if line.startswith("#EXT-X-STREAM-INF"):
                    attr_blob = line.partition(":")[2]
                    pending_attrs = self._parse_attribute_list(attr_blob)
                    continue
                if line.startswith("#"):
                    continue
                if pending_attrs is not None:
                    variants.append({"url": urljoin(current_url, line), "attrs": pending_attrs})
                    pending_attrs = None

            if not variants:
                return current_url

            chosen_url = self._choose_hls_variant(variants, resolution)
            if not chosen_url:
                return current_url

            if ".m3u8" in chosen_url.lower():
                current_url = chosen_url
                continue

            return chosen_url

        return current_url

    def _normalize_stream_candidate(
        self,
        stream_url: str,
        resolution: Optional[str],
        scratch_dir: Path,
        trace: bool = False,
        page: Optional[Any] = None,
    ) -> str:
        if not isinstance(stream_url, str):
            return ""

        candidate = stream_url.strip()
        if not candidate:
            return ""

        if ".m3u8" not in candidate.lower():
            return candidate

        return self._resolve_hls_variant_playlist(candidate, resolution, scratch_dir, trace=trace, page=page)

    @staticmethod
    def _page_title(page: Any) -> str:
        try:
            return page.title()
        except Exception:
            return ""

    def _save_trace_dump(self, scratch_dir: Path, filename: str, content: str) -> None:
        try:
            (scratch_dir / filename).write_text(content, encoding="utf-8")
        except Exception:
            pass

    def _series_page_patterns(self, base_url: str, slug: str, episode: int) -> list[str]:
        base = base_url.rstrip("/")
        return [
            f"{base}/anime/{slug}/{slug}-{episode:02d}-vf/",
            f"{base}/anime/{slug}/{slug}-{episode:02d}-vostfr/",
            f"{base}/anime/{slug}/{episode:02d}/",
            f"{base}/anime/{slug}/episode-{episode}/",
        ]

    def _search_series_page_url(self, serie_name: str, trace: bool = False) -> Optional[str]:
        cache_key = self._series_cache_key(serie_name)
        cached_url = self.cache.get(cache_key)
        if isinstance(cached_url, str) and cached_url.startswith("http"):
            if trace:
                print(f"[trace] Using cached series page URL: {cached_url}")
            return cached_url

        query_norm = self._normalize_for_match(serie_name)
        if self.browser_manager is None:
            return None

        try:
            with self.browser_manager as bm:
                page = bm.get_page()

                def _on_response(resp):
                    try:
                        status = resp.status
                        url = resp.url
                        logger.debug("[response] %s %s", status, url)
                        if trace:
                            print(f"[trace][response] {status} {url}")
                        if status in (403, 503):
                            logger.warning("[Cloudflare] Blocage detecte sur %s (status=%s)", url, status)
                    except Exception:
                        logger.debug("Erreur dans le handler response", exc_info=True)

                try:
                    page.on("response", _on_response)
                except Exception:
                    logger.debug("Impossible d'attacher response handler", exc_info=True)

                timeout_ms = int(getattr(self.config, "TIMEOUT_SECONDS", 30)) * 1000
                bm.goto_with_retry(page, getattr(self.config, "BASE_URL", "https://voir-anime.to"), timeout=timeout_ms)

                search_selectors = [
                    'input[name="s"]',
                    'input[type="search"]',
                    'input[placeholder*="recherche"]',
                    'input[placeholder*="Rechercher"]',
                    'input[placeholder*="search"]',
                ]
                search_selector = None
                for selector in search_selectors:
                    try:
                        if page.query_selector(selector):
                            search_selector = selector
                            if trace:
                                print(f"[trace] Using search selector: {selector}")
                            break
                    except Exception:
                        continue

                if not search_selector:
                    logger.debug("Aucun champ de recherche trouve sur la home")
                    return None

                def _load_search_results() -> None:
                    try:
                        page.fill(search_selector, serie_name)
                        time.sleep(random.uniform(0.5, 1.2))
                        page.press(search_selector, "Enter")
                        time.sleep(2.5)
                    except Exception:
                        search_url = f"{getattr(self.config, 'BASE_URL', 'https://voir-anime.to').rstrip('/')}?s={quote_plus(serie_name)}&post_type=wp-manga"
                        if trace:
                            print(f"[trace] Fallback navigating to search URL: {search_url}")
                        bm.goto_with_retry(page, search_url, timeout=timeout_ms)
                        time.sleep(2)

                _load_search_results()

                try:
                    page.wait_for_selector('a[href*="/anime/"]', timeout=10_000)
                except Exception:
                    pass

                anchors = page.query_selector_all('a[href*="/anime/"]')
                if trace:
                    print(f"[trace] Found {len(anchors)} anchors matching a[href*='/anime/']")

                results: list[tuple[str, str]] = []
                for anchor in anchors:
                    try:
                        href = (anchor.get_attribute("href") or "").strip()
                        text = (anchor.inner_text() or "").strip()
                        if href and text:
                            results.append((href, text))
                    except Exception:
                        continue

                if not results:
                    try:
                        search_url = f"{getattr(self.config, 'BASE_URL', 'https://voir-anime.to').rstrip('/')}?s={quote_plus(serie_name)}&post_type=wp-manga"
                        if trace:
                            print(f"[trace] No anchors — navigating to fallback search URL: {search_url}")
                        bm.goto_with_retry(page, search_url, timeout=timeout_ms)
                        time.sleep(2)
                        anchors = page.query_selector_all('a[href*="/anime/"]')
                        results = []
                        for anchor in anchors:
                            try:
                                href = (anchor.get_attribute("href") or "").strip()
                                text = (anchor.inner_text() or "").strip()
                                if href and text:
                                    results.append((href, text))
                            except Exception:
                                continue
                    except Exception:
                        logger.debug("Fallback GET search navigation failed", exc_info=True)

                normalized_results: list[tuple[str, str, str]] = []
                for href, text in results:
                    normalized_results.append((href, text, self._normalize_for_match(text)))

                for href, text, normalized_text in normalized_results:
                    if query_norm in normalized_text or normalized_text in query_norm:
                        if trace:
                            print(f"[trace] Found result by contains: {text} -> {href}")
                        self.cache.set(cache_key, href, ttl_seconds=7 * 24 * 60 * 60)
                        return href

                titles = [normalized_text for _, _, normalized_text in normalized_results]
                if titles:
                    matches = get_close_matches(query_norm, titles, n=1, cutoff=0.45)
                    if matches:
                        matched = matches[0]
                        for href, text, normalized_text in normalized_results:
                            if normalized_text == matched:
                                if trace:
                                    print(f"[trace] Found result by fuzzy: {text} -> {href}")
                                self.cache.set(cache_key, href, ttl_seconds=7 * 24 * 60 * 60)
                                return href
        except Exception:
            logger.debug("Browser unavailable during series page search", exc_info=True)

        return None

    def search_series_all_results(self, serie_name: str, trace: bool = False) -> list[dict[str, str]]:
        if self.browser_manager is None:
            return []

        try:
            with self.browser_manager.get_page() as page:
                bm = self.browser_manager
                timeout_ms = 30000
                base_url = getattr(self.config, "BASE_URL", "https://voir-anime.to").rstrip("/")

                # Navigate to home
                bm.goto_with_retry(page, f"{base_url}/", timeout=timeout_ms)
                import time, random

                time.sleep(2)

                # 1. Capture currently visible anime links on the homepage to exclude them later
                existing_hrefs = set()
                try:
                    for a in page.query_selector_all('a[href*="/anime/"]'):
                        if a.is_visible():
                            href = (a.get_attribute("href") or "").strip()
                            if href:
                                existing_hrefs.add(href)
                except Exception:
                    pass

                # 2. Find the VF search input
                search_selector = None
                for selector in [
                    "input[placeholder*='VF']:visible",
                    "input[placeholder*='vf']:visible",
                    ".search-input:visible",
                    "input[name='s']:visible",
                ]:
                    try:
                        if page.query_selector(selector):
                            search_selector = selector
                            break
                    except Exception:
                        continue

                if not search_selector:
                    return []

                # 3. Type into the input to trigger the AJAX dropdown
                # Using type instead of fill to trigger keyboard events for autocomplete
                page.locator(search_selector).first.type(serie_name, delay=150)
                time.sleep(3)  # Wait for AJAX dropdown to appear

                # 4. Extract NEW links that appeared (the dropdown results)
                results: list[dict[str, str]] = []
                anchors = page.query_selector_all('a[href*="/anime/"]')
                for anchor in anchors:
                    try:
                        if not anchor.is_visible():
                            continue

                        href = (anchor.get_attribute("href") or "").strip()
                        text = (anchor.inner_text() or "").strip()

                        if href and text and href not in existing_hrefs:
                            slug = self._extract_slug_from_page_url(href)
                            # Remove weird newlines or numbers from text (like "11" or "VF" if they are standalone tags)
                            # But dropdown usually has the full title.
                            if slug and len(text) > 2:
                                # We only add if it's unique by slug
                                if not any(r["slug"] == slug for r in results):
                                    # Cleanup text (sometimes the text includes tags separated by newlines)
                                    clean_title = text.split("\n")[0].strip()
                                    results.append({"title": clean_title, "url": href, "slug": slug})
                    except Exception:
                        continue

                return results
        except Exception:
            return []

    def _search_series_slug(self, serie_name: str, trace: bool = False) -> Optional[str]:
        page_url = self._search_series_page_url(serie_name, trace=trace)
        if not page_url:
            return None
        return self._extract_slug_from_page_url(page_url)

    def get_episodes_list(self, serie: str, saison: int, trace: bool = False) -> list[int]:
        if self.browser_manager is None:
            return []

        try:
            series_page_url = self._search_series_page_url(serie, trace=trace)
            if not series_page_url:
                if trace:
                    print(f"[trace] get_episodes_list: URL de la série introuvable pour '{serie}'")
                return []

            slug = self._extract_slug_from_page_url(series_page_url) or self._slugify(serie)
            timeout_ms = int(getattr(self.config, "TIMEOUT_SECONDS", 30)) * 1000

            with self.browser_manager as bm:
                page = bm.get_page()
                try:
                    bm.goto_with_retry(page, series_page_url, timeout=timeout_ms)
                    time.sleep(1)
                except Exception as e:
                    if trace:
                        print(f"[trace] get_episodes_list: Erreur navigation: {e}")
                    return []

                anchors = page.query_selector_all("a")
                episodes = set()

                for el in anchors:
                    try:
                        href = (el.get_attribute("href") or "").strip().lower()
                    except Exception:
                        continue

                    if not href or href == "#":
                        continue

                    episode_path = href
                    anchor_prefix = f"/anime/{slug.lower()}/"
                    if anchor_prefix in href:
                        episode_path = href.split(anchor_prefix, 1)[1]

                    match = re.search(r"-(\d{1,4})-vf/?$", episode_path)
                    if not match:
                        match = re.search(r"-(\d{1,4})-vostfr/?$", episode_path)
                    if not match:
                        match = re.search(r"episode-(\d{1,4})/?$", episode_path)
                    if not match:
                        match = re.search(r"^(\d{1,4})/?$", episode_path)

                    if match:
                        ep = int(match.group(1))
                        episodes.add(ep)

                sorted_eps = sorted(list(episodes))
                if trace:
                    print(f"[trace] get_episodes_list: Épisodes trouvés: {sorted_eps}")
                return sorted_eps

        except Exception as e:
            logger.error("Erreur dans get_episodes_list: %s", e)
            return []

    def search_episode(
        self,
        serie: str,
        saison: int,
        episode: int,
        resolution: str = "1080p",
        trace: bool = False,
    ) -> Episode:
        logger.info("search_episode: %s S%sE%s", serie, saison, episode)

        if self.browser_manager is None:
            raise ScraperError("Playwright/BrowserManager non disponible")

        scratch_dir = Path(tempfile.mkdtemp(prefix="magia_scratch_"))
        try:
            try:
                series_page_url = self._search_series_page_url(serie, trace=trace)
            except Exception:
                series_page_url = None

            try:
                found_slug = self._search_series_slug(serie, trace=trace)
            except Exception:
                found_slug = None

            slug = found_slug or self._slugify(serie)
            if trace:
                print(f"[trace] Using slug: {slug} (found: {found_slug})")

            patterns: list[str] = []
            if series_page_url:
                patterns.append(series_page_url)
            patterns.extend(
                self._series_page_patterns(getattr(self.config, "BASE_URL", "https://voir-anime.to"), slug, episode)
            )

            timeout_ms = int(getattr(self.config, "TIMEOUT_SECONDS", 30)) * 1000

            with self.browser_manager as bm:
                page = bm.get_page()
                found_streams: list[str] = []

                def _on_request(req):
                    try:
                        url = req.url
                        if url and (".m3u8" in url.lower() or url.lower().endswith(".mp4")):
                            found_streams.append(url)
                    except Exception:
                        logger.debug("Error in request handler", exc_info=True)

                def _on_response_deep(resp):
                    try:
                        req = resp.request
                        resource_type = req.resource_type
                        status = resp.status
                        if resource_type in ("xhr", "fetch") or "application/json" in (
                            resp.headers.get("content-type", "") if hasattr(resp, "headers") else ""
                        ):
                            if status == 200:
                                try:
                                    body = resp.text()
                                except Exception:
                                    body = None
                                if body:
                                    urls = re.findall(r"https?://[^\"'\s<>]+", body)
                                    for extracted_url in urls:
                                        if ".m3u8" in extracted_url.lower() or extracted_url.lower().endswith(".mp4"):
                                            found_streams.append(extracted_url)
                    except Exception:
                        logger.debug("Error in detailed response handler", exc_info=True)

                try:
                    page.on("request", _on_request)
                    page.on("response", _on_response_deep)
                except Exception:
                    pass

                def _human_pause() -> None:
                    time.sleep(random.uniform(1.0, 3.0))

                for ep_url in patterns:
                    if trace:
                        print(f"[trace] Trying episode URL pattern: {ep_url}")
                    try:
                        bm.goto_with_retry(page, ep_url, timeout=timeout_ms)
                        time.sleep(1)
                        try:
                            html = page.content()
                            self._save_trace_dump(scratch_dir, f"episode_{episode:02d}_page.html", html)
                        except Exception:
                            pass
                    except Exception:
                        continue

                    _human_pause()

                    try:
                        clicked_episode = False
                        target_texts = [str(episode), f"{episode:02d}"]
                        candidates = page.query_selector_all("a")
                        if trace:
                            print(f"[trace] Scanning {len(candidates)} links for episode {episode}")

                        for el in candidates:
                            try:
                                text = (el.inner_text() or "").strip()
                                href = (el.get_attribute("href") or "").strip()
                            except Exception:
                                continue

                            normalized = " ".join(text.split())
                            compact = normalized.lower()
                            href_compact = href.lower()
                            episode_path = href_compact
                            anchor_prefix = f"/anime/{slug.lower()}/"
                            if anchor_prefix in href_compact:
                                episode_path = href_compact.split(anchor_prefix, 1)[1]
                            matched = False
                            for candidate in target_texts:
                                if (
                                    href_compact
                                    and href_compact != "#"
                                    and (
                                        f"-{candidate}-vf" in episode_path
                                        or f"-{candidate}-vostfr" in episode_path
                                        or f"episode-{int(candidate)}" in episode_path
                                        or episode_path.startswith(f"{candidate}/")
                                        or episode_path.startswith(f"{int(candidate):02d}/")
                                    )
                                ):
                                    matched = True
                                    break
                                if compact in {f"ep {candidate}", f"episode {candidate}", f"épisode {candidate}"}:
                                    matched = True
                                    break
                                if re.search(rf"\b{re.escape(candidate)}\b", compact) and "wistoria" not in compact:
                                    matched = True
                                    break

                            if matched:
                                if trace:
                                    print(f"[trace] Clicking episode link matched by text: {normalized!r}")
                                try:
                                    el.click()
                                except Exception:
                                    try:
                                        page.evaluate("element => element.click()", el)
                                    except Exception:
                                        continue
                                try:
                                    page.wait_for_load_state("networkidle")
                                except Exception:
                                    time.sleep(2)
                                try:
                                    html2 = page.content()
                                    self._save_trace_dump(scratch_dir, f"episode_{episode:02d}_clicked.html", html2)
                                except Exception:
                                    pass
                                clicked_episode = True
                                break

                        if not clicked_episode and episode == 1:
                            first_selectors = [
                                'a:has-text("Premier EP")',
                                'a:has-text("Premier EP")',
                                'a:has-text("Premier episode")',
                                'a:has-text("Premier Episode")',
                                'a:has-text("Premier")',
                                'a:has-text("Premier ep")',
                                "text=Premier EP",
                                "text=Premier episode",
                                "text=Premier",
                            ]
                            for selector in first_selectors:
                                try:
                                    el = page.query_selector(selector)  # type: ignore
                                    if el:
                                        if trace:
                                            print(f"[trace] Fallback clicking first-ep selector: {selector}")
                                        try:
                                            el.click()
                                        except Exception:
                                            try:
                                                page.evaluate("element => element.click()", el)
                                            except Exception:
                                                pass
                                        try:
                                            page.wait_for_load_state("networkidle")
                                        except Exception:
                                            time.sleep(2)
                                        try:
                                            html2 = page.content()
                                            self._save_trace_dump(
                                                scratch_dir, f"episode_{episode:02d}_first.html", html2
                                            )
                                        except Exception:
                                            pass
                                        clicked_episode = True
                                        break
                                except Exception:
                                    continue
                    except Exception:
                        clicked_episode = False

                    try:
                        frames = page.query_selector_all("iframe")
                    except Exception:
                        frames = []

                    iframe_srcs: list[str] = []
                    for frame in frames:
                        try:
                            src = frame.get_attribute("src") or ""
                            if src and "youtube" not in src and "youtu.be" not in src:
                                iframe_srcs.append(src)
                        except Exception:
                            continue

                    if trace:
                        print(f"[trace] Found iframe srcs: {iframe_srcs}")

                    for iframe_url in iframe_srcs:
                        try:
                            parsed = urlparse(iframe_url)
                            domain = parsed.netloc or ""
                            if "vidmoly" in domain:
                                if trace:
                                    print("[trace] Detected VidMoly iframe, resolving...")
                                resolved = self._resolve_vidmoly_stream(
                                    iframe_url,
                                    resolution=resolution,
                                    scratch_dir=scratch_dir,
                                    trace=trace,
                                )
                                if resolved:
                                    found_streams.append(resolved)
                                    break
                            else:
                                iframe_context = None
                                iframe_page = None
                                found_if: list[str] = []

                                try:
                                    iframe_context = bm.new_context()
                                    iframe_page = iframe_context.new_page()

                                    def on_req_if(rq):
                                        try:
                                            candidate_url = rq.url
                                            if candidate_url and (
                                                ".m3u8" in candidate_url.lower()
                                                or candidate_url.lower().endswith(".mp4")
                                            ):
                                                found_if.append(candidate_url)
                                        except Exception:
                                            pass

                                    def on_resp_if(resp):
                                        try:
                                            candidate_url = resp.url
                                            if candidate_url and ".m3u8" in candidate_url.lower():
                                                found_if.append(candidate_url)
                                            try:
                                                body = resp.text()
                                            except Exception:
                                                body = ""
                                            if body:
                                                urls = re.findall(r"https?://[^\"'\s<>]+", body)
                                                for extracted_url in urls:
                                                    if (
                                                        ".m3u8" in extracted_url.lower()
                                                        or extracted_url.lower().endswith(".mp4")
                                                    ):
                                                        found_if.append(extracted_url)
                                        except Exception:
                                            pass

                                    try:
                                        iframe_page.on("request", on_req_if)
                                        iframe_page.on("response", on_resp_if)
                                    except Exception:
                                        pass

                                    try:
                                        iframe_page.goto(iframe_url, timeout=20_000)
                                    except Exception:
                                        try:
                                            iframe_page.goto(iframe_url, timeout=40_000)
                                        except Exception:
                                            pass

                                    time.sleep(2)
                                    try:
                                        for selector in [
                                            "button.play",
                                            ".playbtn",
                                            ".btn-play",
                                            "#play",
                                            ".jw-icon-play",
                                            ".vjs-big-play-button",
                                        ]:
                                            try:
                                                element = iframe_page.query_selector(selector)
                                                if element:
                                                    element.click()
                                                    time.sleep(0.5)
                                            except Exception:
                                                continue
                                    except Exception:
                                        pass

                                    time.sleep(3)
                                    try:
                                        html_iframe = iframe_page.content()
                                        self._save_trace_dump(
                                            scratch_dir,
                                            f"iframe_{uuid.uuid4().hex}.html",
                                            html_iframe,
                                        )
                                    except Exception:
                                        pass
                                finally:
                                    try:
                                        if iframe_page is not None:
                                            iframe_page.close()
                                    except Exception:
                                        pass
                                    try:
                                        if iframe_context is not None:
                                            iframe_context.close()
                                    except Exception:
                                        pass

                                for candidate_url in found_if:
                                    found_streams.append(candidate_url)
                        except Exception as exc:
                            if trace:
                                print(f"[trace] error visiting iframe: {exc}")

                    if found_streams:
                        normalized_stream: Optional[str] = None
                        for candidate_url in found_streams:
                            normalized_stream = self._normalize_stream_candidate(
                                candidate_url,
                                resolution=resolution,
                                scratch_dir=scratch_dir,
                                trace=trace,
                                page=page,
                            )
                            if normalized_stream:
                                break

                        if normalized_stream:
                            title = self._page_title(page) or serie

                            extracted_headers: dict[str, str] = {}
                            try:
                                user_agent = page.evaluate("navigator.userAgent")
                                if user_agent:
                                    extracted_headers["User-Agent"] = user_agent
                                else:
                                    extracted_headers["User-Agent"] = getattr(self.config, "USER_AGENT", "Mozilla/5.0")
                            except Exception:
                                extracted_headers["User-Agent"] = getattr(self.config, "USER_AGENT", "Mozilla/5.0")

                            try:
                                cookies = page.context.cookies()
                                if cookies:
                                    cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
                                    if cookie_str:
                                        extracted_headers["Cookie"] = cookie_str
                            except Exception:
                                pass

                            try:
                                if ep_url:
                                    extracted_headers["Referer"] = ep_url
                                else:
                                    extracted_headers["Referer"] = page.url
                            except Exception:
                                pass

                            ep = Episode(
                                series=serie,
                                season=saison,
                                episode=episode,
                                title=title,
                                page_url=ep_url,
                                stream_url=normalized_stream,
                                resolution=resolution,
                                raw_url=ep_url,
                                headers=extracted_headers,
                            )
                            return ep

                raise ScraperError("Aucun flux trouve")
        except Exception as exc:
            logger.exception("Erreur lors du scraping: %s", exc)
            raise ScraperError(str(exc)) from exc
        finally:
            shutil.rmtree(scratch_dir, ignore_errors=True)

    def get_available_episodes(self, serie: str, saison: int) -> list[Episode]:
        eps: list[Episode] = []
        if self.browser_manager is None:
            return eps

        with self.browser_manager as bm:
            page = bm.get_page()
            bm.goto_with_retry(
                page,
                getattr(self.config, "BASE_URL", "https://voir-anime.to"),
                timeout=int(getattr(self.config, "TIMEOUT_SECONDS", 30)) * 1000,
            )
            page.wait_for_timeout(500)
            for anchor in page.query_selector_all("a"):
                text = (anchor.inner_text() or "").lower()
                href = anchor.get_attribute("href") or ""
                if "episode" in text or "ep" in text:
                    eps.append(Episode(series=serie, season=saison, episode=0, title=text, page_url=href))
        return eps

    def _resolve_vidmoly_stream(
        self,
        embed_url: str,
        resolution: Optional[str] = None,
        scratch_dir: Optional[Path] = None,
        trace: bool = False,
    ) -> Optional[str]:
        """Resolve a VidMoly embed URL to a stream URL using Playwright."""

        if self.browser_manager is None:
            return None

        owns_scratch_dir = scratch_dir is None
        scratch_path = scratch_dir or Path(tempfile.mkdtemp(prefix="magia_scratch_"))

        try:
            with self.browser_manager as bm:
                har_path = scratch_path / f"vidmoly_{uuid.uuid4().hex}.har"
                try:
                    if har_path.exists():
                        har_path.unlink()
                except Exception:
                    pass

                ctx = bm.new_context(record_har_path=str(har_path))

                init_script = r"""
                (function(){
                    try{ console.log('VIDMOLY_RESOLVER_INJECTED'); }catch(e){}
                    const PREFIX = 'PLAYBRIDGE_URL:';
                    function notify(u){ try{ console.log(PREFIX + u); }catch(e){} }
                    try{ if(!window.playwright_bridge) window.playwright_bridge = { send_url: function(u){ console.log(PREFIX+u); } }; }catch(e){}
                    try{ const _fetch = window.fetch; window.fetch = function(input, init){ try{ const url = (typeof input === 'string')? input : (input && input.url) || ''; if(url && (url.indexOf('.m3u8')!==-1 || url.indexOf('.mp4')!==-1)) notify(url); }catch(e){} return _fetch.apply(this, arguments); } }catch(e){}
                    try{ const _open = XMLHttpRequest.prototype.open; XMLHttpRequest.prototype.open = function(method, url){ try{ if(url && (url.indexOf('.m3u8')!==-1 || url.indexOf('.mp4')!==-1)) notify(url); }catch(e){} return _open.apply(this, arguments); } }catch(e){}
                    try{ const _create = URL.createObjectURL.bind(URL); URL.createObjectURL = function(obj){ try{ const res = _create(obj); try{ console.log('BLOB_URL:' + res); }catch(e){} return res; }catch(e){ return _create(obj); } } }catch(e){}
                    try{ if(window.MediaSource && MediaSource.prototype){ const _add = MediaSource.prototype.addSourceBuffer; MediaSource.prototype.addSourceBuffer = function(type){ try{ console.log('MS_ADD:' + type); }catch(e){} return _add.apply(this, arguments); } } }catch(e){}
                    try{ const _ws_send = WebSocket.prototype.send; WebSocket.prototype.send = function(data){ try{ let preview = ''; if(typeof data === 'string') preview = data.slice(0,200); else if(data instanceof ArrayBuffer) preview = '[ArrayBuffer:' + data.byteLength + ']'; else if(ArrayBuffer.isView && ArrayBuffer.isView(data)) preview = '[TypedArray:' + data.byteLength + ']'; console.log('WS_SEND:' + preview); }catch(e){} return _ws_send.apply(this, arguments); } }catch(e){}
                    try{ const proto = HTMLMediaElement && HTMLMediaElement.prototype; const desc = Object.getOwnPropertyDescriptor(proto, 'src'); const origSet = desc && desc.set; const origGet = desc && desc.get; Object.defineProperty(proto, 'src', { configurable: true, enumerable: true, get: function(){ try{ return origGet ? origGet.call(this) : this.getAttribute('src'); }catch(e){ return this.getAttribute('src'); } }, set: function(v){ try{ if(v) console.log('MEDIA_SRC_SET:' + v); }catch(e){} try{ if(origSet) return origSet.call(this, v); else return this.setAttribute('src', v); }catch(e){ try{ this.setAttribute('src', v); }catch(e){} } } }); }catch(e){}
                    try{ function attach(el){ try{ el.addEventListener('loadstart', ()=>{ try{ if(el.currentSrc) console.log('MEDIA_LOAD:'+el.currentSrc); }catch(e){} }); el.addEventListener('canplay', ()=>{ try{ if(el.currentSrc) console.log('MEDIA_CANPLAY:'+el.currentSrc); }catch(e){} }); }catch(e){} } Array.from(document.querySelectorAll('video,audio')).forEach(attach); const mo = new MutationObserver(function(muts){ for(const m of muts){ for(const n of m.addedNodes || []){ try{ if(n && n.querySelectorAll) Array.from((n.tagName && (n.tagName.toLowerCase()==='video' || n.tagName.toLowerCase()==='audio'))?[n]:n.querySelectorAll('video,audio')).forEach(attach); }catch(e){} } } }); mo.observe(document.documentElement || document, { childList: true, subtree: true }); } )();
                """

                try:
                    ctx.add_init_script(script=init_script)
                except Exception:
                    pass

                page = ctx.new_page()
                found_urls: list[str] = []
                saved_bodies: list[Path] = []

                def on_console(msg):
                    try:
                        txt = msg.text()
                        if txt and txt.startswith("PLAYBRIDGE_URL:"):
                            found_urls.append(txt.split("PLAYBRIDGE_URL:", 1)[1].strip())
                    except Exception:
                        pass

                def on_response(resp):
                    try:
                        url_r = resp.url
                        if url_r and ".m3u8" in url_r.lower():
                            found_urls.append(url_r)
                        try:
                            txt = resp.text()
                        except Exception:
                            txt = ""
                        if txt:
                            m3u8_urls = re.findall(r"https?://[^\"'\s<>]+\.m3u8", txt)
                            for candidate_url in m3u8_urls:
                                found_urls.append(candidate_url)
                                try:
                                    body_path = scratch_path / f"vidmoly_resp_{len(saved_bodies)}.txt"
                                    body_path.write_text(txt, encoding="utf-8")
                                    saved_bodies.append(body_path)
                                except Exception:
                                    pass
                    except Exception:
                        pass

                try:
                    page.on("console", on_console)
                    page.on("response", on_response)
                except Exception:
                    pass

                page.goto(embed_url, wait_until="domcontentloaded")
                page.wait_for_timeout(1500)

                try:
                    html = page.content()
                    self._save_trace_dump(scratch_path, f"vidmoly_{uuid.uuid4().hex}.html", html)
                    m = re.search(r"https?://[^\"'\s<>]+\.m3u8", html)
                    if m:
                        found_urls.append(m.group(0))
                except Exception:
                    pass

                try:
                    btn = page.query_selector(
                        "button:has-text('Play'), button:has-text('Regarder'), .play-button, .btn-play, .play, #play, .vjs-big-play-button"
                    )
                    if btn:
                        try:
                            btn.click()
                            page.wait_for_timeout(10_000)
                        except Exception:
                            pass
                except Exception:
                    pass

                found = found_urls[0] if found_urls else None

                if not found:
                    try:
                        if har_path.exists():
                            data = har_path.read_text(encoding="utf-8", errors="ignore")
                            urls = re.findall(r"https?://[^\"'\s<>]+\.(?:m3u8|mp4|mpd)", data)
                            if urls:
                                found = urls[0]
                    except Exception:
                        pass

                if found:
                    found = self._normalize_stream_candidate(found, resolution, scratch_path, trace=trace, page=page)

                try:
                    ctx.close()
                except Exception:
                    pass

                for body_path in saved_bodies:
                    try:
                        body_path.unlink(missing_ok=True)
                    except Exception:
                        pass

                return found
        except Exception:
            return None
        finally:
            if owns_scratch_dir:
                shutil.rmtree(scratch_path, ignore_errors=True)
