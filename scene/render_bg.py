"""Render the Prism background strip (scene.html) to stills and seamless video loops.

    python scene/render_bg.py --stills            # kit/assets/bg/bg_01.jpg … bg_10.jpg  (2160x2700)
    python scene/render_bg.py --loops             # kit/assets/bg/bg_01.mp4 … bg_10.mp4  (1080x1350, 6 s, 25 fps)
    python scene/render_bg.py --preview           # quick 1080 stills into scene/preview/

Needs: pip install playwright && a Chrome/Chromium, plus ffmpeg for --loops.
Run from the repo root (it starts a tiny local web server so the page can load tokens.json).
"""
import argparse, base64, functools, http.server, os, subprocess, sys, threading, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'kit', 'assets', 'bg')
FPS, SECONDS, N = 25, 6, 10


def serve():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT)
    handler.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv.server_address[1]


def open_page(pw, port, pr):
    exe = shutil.which('google-chrome') or shutil.which('chromium') or shutil.which('chromium-browser')
    browser = pw.chromium.launch(executable_path=exe, args=['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'])
    page = browser.new_page(viewport={'width': 1080, 'height': 1350}, device_scale_factor=1)
    page.on('console', lambda m: print('[page]', m.text) if m.type in ('error', 'warning') else None)
    page.goto(f'http://127.0.0.1:{port}/scene/scene.html?pr={pr}')
    page.wait_for_function('window.ready === true', timeout=120000)
    return browser, page


def grab(page, i, t):
    data = page.evaluate(f'(() => {{ drawSlide({i}, {t}); return frameData(); }})()')
    return base64.b64decode(data.split(',', 1)[1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stills', action='store_true')
    ap.add_argument('--loops', action='store_true')
    ap.add_argument('--preview', action='store_true')
    ap.add_argument('--only', type=int, nargs='*', help='slide numbers (1-10)')
    ap.add_argument('--still-time', type=float, default=1.2)
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright
    port = serve()
    slides = [s - 1 for s in (a.only or range(1, N + 1))]
    os.makedirs(OUT, exist_ok=True)
    with sync_playwright() as pw:
        if a.preview or a.stills:
            pr = 1 if a.preview else 2
            browser, page = open_page(pw, port, pr)
            dst = os.path.join(ROOT, 'scene', 'preview') if a.preview else OUT
            os.makedirs(dst, exist_ok=True)
            from PIL import Image
            import io
            for i in slides:
                im = Image.open(io.BytesIO(grab(page, i, a.still_time))).convert('RGB')
                if a.preview:
                    im.save(os.path.join(dst, f'bg_{i + 1:02d}.png'))
                else:  # JPEG keeps the kit small enough to upload into a chat (grain makes PNGs ~7 MB each)
                    im.save(os.path.join(dst, f'bg_{i + 1:02d}.jpg'), quality=92, subsampling=0)
                print('still', i + 1, flush=True)
            browser.close()
        if a.loops:
            browser, page = open_page(pw, port, 1)
            for i in slides:
                out = os.path.join(OUT, f'bg_{i + 1:02d}.mp4')
                ff = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'image2pipe', '-framerate', str(FPS), '-i', '-',
                                       '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p',
                                       '-movflags', '+faststart', out], stdin=subprocess.PIPE)
                for k in range(FPS * SECONDS):
                    ff.stdin.write(grab(page, i, k / FPS))
                ff.stdin.close(); ff.wait()
                print('loop', i + 1, flush=True)
            browser.close()


if __name__ == '__main__':
    main()
