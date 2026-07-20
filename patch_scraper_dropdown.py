with open("magia_stream/scraper.py", "r") as f:
    content = f.read()

import re

# Find the search_series_all_results function body
start_idx = content.find("def search_series_all_results(")
end_idx = content.find("def _search_series_slug(", start_idx)

old_method = content[start_idx:end_idx]

new_method = """def search_series_all_results(self, serie_name: str, trace: bool = False) -> list[dict[str, str]]:
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
                for selector in ["input[placeholder*='VF']", "input[placeholder*='vf']", ".search-input", "input[name='s']"]:
                    try:
                        if page.query_selector(selector):
                            search_selector = selector
                            break
                    except Exception:
                        continue
                
                if not search_selector:
                    return []
                    
                # 3. Type into the input to trigger the AJAX dropdown
                page.fill(search_selector, serie_name)
                time.sleep(3) # Wait for AJAX dropdown to appear
                
                # 4. Extract NEW links that appeared (the dropdown results)
                results = []
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
                                    clean_title = text.split('\\n')[0].strip()
                                    results.append({"title": clean_title, "url": href, "slug": slug})
                    except Exception:
                        continue
                
                return results
        except Exception:
            return []

    """

content = content.replace(old_method, new_method)

with open("magia_stream/scraper.py", "w") as f:
    f.write(content)
