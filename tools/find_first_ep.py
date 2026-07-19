#!/usr/bin/env python3
"""Trouve le lien du premier épisode sur la page de la série (voir-anime.to).

Usage: python tools/find_first_ep.py
"""
from playwright.sync_api import sync_playwright
import sys

URL = "https://voir-anime.to/anime/wistoria-wand-and-sword-2-vf/"

def find_first_episode(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()
        resp = page.goto(url, wait_until="domcontentloaded")
        print(f"DEBUG: navigated to {page.url} status={resp.status if resp else 'noresp'}")
        # attendre que le JS client charge la liste des épisodes si nécessaire
        try:
            page.wait_for_load_state('networkidle', timeout=3000)
        except Exception:
            pass
        page.wait_for_timeout(800)

        # heuristiques pour trouver le lien "Premier EP" / premier épisode
        selectors = [
            "a:has-text('Premier EP')",
            "a:has-text('Premier épisode')",
            "a:has-text('Episode 1')",
            "a:has-text('EP 1')",
            "a:has-text('Ep 1')",
            "a:has-text('Épisode 1')",
            "a.btn-primary:has-text('EP')",
            "a.btn-ep",
            "a[href*='episode-1']",
        ]

        # chercher les sélecteurs simples d'abord
        for sel in selectors:
            try:
                el = page.query_selector(sel)
                print(f"DEBUG: try selector {sel} -> {'FOUND' if el else 'MISS'}")
                if el:
                    href = el.get_attribute('href')
                    print(f"DEBUG: selector {sel} href={href}")
                    if href and href.strip() and href not in ('#', 'javascript:void(0)') and not href.lower().startswith('javascript:'):
                        return href
                    # if href is placeholder, inspect dataset / onclick / data-href
                    info = page.evaluate("el=>({dataset: el.dataset||null, dataHref: el.getAttribute('data-href')||null, onclick: el.getAttribute('onclick')||null, outerHTML: el.outerHTML}), el", el)
                    print(f"DEBUG: extra element info: dataset={info.get('dataset')} data-href={info.get('dataHref')} onclick={info.get('onclick')}")
                    # attempt to find a navigable URL in dataset or onclick
                    for candidate in (info.get('dataHref'), info.get('onclick')):
                        if candidate and 'http' in candidate:
                            # extract first http... occurrence
                            import re
                            m = re.search(r"https?://[\w\-./?&=%]+", candidate)
                            if m:
                                return m.group(0)
                    # try clicking the element and wait for navigation
                    try:
                        with page.expect_navigation(timeout=5000):
                            el.click()
                        print(f"DEBUG: clicked selector {sel}, new url={page.url}")
                        return page.url
                    except Exception as e:
                        print(f"DEBUG: click/navigation failed: {e}")
            except Exception:
                continue

        # fallback: parcourir la liste des épisodes et prendre le premier link utile
        try:
            # extraire côté client les ancres (href absolu + texte)
            anchors = page.evaluate("() => Array.from(document.querySelectorAll('a')).map(a=>({href: a.getAttribute('href')||'', hrefAbs: a.href||'', text: (a.innerText||'').trim()}))")
            print(f"DEBUG: total anchors found={len(anchors)}")
            for a in anchors[:200]:
                # afficher quelques ancres pour diagnostic
                if a['href'] or a['hrefAbs']:
                    pass
            for a in anchors:
                href = a.get('href') or a.get('hrefAbs')
                txt = a.get('text') or ''
                if not href or href.strip() in ('', '#') or href.lower().startswith('javascript:'):
                    continue
                low = txt.lower()
                if 'episode 1' in low or 'ep 1' in low or 'épisode 1' in low or ('episode-1' in href.lower()) or ('episode/1' in href.lower()):
                    print(f"DEBUG: matched anchor text='{txt}' href={href}")
                    return href
            # as last resort, collect anchors containing 'episode' in href
            candidates = []
            for a in anchors:
                href = a.get_attribute('href')
                txt = (a.inner_text() or '').strip()
                if href and 'episode' in href.lower():
                    candidates.append((txt, href))
            print(f"DEBUG: candidates with 'episode' in href: {len(candidates)}")
            for i, (txt, href) in enumerate(candidates[:20]):
                print(f"CAND[{i}] text='{txt}' href={href}")
            # prefer explicit 'episode-1' in href
            for txt, href in candidates:
                if 'episode-1' in href.lower() or 'episode-01' in href.lower():
                    print(f"DEBUG: choosing candidate (episode-1) href={href}")
                    return href
            # else pick first candidate if any
            if candidates:
                print(f"DEBUG: choosing first candidate href={candidates[0][1]}")
                return candidates[0][1]
        except Exception:
            pass

        return None

def main():
    href = find_first_episode(URL)
    if not href:
        print('NO_EPISODE_FOUND', file=sys.stderr)
        sys.exit(2)
    # normaliser URL: faire relative -> absolute si besoin
    if href.startswith('/'):
        from urllib.parse import urljoin
        href = urljoin(URL, href)
    print(href)

if __name__ == '__main__':
    main()
