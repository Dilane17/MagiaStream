#!/usr/bin/env python3
"""Advanced finder: headful Playwright run to click 'Premier EP' and capture final URL."""
import time
from playwright.sync_api import sync_playwright
from urllib.parse import urljoin

URL = "https://voir-anime.to/anime/wistoria-wand-and-sword-2-vf/"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_context()
        page = ctx.new_page()

        print(f"NAVIGATING {URL}")
        page.goto(URL, wait_until="domcontentloaded")
        time.sleep(2)

        # progressive scroll to trigger lazy loading
        for i in range(8):
            page.evaluate("window.scrollBy(0, document.body.scrollHeight/8)")
            page.wait_for_timeout(500)

        # try to find the button by text
        selector = "a:has-text('Premier EP')"
        el = page.query_selector(selector)
        if not el:
            # broader search
            el = page.query_selector("text=/Premier EP/i")

        if not el:
            print("NO_BUTTON_FOUND")
            # as fallback, search for any element containing 'Premier EP'
            res = page.evaluate("() => Array.from(document.querySelectorAll('*')).filter(e=> (e.innerText||'').toLowerCase().includes('premier ep')).map(e=>({tag:e.tagName, outer:e.outerHTML.slice(0,300)}))")
            print('FALLBACK_RESULTS_COUNT:', len(res))
            for r in res[:10]:
                print(r)
            browser.close()
            return

        # extract attributes and data-*
        info = page.evaluate("(e)=>{const d={};for(const k of e.getAttributeNames()){d[k]=e.getAttribute(k);}return {outer:e.outerHTML.slice(0,400), attrs:d, dataset:e.dataset||{}}}", el)
        print("ELEMENT_OUTER:", info.get('outer'))
        print("ELEMENT_ATTRS:")
        for k,v in (info.get('attrs') or {}).items():
            print(" ", k, "=", v)
        if info.get('dataset'):
            print("DATASET:")
            for k,v in info.get('dataset').items():
                print(" ", k, "=", v)

        # look for candidate URL in attributes/dataset
        candidate = None
        for v in (list((info.get('attrs') or {}).values()) + list((info.get('dataset') or {}).values())):
            if v and isinstance(v, str) and ('http' in v or 'episode' in v or 'episode-' in v):
                # normalize
                if v.startswith('/'):
                    v = urljoin(URL, v)
                candidate = v
                break

        # prepare to capture navigation and requests
        last_frame_nav = []
        def on_frame(frame):
            try:
                if frame.url:
                    last_frame_nav.append(frame.url)
            except Exception:
                pass

        page.on('framenavigated', on_frame)
        reqs = []
        page.on('request', lambda r: reqs.append((r.method, r.url)))

        final_url = None
        if candidate:
            print("FOUND_CANDIDATE_IN_ATTRS:", candidate)
            final_url = candidate
        else:
            print("NO_CANDIDATE_IN_ATTRS, TRYING CLICK")
            try:
                with page.expect_navigation(timeout=10000) as navinfo:
                    el.click()
                nav = navinfo.value
                # nav may be a response; use page.url
                page.wait_for_load_state('networkidle', timeout=5000)
                final_url = page.url
                print("NAV_BY_CLICK captured page.url:", final_url)
            except Exception as e:
                print("CLICK navigation did not produce full navigation:", e)
                # check frame navigations
                page.wait_for_timeout(1500)
                if last_frame_nav:
                    final_url = last_frame_nav[-1]
                    print("LAST_FRAME_NAV:", final_url)
                else:
                    # inspect recent requests for a request containing 'episode'
                    for m,u in reversed(reqs[-200:]):
                        if 'episode' in u.lower() or '/episode-' in u.lower():
                            final_url = u
                            print("FOUND_EPISODE_URL_IN_REQUESTS:", final_url)
                            break

        if final_url:
            # normalize
            if final_url.startswith('/'):
                final_url = urljoin(URL, final_url)
            print('\nFINAL_URL:', final_url)
        else:
            print('NO_FINAL_URL_FOUND')

        browser.close()


if __name__ == '__main__':
    main()
