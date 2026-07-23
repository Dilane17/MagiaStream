import re
with open("magia_stream/scraper.py", "r") as f:
    content = f.read()

new_method = """
    def search_series_all_results(self, serie_name: str, trace: bool = False) -> list[dict[str, str]]:
        if self.browser_manager is None:
            return []
        
        try:
            with self.browser_manager.get_page(trace=trace) as page:
                bm = self.browser_manager
                timeout_ms = bm.page_timeout
                base_url = getattr(self.config, 'BASE_URL', 'https://voir-anime.to').rstrip('/')
                
                # Navigate to home
                bm.goto_with_retry(page, f"{base_url}/", timeout=timeout_ms)
                import time, random
                time.sleep(2)
                
                search_selector = None
                for selector in [".search-input", "input[name='s']", "input[type='search']", "#s", ".search-field"]:
                    try:
                        if page.query_selector(selector):
                            search_selector = selector
                            break
                    except Exception:
                        continue
                
                def _load_search_results() -> None:
                    try:
                        if search_selector:
                            page.fill(search_selector, serie_name)
                            time.sleep(random.uniform(0.5, 1.2))
                            page.press(search_selector, "Enter")
                            time.sleep(2.5)
                        else:
                            raise ValueError("No selector")
                    except Exception:
                        from urllib.parse import quote_plus
                        search_url = f"{base_url}?s={quote_plus(serie_name)}&post_type=wp-manga"
                        bm.goto_with_retry(page, search_url, timeout=timeout_ms)
                        time.sleep(2)
                
                _load_search_results()
                
                try:
                    page.wait_for_selector('a[href*="/anime/"]', timeout=10_000)
                except Exception:
                    pass
                
                anchors = page.query_selector_all('a[href*="/anime/"]')
                results = []
                seen = set()
                
                for anchor in anchors:
                    try:
                        href = (anchor.get_attribute("href") or "").strip()
                        text = (anchor.inner_text() or "").strip()
                        if href and text and href not in seen:
                            slug = self._extract_slug_from_page_url(href)
                            if slug:
                                results.append({"title": text, "url": href, "slug": slug})
                                seen.add(href)
                    except Exception:
                        continue
                
                return results
        except Exception:
            return []
            
"""
# insert before _search_series_slug
content = content.replace("    def _search_series_slug(", new_method + "\n    def _search_series_slug(")

with open("magia_stream/scraper.py", "w") as f:
    f.write(content)
