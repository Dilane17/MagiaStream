#!/usr/bin/env python3
"""Resolve VidMoly embed pages to find .m3u8 streams.

Usage: python tools/resolve_vidmoly.py https://vidmoly.biz/embed-...html
"""
import sys
import re
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright


def find_m3u8_in_text(text):
    if not text:
        return None
    # common patterns
    m = re.search(r"https?://[\w\-./?=&%]+\.m3u8", text)
    if m:
        return m.group(0)
    # sometimes escaped
    m = re.search(r"(index|file)[^\"'\\]{0,40}\.m3u8", text)
    if m:
        # try to grab surrounding URL-like token
        m2 = re.search(r"https?://[\w\-./?=&%]+" + re.escape(m.group(0)), text)
        if m2:
            return m2.group(0)
    return None


def resolve(url):
    found = None
    with sync_playwright() as p:
        # use headful so injected init script runs before site JS
        browser = p.chromium.launch(headless=False)
        import os
        # remove old HAR if present
        try:
            if os.path.exists('/tmp/vidmoly.har'):
                os.remove('/tmp/vidmoly.har')
        except Exception:
            pass
        # create context that records HAR to /tmp/vidmoly.har
        ctx = browser.new_context(record_har_path='/tmp/vidmoly.har')

        # inject a more aggressive init script to catch blobs, MSE and WebSocket activity
        init_script = r'''
        (function(){
            const PREFIX = 'PLAYBRIDGE_URL:';
            function notify(u){
                try{ console.log(PREFIX + u); }catch(e){}
            }

            // ensure playwright_bridge stub
            try{ if(!window.playwright_bridge) window.playwright_bridge = { send_url: function(u){ console.log(PREFIX+u); } }; }catch(e){}

            // wrap fetch
            try{
                const _fetch = window.fetch;
                window.fetch = function(input, init){
                    try{ const url = (typeof input === 'string')? input : (input && input.url) || ''; if(url && (url.indexOf('.m3u8')!==-1 || url.indexOf('.mp4')!==-1)) notify(url); }catch(e){}
                    return _fetch.apply(this, arguments);
                }
            }catch(e){}

            // wrap XHR open
            try{ const _open = XMLHttpRequest.prototype.open; XMLHttpRequest.prototype.open = function(method, url){ try{ if(url && (url.indexOf('.m3u8')!==-1 || url.indexOf('.mp4')!==-1)) notify(url); }catch(e){} return _open.apply(this, arguments); } }catch(e){}

            // override URL.createObjectURL to capture blob urls
            try{
                const _create = URL.createObjectURL.bind(URL);
                URL.createObjectURL = function(obj){
                    try{
                        const res = _create(obj);
                        try{ console.log('BLOB_URL:' + res); }catch(e){}
                        return res;
                    }catch(e){ return _create(obj); }
                }
            }catch(e){}

            // monitor MediaSource.addSourceBuffer to log MIME types
            try{
                if(window.MediaSource && MediaSource.prototype){
                    const _add = MediaSource.prototype.addSourceBuffer;
                    MediaSource.prototype.addSourceBuffer = function(type){
                        try{ console.log('MS_ADD:' + type); }catch(e){}
                        return _add.apply(this, arguments);
                    }
                }
            }catch(e){}

            // intercept WebSocket.send
            try{
                const _ws_send = WebSocket.prototype.send;
                WebSocket.prototype.send = function(data){
                    try{
                        let preview = '';
                        if(typeof data === 'string') preview = data.slice(0,200);
                        else if(data instanceof ArrayBuffer) preview = '[ArrayBuffer:' + data.byteLength + ']';
                        else if(ArrayBuffer.isView && ArrayBuffer.isView(data)) preview = '[TypedArray:' + data.byteLength + ']';
                        console.log('WS_SEND:' + preview);
                    }catch(e){}
                    return _ws_send.apply(this, arguments);
                }
            }catch(e){}

            // monitor HTMLMediaElement.src via descriptor
            try{
                const proto = HTMLMediaElement && HTMLMediaElement.prototype;
                const desc = Object.getOwnPropertyDescriptor(proto, 'src');
                const origSet = desc && desc.set;
                const origGet = desc && desc.get;
                Object.defineProperty(proto, 'src', {
                    configurable: true,
                    enumerable: true,
                    get: function(){ try{ return origGet ? origGet.call(this) : this.getAttribute('src'); }catch(e){ return this.getAttribute('src'); } },
                    set: function(v){ try{ if(v) console.log('MEDIA_SRC_SET:' + v); }catch(e){} try{ if(origSet) return origSet.call(this, v); else return this.setAttribute('src', v); }catch(e){ try{ this.setAttribute('src', v); }catch(e){} } }
                });
            }catch(e){}

            // attach events to existing and future media elements
            try{
                function attach(el){ try{ el.addEventListener('loadstart', ()=>{ try{ if(el.currentSrc) console.log('MEDIA_LOAD:'+el.currentSrc); }catch(e){} }); el.addEventListener('canplay', ()=>{ try{ if(el.currentSrc) console.log('MEDIA_CANPLAY:'+el.currentSrc); }catch(e){} }); }catch(e){} }
                Array.from(document.querySelectorAll('video,audio')).forEach(attach);
                const mo = new MutationObserver(function(muts){ for(const m of muts){ for(const n of m.addedNodes || []){ try{ if(n && n.querySelectorAll) Array.from((n.tagName && (n.tagName.toLowerCase()==='video' || n.tagName.toLowerCase()==='audio'))?[n]:n.querySelectorAll('video,audio')).forEach(attach); }catch(e){} } } });
                mo.observe(document.documentElement || document, { childList: true, subtree: true });
            }catch(e){}

        })();
        '''
        ctx.add_init_script(script=init_script)

        page = ctx.new_page()

        nonlocal_found = []
        nonlocal_saved = []

        def on_console(msg):
            try:
                txt = msg.text()
                if txt and txt.startswith('PLAYBRIDGE_URL:'):
                    val = txt.split('PLAYBRIDGE_URL:')[1].strip()
                    nonlocal_found.append(val)
                    print('CONSOLE_CAPTURE:', val)
            except Exception:
                pass

        def on_response(resp):
            try:
                url_r = resp.url
                # quick check in url
                if url_r and '.m3u8' in url_r.lower():
                    print('FOUND_M3U8_IN_URL:', url_r)
                    nonlocal_found.append(url_r)
                # try reading body
                try:
                    txt = resp.text()
                except Exception:
                    txt = ''
                m = find_m3u8_in_text(txt)
                if m:
                    print('FOUND_IN_RESPONSE_BODY:', m, 'from', url_r)
                    try:
                        idx = len(nonlocal_saved)
                        path = f"/tmp/vidmoly_resp_{idx}.txt"
                        open(path, 'w', encoding='utf-8', errors='ignore').write(txt)
                        nonlocal_saved.append(path)
                        nonlocal_found.append(m)
                    except Exception:
                        nonlocal_found.append(m)
            except Exception:
                pass

        page.on('console', on_console)
        page.on('response', on_response)

        # navigate and give scripts time to run
        page.goto(url, wait_until='domcontentloaded')
        page.wait_for_timeout(1500)

        # save initial html
        try:
            html = page.content()
            open('/tmp/vidmoly_page.html', 'w', encoding='utf-8', errors='ignore').write(html)
            m = find_m3u8_in_text(html)
            if m:
                print('FOUND_IN_HTML:', m)
                nonlocal_found.append(m)
        except Exception:
            html = ''

        # check inline scripts for m3u8
        if not nonlocal_found:
            scripts = page.query_selector_all('script')
            for s in scripts:
                try:
                    txt = s.inner_text()
                    if 'sources' in txt or '.m3u8' in txt:
                        m = find_m3u8_in_text(txt)
                        if m:
                            print('FOUND_IN_SCRIPT:', m)
                            nonlocal_found.append(m)
                            break
                except Exception:
                    continue

        # attempt to click play and wait longer (10s)
        if not nonlocal_found:
            btn = page.query_selector("button:has-text('Play'), button:has-text('Regarder'), .play-button, .btn-play, .play, #play, .vjs-big-play-button")
            if btn:
                try:
                    print('CLICK play button')
                    btn.click()
                    page.wait_for_timeout(10000)
                except Exception as e:
                    print('CLICK_PLAY_FAILED', e)

        # after wait, check collected urls
        found_url = nonlocal_found[0] if nonlocal_found else None
        if nonlocal_saved:
            print('Saved response bodies to:')
            for p in nonlocal_saved[:10]:
                print(' ', p)

        if found_url:
            print('\nFINAL_M3U8:', found_url)
            browser.close()
            return found_url

        browser.close()
    return found


def main():
    if len(sys.argv) < 2:
        print('Usage: resolve_vidmoly.py <embed-url>')
        sys.exit(1)
    url = sys.argv[1]
    m = resolve(url)
    if m:
        print('\nFINAL_M3U8:', m)
    else:
        print('NO_M3U8_FOUND')


if __name__ == '__main__':
    main()
