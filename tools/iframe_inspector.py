#!/usr/bin/env python3
"""Inspecteur d'iframes et XHR pour une page d'épisode.
Usage: python tools/iframe_inspector.py --serie Wistoria --season 1 --episode 1

Sauvegarde les bodies XHR/fetch dans /tmp/xhr-<uuid>.txt
Extrait les iframe[src] (ignore YouTube), visite chaque iframe et tente un clic 'play'.
"""

import argparse
import time
import uuid
import re
from urllib.parse import urlparse

from magia_stream.browser import managed_browser


def save_xhr_body(resp, trace=True):
    try:
        req = resp.request
        rtype = req.resource_type
        url = resp.url
        status = resp.status
    except Exception:
        return
    try:
        ct = ''
        if hasattr(resp, 'headers'):
            ct = resp.headers.get('content-type', '')
    except Exception:
        ct = ''

    if rtype in ('xhr', 'fetch') or 'application/json' in ct or 'text/' in ct:
        if status == 200:
            try:
                body = resp.text()
            except Exception:
                body = None
            try:
                fname = f'/tmp/xhr-{uuid.uuid4().hex}.txt'
                with open(fname, 'w', encoding='utf-8') as fh:
                    fh.write(f'URL: {url}\nSTATUS: {status}\nCONTENT-TYPE: {ct}\n\n')
                    fh.write(body or '')
                if trace:
                    print(f'[trace] saved XHR body to {fname}')
            except Exception as e:
                if trace:
                    print('[trace] failed to save XHR body', e)
            # quick scan for m3u8/mp4
            if body:
                for m in re.findall(r'https?://[^"\'\s<>]+\.(?:m3u8|mp4)', body, re.IGNORECASE):
                    print('[found-in-body]', m)


def inspect_episode(episode_urls, trace=True):
    found_streams = []
    iframe_domains = []
    with managed_browser() as bm:
        ctx = bm.new_context()
        page = ctx.new_page()

        def _on_request(req):
            try:
                url = req.url
                if trace:
                    print('[trace][request]', url)
                if url and ('.m3u8' in url or url.endswith('.mp4')):
                    found_streams.append(url)
            except Exception:
                pass

        def _on_response(resp):
            try:
                save_xhr_body(resp, trace=trace)
            except Exception:
                if trace:
                    print('[trace] error in response handler')

        page.on('request', _on_request)
        page.on('response', _on_response)

        for ep_url in episode_urls:
            if trace:
                print('[trace] trying', ep_url)
            try:
                page.goto(ep_url, timeout=20000)
                time.sleep(1)
                try:
                    html = page.content()
                    with open('/tmp/debug_episode.html', 'w', encoding='utf-8') as f:
                        f.write(html)
                    if trace:
                        print('[trace] saved episode HTML to /tmp/debug_episode.html')
                except Exception:
                    pass

                # extract iframes
                iframe_srcs = []
                try:
                    frames = page.query_selector_all('iframe')
                    for f in frames:
                        try:
                            src = f.get_attribute('src') or ''
                            if not src:
                                continue
                            if 'youtube.com' in src or 'youtu.be' in src:
                                if trace:
                                    print('[trace] skipping YouTube iframe', src)
                                continue
                            iframe_srcs.append(src)
                        except Exception:
                            continue
                except Exception:
                    iframe_srcs = []

                if trace:
                    print('[trace] found iframes on episode page:', iframe_srcs)

                # visit each iframe
                for iframe_url in iframe_srcs:
                    try:
                        dom = urlparse(iframe_url).netloc
                        iframe_domains.append(dom)
                        if trace:
                            print('[trace] visiting iframe', iframe_url)
                        pg = ctx.new_page()

                        def _on_req_if(rq):
                            try:
                                if trace:
                                    print('[trace][iframe-request]', rq.url)
                                u = rq.url
                                if u and ('.m3u8' in u or u.endswith('.mp4')):
                                    found_streams.append(u)
                            except Exception:
                                pass

                        def _on_resp_if(resp):
                            try:
                                save_xhr_body(resp, trace=trace)
                            except Exception:
                                if trace:
                                    print('[trace] iframe response handler error')

                        pg.on('request', _on_req_if)
                        pg.on('response', _on_resp_if)

                        try:
                            pg.goto(iframe_url, timeout=20000)
                        except Exception:
                            try:
                                pg.goto(iframe_url, timeout=40000)
                            except Exception:
                                if trace:
                                    print('[trace] failed to goto iframe')
                        time.sleep(1)
                        # attempt to click common play buttons
                        for sel in ['button.play', '.playbtn', '.btn-play', '#play', '.jw-icon-play', '.vjs-big-play-button']:
                            try:
                                el = pg.query_selector(sel)
                                if el:
                                    if trace:
                                        print('[trace] clicking', sel)
                                    el.click()
                                    time.sleep(0.5)
                            except Exception:
                                continue

                        time.sleep(3)
                        try:
                            pg.close()
                        except Exception:
                            pass

                    except Exception as e:
                        if trace:
                            print('[trace] error visiting iframe', e)

            except Exception as e:
                if trace:
                    print('[trace] goto failed', ep_url, e)

    return iframe_domains, list(set(found_streams))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--serie', default='Wistoria')
    parser.add_argument('--season', type=int, default=1)
    parser.add_argument('--episode', type=int, default=1)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--trace', action='store_true')
    args = parser.parse_args()

    slug = 'wistoria-wand-and-sword-2-vf'
    ep = args.episode
    base = 'https://voir-anime.to'
    patterns = [
        f"{base}/anime/{slug}/{slug}-{ep:02d}-vf/",
        f"{base}/anime/{slug}/{slug}-{ep:02d}-vostfr/",
        f"{base}/anime/{slug}/{ep:02d}/",
        f"{base}/anime/{slug}/episode-{ep}/",
    ]

    domains, streams = inspect_episode(patterns, trace=args.trace)

    print('IFRAME DOMAINS FOUND:')
    for d in set(domains):
        print('-', d)
    print('\nSTREAM URLS FOUND:')
    for s in streams:
        print('-', s)

